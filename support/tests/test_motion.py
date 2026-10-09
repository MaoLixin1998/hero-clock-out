"""验证实际位移、起跑保护、追击与重开行为。"""

# 二维距离用于独立比较横走与斜走的实际位移。
import math
# 标准测试框架负责断言与失败报告。
import unittest

# 正式规则按例读取，避免测试之间共享可变配置。
from hero_game.config import load_game_rules
# 应用工厂显式读取正式默认数据，纯模型本身不承担文件IO。
from hero_game.app.game_factory import create_game


# 运动回归使用独立游戏实例与有限时长，不依赖个人动画素材。
class MotionChecks(unittest.TestCase):
    # 检查斜走与横走速度一致，并验证松键立即停止。
    def test_diagonal_distance_matches_horizontal(self) -> None:
        # 创建两份独立游戏状态，都跳过开场，分别用于横走和斜走比较。
        straight, diagonal = create_game(play_intro=False), create_game(play_intro=False)
        # 分别给两份状态传入向右与向右下的单位按键方向。
        for model, vector in ((straight, (1, 0)), (diagonal, (1, 1))):
            # 把两名测试勇者放到相同起点，排除出生位置差异。
            model.hero.x, model.hero.y = 250, 230
            # 每个方向都模拟十次，使总移动时间相同。
            for _ in range(10):
                # 每次更新 0.025 秒，星号把方向元组展开成横、纵参数。
                model.update(0.025, *vector)
        # 计算横走测试里勇者离起点的实际直线距离。
        straight_distance = math.hypot(straight.hero.x - 250, straight.hero.y - 230)
        # 计算斜走测试里勇者离同一起点的直线距离。
        diagonal_distance = math.hypot(diagonal.hero.x - 250, diagonal.hero.y - 230)
        # 确认两种方向走过的距离近似相等，归一化没有让斜向加速。
        self.assertAlmostEqual(straight_distance, diagonal_distance)
        # 保存松开方向键之前的勇者坐标。
        before = (straight.hero.x, straight.hero.y)
        # 不传方向更新一帧，模拟所有移动键已经松开。
        straight.update(0.05)
        # 确认坐标完全没变，松键后没有额外漂移。
        self.assertEqual(before, (straight.hero.x, straight.hero.y))

    # 检查勇者和史莱姆都留在活动边界内，贴墙时不原地走路。
    def test_both_actors_stay_inside_bounds(self) -> None:
        # 创建跳过开场的游戏，直接检查活动边界。
        model = create_game(play_intro=False)
        # 分别检查勇者与史莱姆，确保双方都遵守边界。
        for actor in (model.hero, model.slime):
            # 重复足够多次移动，让角色一定到达右下角并继续尝试越界。
            for _ in range(200):
                # 直接调用角色移动，避免追击和失败状态干扰边界检查。
                actor.move(1, 1, 0.05, 160, model.bounds)
            # 确认脚底停在配置的右边界和下边界，没有越出活动区域。
            self.assertEqual((actor.x, actor.y), (model.bounds[2], model.bounds[3]))
            # 确认到墙边不能继续位移时，moving 为 False，不原地播走路动画。
            self.assertFalse(actor.moving)

    # 检查暂停冻结角色全部字段与有效时间、转向倒计时。
    def test_pause_freezes_clock_position_and_animation(self) -> None:
        # 创建能直接开始追击的状态，准备检查暂停冻结。
        model = create_game(play_intro=False)
        # 去掉开场等待，让史莱姆也先发生一点真实移动。
        model.start_delay = 0
        # 模拟勇者向右移动 0.04 秒，使坐标、动画和反应计时都有变化。
        model.update(0.04, 1, 0)
        # 复制双方全部字段和游戏计时，作为暂停前的独立快照。
        before = (vars(model.hero).copy(), vars(model.slime).copy(), model.elapsed, model.retarget_in)
        # 主动设置暂停标志，后续更新都应该被拦住。
        model.paused = True
        # 重复更新一百次，相当于给暂停状态足够长的时间。
        for _ in range(100):
            # 即使传入左下方向，暂停中的输入也不应该改变世界。
            model.update(0.05, -1, 1)
        # 比较完整快照，确认位置、朝向、动画时间和追击倒计时都未变化。
        self.assertEqual(before, (vars(model.hero), vars(model.slime), model.elapsed, model.retarget_in))

    # 检查史莱姆确实会追上勇者，并在被抓后冻结双方。
    def test_automatic_chase_captures_without_pet_stopping_distance(self) -> None:
        # 创建直接追逐的游戏，勇者不输入移动，方便等史莱姆追上。
        model = create_game(play_intro=False)
        # 推进一百个更新步，给敌人足够时间从出生点走到勇者旁边。
        for _ in range(100):
            # 没有方向输入，勇者保持原地，只有史莱姆执行自动追击。
            model.update(0.05)
        # 确认最后触发被抓，史莱姆没有像宠物一样在附近停靠。
        self.assertTrue(model.caught)
        # 复制被抓时双方全部字段与游戏时间，作为失败冻结的对照。
        before = (vars(model.hero).copy(), vars(model.slime).copy(), model.elapsed)
        # 尝试在失败后向右移动，检查失败规则是否仍阻止位移。
        model.update(0.05, 1, 0)
        # 确认双方状态和有效时间都没变，失败不会继续跑动。
        self.assertEqual(before, (vars(model.hero), vars(model.slime), model.elapsed))

    # 检查开场缓冲只让敌人等待，勇者能先跑，缓冲结束开始追。
    def test_start_grace_only_freezes_slime(self) -> None:
        # 创建新的一局，保留配置中的 0.8 秒开场缓冲。
        model = create_game(play_intro=False)
        # 保存史莱姆出生坐标，稍后比较它在缓冲内是否真的静止。
        before = (model.slime.x, model.slime.y)
        # 模拟十六次、每次 0.05 秒，刚好覆盖 0.8 秒缓冲。
        for _ in range(16):
            # 勇者在等待期间持续向右跑，验证缓冲只约束敌人。
            model.update(0.05, 1, 0)
        # 确认十六步结束时敌人仍在原位置，没有提前追击。
        self.assertEqual(before, (model.slime.x, model.slime.y))
        # 确认勇者横坐标大于出生横坐标，等待期间可以先跑。
        self.assertGreater(model.hero.x, model.rules["heroSpawn"][0])
        # 再更新 0.05 秒，已经进入缓冲结束后的追击时间。
        model.update(0.05)
        # 确认史莱姆这次发生位移，缓冲结束确实开始追。
        self.assertNotEqual(before, (model.slime.x, model.slime.y))

    # 检查敌人按间隔重新瞄准，目标突然转向不会被即时跟随。
    def test_slime_reacts_to_turn_after_interval(self) -> None:
        # 创建追逐状态，单独检查转向反应间隔。
        model = create_game(play_intro=False)
        # 取消开场等待，让第一次更新立即锁定追击方向。
        model.start_delay = 0
        # 把史莱姆放在左侧固定高度，与勇者保持水平关系。
        model.slime.x, model.slime.y = 200, 240
        # 把勇者放在同一高度的右侧，让首次瞄准只朝右。
        model.hero.x, model.hero.y = 400, 240
        # 更新 0.05 秒，使史莱姆第一次瞄准并向右移动。
        model.update(0.05)
        # 把勇者突然移到上方，模拟目标在一个转向周期内改变位置。
        model.hero.y = 180
        # 再过 0.05 秒，尚未用完 0.2 秒反应间隔。
        model.update(0.05)
        # 确认史莱姆仍在原高度，不能每帧立刻朝新位置转向。
        self.assertAlmostEqual(model.slime.y, 240)
        # 再更新三次，跨过下一次反应时刻。
        for _ in range(3):
            # 每次增加 0.05 秒，使总模拟时间足以触发重新瞄准。
            model.update(0.05)
        # 确认史莱姆纵坐标开始变小，也就是重新朝上方目标追。
        self.assertLess(model.slime.y, 240)

    # 检查配置中的勇者速度优势确实能让直线距离扩大。
    def test_hero_outruns_slime_in_straight_line(self) -> None:
        # 创建直接追逐状态，准备比较双方的直线速度。
        model = create_game(play_intro=False)
        # 取消敌人等待，只检查同时移动时的速度差。
        model.start_delay = 0
        # 把勇者放在活动区内，让它有足够向右跑的距离。
        model.hero.x, model.hero.y = 320, 240
        # 把史莱姆放在勇者左边 100 像素处，两者高度相同。
        model.slime.x, model.slime.y = 220, 240
        # 更新二十步，每步 0.05 秒，一共模拟一秒。
        for _ in range(20):
            # 勇者持续向右跑，敌人也沿同一直线追。
            model.update(0.05, 1, 0)
        # 速度差是每秒 40 像素，一秒后 100 像素间距应扩大到 140。
        self.assertAlmostEqual(model.hero.x - model.slime.x, 140)
        # 确认直线跑期间没有被抓，速度优势实际生效。
        self.assertFalse(model.caught)

    # 连续十次重开，检查出生点、时间、方向和失败标记全部复位。
    def test_reset_restores_chase_and_configured_clock(self) -> None:
        # 创建无需播放开场的状态，准备先制造一次真实被抓。
        model = create_game(play_intro=False)
        # 重复一百步，让原地勇者被敌人追上。
        for _ in range(100):
            # 每步正常推进追击，不直接伪造 caught 字段。
            model.update(0.05)
        # 确认真的进入失败状态，后面重置的是实际失败后的游戏。
        self.assertTrue(model.caught)
        # 连续做十次重开，检查复位不会累加速度或残留状态。
        for _ in range(10):
            # 调用游戏的真实 reset，把这一局恢复到开始位置。
            model.reset()
            # 确认勇者坐标恢复为配置中的出生点。
            self.assertEqual((model.hero.x, model.hero.y), tuple(model.rules["heroSpawn"]))
            # 确认史莱姆坐标也恢复，不能沿用上一局的位置。
            self.assertEqual((model.slime.x, model.slime.y), tuple(model.rules["slimeSpawn"]))
            # 确认有效游戏时间归零，不把上一局的时间带进新局。
            self.assertEqual(model.elapsed, 0)
            # 确认转向倒计时归零，第一次追击会重新瞄准。
            self.assertEqual(model.retarget_in, 0)
            # 确认旧方向清空，重开不会继承上一局敌人的运动方向。
            self.assertEqual(model.chase_direction, (0, 0))
            # 确认被抓标记清除，新一局不再保持失败冻结。
            self.assertFalse(model.caught)
        # 确认重开仍使用本局配置的时钟文字，不偷偷改动显示字段。
        self.assertEqual(model.clock_text, model.rules["clockText"])

    # 比较三个帧率下一秒追击结果，检查反应规则依赖秒数。
    def test_reaction_interval_is_frame_rate_independent(self) -> None:
        # 准备收集三个帧率下同一段模拟的最终结果。
        results = []
        # 依次检查 30、60、120 FPS，验证追击反应依赖时间而不是帧数。
        for frames_per_second in (30, 60, 120):
            # 每个帧率都使用独立新游戏，避免继承之前的坐标和计时。
            model = create_game(play_intro=False)
            # 取消开场等待，只比较追击时间切分的帧率一致性。
            model.start_delay = 0
            # 把勇者放到相同测试起点，保证三个场景初始状态一致。
            model.hero.x, model.hero.y = 320, 300
            # 把史莱姆也放到相同起点，避免不同初始距离干扰结果。
            model.slime.x, model.slime.y = 100, 180
            # 每秒帧数与更新次数相同，正好覆盖一秒模拟时间。
            for _ in range(frames_per_second):
                # 每次时间取帧率的倒数，勇者持续向右跑，总模拟时长保持一致。
                model.update(1 / frames_per_second, 1, 0)
            # 记录勇者横坐标和敌人二维位置，供不同帧率相互比较。
            results.append((model.hero.x, model.slime.x, model.slime.y))
        # 以 30 FPS 结果为基准，逐个检查后面两种帧率。
        for result in results[1:]:
            # 把基准与当前结果的每个坐标逐项配对。
            for expected_coordinate, actual_coordinate in zip(results[0], result):
                # 确认坐标在六位小数精度内一致，不同帧率没有改变追击结果。
                self.assertAlmostEqual(expected_coordinate, actual_coordinate, places=6)

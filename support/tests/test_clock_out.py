"""验证有效游戏计时、可达出口、事件先后和下班终态。"""

# 标准测试框架记录游戏行为，而不依赖真实窗口或等待墙上时间。
import unittest

# 正式工厂提供默认对白，测试只覆盖必要的规则参数。
from hero_game.app.game_factory import create_game
# 正式规则读取为每个案例提供独立配置。
from hero_game.config import load_game_rules


# 使用真实逐帧更新验证时间和通行，避免只断言人工写入的成功标记。
class ClockOutChecks(unittest.TestCase):
    # 默认一局在60秒开放，门未进入时不会自动通关，钟面停在下班时刻。
    def test_clock_reaches_shift_end_at_sixty_active_seconds(self) -> None:
        # 极慢的测试敌人隔离计时规则，避免原地等待被抓。
        rules = {**load_game_rules(), "slimeSpeed": 0.001}
        # 跳过开场后进入真实有效游戏计时。
        model = create_game(rules=rules, play_intro=False)
        # 先走满59.95秒，保持在门槛之外。
        for _ in range(1199):
            # 模型每次至多接收0.05秒，不用大步长绕过真实帧循环。
            model.update(0.05)
        # 推进到59.999秒，最后一毫秒尚未到点。
        model.update(0.049)
        # 到点前钟面仍是17:29。
        self.assertEqual(model.clock_text, "17:29")
        # 门不能因显示取整或浮点误差提前一毫秒开放。
        self.assertFalse(model.door_open)
        # 最后一毫秒使计时恰好到60秒。
        model.update(0.001)
        # 钟面和门状态在同一更新边界改变。
        self.assertEqual(model.clock_text, "17:30")
        # 下班时间已到，门口允许通行。
        self.assertTrue(model.door_open)
        # 到点只开门，站在房间中间还没有离开。
        self.assertFalse(model.escaped)
        # 开门后再经过一秒，钟面保持明确的下班时刻。
        for _ in range(20):
            # 不输入方向，继续验证时钟封顶而非自动成功。
            model.update(0.05)
        # 时钟不继续跳到另一个目标时间。
        self.assertEqual(model.clock_text, "17:30")

    # 不同帧率依赖相同的秒数边界，不能因累加误差多等一帧。
    def test_opening_time_matches_at_thirty_sixty_and_one_twenty_fps(self) -> None:
        # 三种真实帧率分别运行到同一秒数。
        for frames_per_second in (30, 60, 120):
            # 子案例记录发生问题的帧率。
            with self.subTest(fps=frames_per_second):
                # 慢速测试敌人不影响默认60秒下班时长。
                model = create_game(rules={**load_game_rules(), "slimeSpeed": 0.001}, play_intro=False)
                # 每一秒按指定帧率推进，不直接修改elapsed。
                for _ in range(60 * frames_per_second):
                    # 以帧率倒数作为真实模拟步长。
                    model.update(1 / frames_per_second)
                # 三种帧率均应恰好完成一分钟。
                self.assertAlmostEqual(model.elapsed, 60)
                # 门不因浮点累加残差延迟开放。
                self.assertTrue(model.door_open)
                # 时间展示与通行状态一致。
                self.assertEqual(model.clock_text, "17:30")

    # 开场、对白、暂停和被抓都不消耗这一局剩余的有效游戏秒数。
    def test_nonplaying_phases_freeze_shift_time(self) -> None:
        # 正常开场在原地等待时只呼吸，不推进下班钟。
        model = create_game()
        # 给开场足够多更新，避免只检查零时长帧。
        for _ in range(100):
            # 未输入方向，不触发走路结束。
            model.update(0.05)
        # 开场没有消耗任何上班有效秒数。
        self.assertEqual(model.elapsed, 0)
        # 重开跳过开场，以公开播放器接口启动一段真实对白。
        model.reset()
        # 对白状态由组件正常进入，不伪造active字段。
        model.dialogue.start("intro")
        # 对白更新应只打字。
        model.update(0.05, 1, 0)
        # 对白不计时，也不偷走起跑机会。
        self.assertEqual(model.elapsed, 0)
        # 对白结束后验证暂停冻结同一计时。
        model.dialogue.skip()
        # 暂停是模型正式公开输入状态。
        model.paused = True
        # 持续移动输入也不能在暂停中消耗时间。
        model.update(0.05, 1, 0)
        # 暂停中的钟仍保持开始时间。
        self.assertEqual(model.clock_text, "17:29")
        # 恢复后原地等待，实际触发一次被抓。
        model.paused = False
        # 默认敌人足以在这些帧内追上原地勇者。
        for _ in range(100):
            # 不注入失败标记，使用真实接触规则。
            model.update(0.05)
        # 确认失败实际发生。
        self.assertTrue(model.caught)
        # 保存失败时剩余秒数，而不是依赖某个实现内部时刻。
        remaining_seconds = model.remaining_shift_seconds
        # 跳过失败文字仍保持失败终态。
        model.dialogue.skip()
        # 再尝试移动和计时。
        model.update(0.05, 1, 0)
        # 失败之后门不会靠等待自行打开。
        self.assertEqual(model.remaining_shift_seconds, remaining_seconds)

    # 门槛可达，开门后沿正常方向移动进入，结果和计时随后冻结。
    def test_walking_into_open_exit_wins_and_reset_closes_it(self) -> None:
        # 缩短测试时间并减慢敌人，只隔离验证实际通行而不等待一分钟。
        rules = {**load_game_rules(), "gameSecondsPerMinute": 0.1, "slimeSpeed": 0.001}
        # 出生位置、移动边界和出口位置仍使用正式默认值。
        model = create_game(rules=rules, play_intro=False)
        # 正常向右走到门槛左方四像素，期间自然到达开门时刻。
        for _ in range(38):
            # 每帧向右移动八逻辑像素。
            model.update(0.05, 1, 0)
        # 调整高度到门口可达范围。
        for _ in range(8):
            # 向下正常移动到右下门前，没有直接重写角色坐标。
            model.update(0.05, 0, 1)
        # 尚未跨过门槛左边缘，不能提前成功。
        self.assertFalse(model.escaped)
        # 再向右跨过入口边缘，使用连续移动判定。
        model.update(0.05, 1, 0)
        # 勇者已经通过开放门槛下班。
        self.assertTrue(model.escaped)
        # 离开与被抓不能同时成立。
        self.assertFalse(model.caught)
        # 运动只推进到首次进入门槛，不能消耗完整帧后跑进室内更深处。
        self.assertAlmostEqual(model.hero.x, model.exit_bounds[0])
        # 记录成功后双方完整状态和时间，检查终态冻结。
        snapshot = (vars(model.hero).copy(), vars(model.slime).copy(), model.elapsed)
        # 通关后输入任何方向都不能继续追逐。
        model.update(0.05, -1, 1)
        # 成功之后位置、朝向、动画和时钟均保持不变。
        self.assertEqual(snapshot, (vars(model.hero), vars(model.slime), model.elapsed))
        # 新一局必须重新争取下班，不继承开放门和成功标记。
        model.reset()
        # 成功已清除。
        self.assertFalse(model.escaped)
        # 门重新关闭。
        self.assertFalse(model.door_open)
        # 钟面回到正式起点。
        self.assertEqual(model.clock_text, "17:29")

    # 闭门时站在门槛不能提前离开，到点仍站在这里才可以直接通过。
    def test_waiting_on_closed_threshold_escapes_exactly_when_it_opens(self) -> None:
        # 可达门槛内是合法测试出生点，起跑保护隔离史莱姆接触。
        rules = {**load_game_rules(), "heroSpawn": [530, 305], "gameSecondsPerMinute": 0.1}
        # 使用正式重试入口开始有效模拟。
        model = create_game(rules=rules, play_intro=False)
        # 一半时间里门仍关闭。
        model.update(0.05)
        # 接近或站在门口都不能替代时间条件。
        self.assertFalse(model.escaped)
        # 下一帧恰好开门，无须离开再重新踏入。
        model.update(0.05)
        # 到点站在入口即可下班。
        self.assertTrue(model.escaped)
        # 终局时间恰好截止开门瞬间。
        self.assertAlmostEqual(model.elapsed, 0.1)

    # 开门前已穿过又离开的轨迹不能被本帧末尾的开放状态追溯算成功。
    def test_crossing_before_opening_does_not_retroactively_escape(self) -> None:
        # 高速测试在一帧内从门槛左边穿到右边，并在更晚时刻开门。
        rules = {**load_game_rules(), "heroSpawn": [510, 186], "heroSpeed": 1000,
                 # 窄门槛使闭门穿越可以在合法活动区内完整发生。
                 "exitBounds": [520, 172, 530, 200], "gameSecondsPerMinute": 0.04}
        # 起跑保护内仅检查门的时间边界。
        model = create_game(rules=rules, play_intro=False)
        # 开门前0.02秒已穿过入口，到0.04秒开门时人已在外侧。
        model.update(0.05, 1, 0)
        # 本帧末门已开放。
        self.assertTrue(model.door_open)
        # 更早发生的闭门穿越仍不能通关。
        self.assertFalse(model.escaped)

    # 同一小段内按事件发生的真实先后，避免先被抓却逃脱或先进门却被抓。
    def test_capture_and_exit_use_first_event_order(self) -> None:
        # 敌人分别靠近门前、紧跟门后以及与入口同刻接触的位置。
        for slime_x, expected_escape in ((470, False), (450, True), (458, False)):
            # 标记几何布置以便定位先后判断错误。
            with self.subTest(slime_x=slime_x):
                # 先用起跑保护原地开门，之后再让双方开始真实移动。
                rules = {**load_game_rules(), "heroSpawn": [500, 305], "slimeSpawn": [slime_x, 305],
                         # 高速勇者一帧内可同时遇到门与接触范围。
                         "heroSpeed": 800, "slimeSpeed": 1600, "gameSecondsPerMinute": 0.05,
                         # 第一帧保护到开门，下一帧正常追逐。
                         "startDelaySeconds": 0.05}
                # 每个几何案例都使用独立游戏。
                model = create_game(rules=rules, play_intro=False)
                # 勇者原地等完保护期，门此刻打开而人尚未在门槛内。
                model.update(0.05)
                # 同帧移动会依次遇到敌人或门槛，最早事件决定结果。
                model.update(0.05, 1, 0)
                # 开放门槛先到则成功，否则被抓。
                self.assertEqual(model.escaped, expected_escape)
                # 两种终态互斥。
                self.assertEqual(model.caught, not expected_escape)

    # 正式速度和地图下的完整逃脱路线，防止只在减速敌人的夹具中能通关。
    def test_default_game_can_be_completed_by_walking_around_room(self) -> None:
        # 使用全部正式默认规则，不注入时间、速度或出生坐标。
        model = create_game(play_intro=False)
        # 先左后下拉开距离，之后沿可达边界反复转弯。
        directions = ((-1, 0), (0, 1), (1, 0), (0, -1))
        # 初始方向从左墙开始。
        direction_index = 0
        # 新出口在右下角，预留70秒包含到点后的半圈路线，通关后立即停止。
        for _ in range(70 * 60):
            # 每帧方向来自当前路线，而不是直接重写位置。
            dx, dy = directions[direction_index]
            # 正式60FPS步长同时推进追逐与钟面。
            model.update(1 / 60, dx, dy)
            # 终态结束回放，避免继续覆盖失败证据。
            if model.caught or model.escaped:
                # 跳出后统一断言真正结果。
                break
            # 到墙边转向，左右上下使用模型公开的活动边界。
            at_wall = ((dx < 0 and model.hero.x <= model.bounds[0])
                       # 纵向正值到达底边。
                       or (dy > 0 and model.hero.y >= model.bounds[3])
                       # 横向正值到达右边。
                       or (dx > 0 and model.hero.x >= model.bounds[2])
                       # 纵向负值到达顶边。
                       or (dy < 0 and model.hero.y <= model.bounds[1]))
            # 转向只在实际抵达边界后发生。
            if at_wall:
                # 四个方向循环，持续避开史莱姆。
                direction_index = (direction_index + 1) % len(directions)
        # 默认规则必须真实可通关。
        self.assertTrue(model.escaped)
        # 成功路线没有穿过史莱姆碰撞体。
        self.assertFalse(model.caught)
        # 右下原门在到点后下一次经过时进入，不能在右上旧位置成功。
        self.assertAlmostEqual(model.elapsed, 66 + 2 / 3)
        # 钟面、门和剩余时间一致。
        self.assertEqual((model.clock_text, model.door_open, model.remaining_shift_seconds), ("17:30", True, 0))

    # 首次开场会重新选择敌人落点，完整默认流程也必须能走到下班成功。
    def test_first_opening_can_be_completed_with_default_rules(self) -> None:
        # 首次启动保留正式开场、速度、边界和所有计时参数。
        model = create_game()
        # 走路和登场共用正式更新，不手工改写开场阶段。
        for _ in range(100):
            # 开场结束后即可进入对白确认阶段。
            if not model.opening_active:
                # 不让后面的更新提前消费追逐时间。
                break
            # 向右走够180像素后，演出组件自行冻结输入并完成跳跃。
            model.update(0.05, 1, 0)
        # 正式开场必须确实触发并结束。
        self.assertFalse(model.opening_active)
        # 落地结束后出现正式对白，不能跳过开场本身来验证。
        self.assertTrue(model.dialogue.active)
        # 使用公开跳过操作结束对白，方向输入由随后真实更新提供。
        model.dialogue.skip()
        # 先向上拉开与右侧敌人的距离，再沿四壁循环移动。
        directions = ((0, -1), (-1, 0), (0, 1), (1, 0))
        # 第一段向上，之后每次到达墙边才转向。
        direction_index = 0
        # 给到点后走至门口留出五秒，不能只验证门已开而未通关。
        for _ in range(65 * 60):
            # 获取玩家当前持续按住的方向。
            dx, dy = directions[direction_index]
            # 正常逐帧运动同时执行真实追逐、接触和出口规则。
            model.update(1 / 60, dx, dy)
            # 任意终态结束路线，后面判断究竟成功还是失败。
            if model.caught or model.escaped:
                # 保留首次结果作为证据。
                break
            # 以真实脚底位置判断当前路段是否已经到墙边。
            at_wall = ((dy < 0 and model.hero.y <= model.bounds[1])
                       # 左边界触发第二个拐弯。
                       or (dx < 0 and model.hero.x <= model.bounds[0])
                       # 下边界触发第三个拐弯。
                       or (dy > 0 and model.hero.y >= model.bounds[3])
                       # 右边界触发第四个拐弯。
                       or (dx > 0 and model.hero.x >= model.bounds[2]))
            # 不在途中突然换方向或改写角色坐标。
            if at_wall:
                # 持续沿上、左、下、右循环，等待下班门开放。
                direction_index = (direction_index + 1) % len(directions)
        # 从首次启动到下班成功的整个默认流程必须成立。
        self.assertTrue(model.escaped)
        # 到点之前没有被抓。
        self.assertFalse(model.caught)
        # 实际进入入口才结束，不要求到点瞬间自动传送。
        self.assertGreaterEqual(model.elapsed, 60)
        # 钟面封顶且门的状态一致。
        self.assertEqual((model.clock_text, model.door_open), ("17:30", True))

    # 钟面按分钟进位并跨午夜，结束时仍与门状态使用同一时间来源。
    def test_clock_rolls_over_midnight(self) -> None:
        # 缩短一分钟的测试时长，覆盖23:59到00:01两分钟。
        rules = {**load_game_rules(), "clockText": "23:59", "shiftEndText": "00:01", "gameSecondsPerMinute": 0.05}
        # 起跑保护内可完整验证两次钟面进位。
        model = create_game(rules=rules, play_intro=False)
        # 经过第一个游戏分钟。
        model.update(0.05)
        # 午夜正确进位，不显示24:00。
        self.assertEqual(model.clock_text, "00:00")
        # 尚未达到下班时间，门保持关闭。
        self.assertFalse(model.door_open)
        # 第二个游戏分钟达到结束时刻。
        model.update(0.05)
        # 钟面与目标时间一致。
        self.assertEqual(model.clock_text, "00:01")
        # 下班条件同时成立。
        self.assertTrue(model.door_open)

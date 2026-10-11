"""真实技能、追击与输入边界回归，不读取本机角色素材。"""

# 复制完整角色快照，用于验证暂停和结果冻结。
from copy import copy
# 数学函数独立计算方向距离和追赶距离。
import math
# 简单视图只供应输入层需要的语言字段。
from types import SimpleNamespace
# 标准测试框架负责行为断言。
import unittest

# 使用真实键盘事件，验证E的按下与松开。
import pygame

# 正式控制器负责输入边沿与模型请求。
from hero_game.app.input_controller import InputController
# 应用工厂注入正式规则与对白。
from hero_game.app.game_factory import create_game
# 规则读取允许测试独立指定双方起点。
from hero_game.config import load_game_rules
# 真实模型类型明确测试辅助函数的输入与返回契约。
from hero_game.model.game import Game
# 绘制器用于检查重复绘图不会消耗喘息时间。
from hero_game.rendering.renderer import Renderer


# 每项测试通过公开接口检验完整技能用例。
class DashChecks(unittest.TestCase):
    # 构造水平追逐，起点留出足够距离，不被默认出生方向干扰。
    def make_game(self, **changes: object) -> Game:
        # 每局都读取新的规则字典，避免测试污染正式默认值。
        rules = load_game_rules()
        # 勇者在前、史莱姆在后，敌人立即开始追击。
        rules.update(heroSpawn=[240, 240], slimeSpawn=[100, 240], startDelaySeconds=0)
        # 少数边界用例可显式覆盖起点或技能参数。
        rules.update(changes)
        # 工厂仍注入正式对白，测试不另写正文。
        return create_game(rules=rules, play_intro=False)

    # 分帧推进指定有效秒数，最后不足一帧也真正消费。
    def advance(self, model: Game, seconds: float, direction: tuple[int, int] = (1, 0), fps: int = 60) -> None:
        # 完整帧采用同一方向输入。
        count = int(seconds * fps + 1e-8)
        # 游戏每帧正常处理世界与技能。
        for _ in range(count):
            # 秒数来自指定帧率而非帧计数假定。
            model.update(1 / fps, *direction)
        # 不整除的时间补最后一个短帧。
        remainder = seconds - count / fps
        # 忽略仅由浮点造成的尾差。
        if remainder > 1e-9:
            # 保证所有用例确实模拟相同秒数。
            model.update(remainder, *direction)

    # 闪身拉开距离，随后原地喘两下期间敌人追回，恢复后继续按住方向跑。
    def test_dash_recovery_pursuit_and_resume_across_frame_rates(self) -> None:
        # 三种帧率均应产生相同的位置与阶段边界。
        for fps in (30, 60, 120):
            # 每种帧率独立检查，失败报告保留实际帧率。
            with self.subTest(fps=fps):
                # 创建相同起点的真实追逐。
                model = self.make_game()
                # E对应请求必须确实启动技能。
                self.assertTrue(model.request_dash(1, 0))
                # 闪身中尝试换方向，运动仍沿最初锁定方向。
                self.advance(model, 0.2, (-1, 0), fps)
                # 完整闪身恰好走128像素，输入不能中途反向。
                self.assertAlmostEqual(model.hero.x, 368)
                # 闪身结束后立即进入恢复且停止行走帧。
                self.assertEqual((model.dash_phase, model.hero.moving), ("recovering", False))
                # 保存喘息起点与敌人位置。
                hero_before, slime_before = copy(model.hero), copy(model.slime)
                # 持续按方向，但恢复期间勇者仍不能移动。
                self.advance(model, 0.4, (1, 0), fps)
                # 原地恢复时脚底保持稳定。
                self.assertEqual((model.hero.x, model.hero.y), (hero_before.x, hero_before.y))
                # 敌人按120像素每秒在0.4秒恢复里追回48像素，没有跟着定格。
                self.assertAlmostEqual(model.slime.x - slime_before.x, 48)
                # 喘完恢复技能可用，闪身0.2秒加恢复0.4秒。
                self.assertEqual(model.dash_phase, "ready")
                # 世界计时没有漏掉恢复时长。
                self.assertAlmostEqual(model.elapsed, 0.6)
                # 下一帧的持续方向输入直接恢复跑步。
                model.update(1 / fps, 1, 0)
                # 不要求玩家重新按方向键才能移动。
                self.assertGreater(model.hero.x, hero_before.x)

    # 单帧跨过恢复结束边界时，只把剩余的部分用于普通跑步。
    def test_phase_boundary_consumes_remainder(self) -> None:
        # 非整帧时长故意让两个边界落在帧内。
        model = self.make_game(dashSeconds=0.17, dashRecoverySeconds=0.73, startDelaySeconds=10)
        # 触发水平技能。
        model.request_dash(1, 0)
        # 19个0.05秒帧覆盖0.9秒技能和0.05秒普通跑步。
        for _ in range(19):
            # 世界更新负责分段，测试不自己调用技能内部方法。
            model.update(0.05, 1, 0)
        # 技能128像素加上普通移动8像素，不能丢掉帧内余时。
        self.assertAlmostEqual(model.hero.x, 240 + 128 + 8)
        # 完整动作后恢复可触发。
        self.assertEqual(model.dash_phase, "ready")

    # 没有方向键时沿朝向闪身，斜向输入的总距离不会加速。
    def test_facing_diagonal_and_wall(self) -> None:
        # 朝左时没有方向输入也能触发。
        model = self.make_game(startDelaySeconds=10)
        # 朝向属于正式Actor状态。
        model.hero.direction = "left"
        # 无方向请求使用当前朝向。
        model.request_dash()
        # 不按方向也完成闪身。
        self.advance(model, 0.2, (0, 0))
        # 水平距离与正式技能规则相同。
        self.assertAlmostEqual(model.hero.x, 112)
        # 对角线起点远离墙面，允许完整128像素距离。
        model = self.make_game(heroSpawn=[280, 280], startDelaySeconds=10)
        # 向右上闪身避免纵向夹紧。
        model.request_dash(1, -1)
        # 更新方向不会改变技能锁定向量。
        self.advance(model, 0.2, (0, 0))
        # 使用独立欧氏距离判断斜向没有倍速。
        self.assertAlmostEqual(math.hypot(model.hero.x - 280, model.hero.y - 280), 128)
        # 靠右墙起点只能走到正式边界。
        model = self.make_game(heroSpawn=[540, 240], startDelaySeconds=10)
        # 贴墙也允许技能进入恢复，不穿墙也不取消代价。
        model.request_dash(1, 0)
        # 完成闪身时长。
        self.advance(model, 0.2)
        # 不扩大活动范围或改变正式出口。
        self.assertEqual(model.hero.x, 548)
        # 撞墙仍正常进入喘息阶段。
        self.assertEqual(model.dash_phase, "recovering")

    # 闪身路径仍有接触判定，喘息时也可能被追上。
    def test_capture_during_dash_and_recovery(self) -> None:
        # 敌人在前方，闪身不能穿越它获得无敌。
        model = self.make_game(slimeSpawn=[290, 240])
        # 向敌人所在位置闪身。
        model.request_dash(1, 0)
        # 足够推进到首次接触，而非只比较最后两端。
        self.advance(model, 0.2)
        # 高速穿越路径触发失败。
        self.assertTrue(model.caught)
        # 结算位置位于敌人之前，未把角色提交到完整闪身终点。
        self.assertLess(model.hero.x, 290)
        # 贴墙闪身让勇者无法拉开距离，敌人在0.4秒恢复内追上。
        model = self.make_game(heroSpawn=[540, 240], slimeSpawn=[462, 240])
        # 右向技能首先撞墙。
        model.request_dash(1, 0)
        # 完成闪身阶段时还未接触。
        self.advance(model, 0.2)
        # 用例必须确实先进入喘息，不能在闪身时已经失败。
        self.assertFalse(model.caught)
        # 敌人继续追击，按住方向无法提前取消恢复。
        self.advance(model, 0.4)
        # 真实接触导致失败，喘息没有隐藏无敌。
        self.assertTrue(model.caught)
        # 终态不能继续消费恢复秒数。
        before = (model.elapsed, model.dash_recovery_progress)
        # 后续更新被失败状态阻止。
        model.update(0.05, 1, 0)
        # 结果冻结包含技能进度。
        self.assertEqual(before, (model.elapsed, model.dash_recovery_progress))

    # 撞墙改变速度后，接触时刻须由分段轨迹得出。
    def test_wall_changes_speed_before_capture(self) -> None:
        # 用快速敌人放大同一帧内撞墙前后的速度变化，不能以夹紧终点匀速插值。
        model = self.make_game(heroSpawn=[540, 240], slimeSpawn=[515, 240], slimeSpeed=800)
        # 技能先在0.0125秒到墙，敌人随后在0.01375秒追到接触半径。
        model.request_dash(1, 0)
        # 整帧足以跨过两个事件，模型必须拆分后再确定先后。
        model.update(0.05)
        # 真正触发接触，而不是贴墙后免于追击。
        self.assertTrue(model.caught)
        # 勇者停在墙面，敌人到达半径22像素的接触位置。
        self.assertEqual((model.hero.x, model.slime.x), (548, 526))
        # 只消费实际接触时刻，不提交整个0.05秒。
        self.assertAlmostEqual(model.elapsed, 0.01375)

    # 暂停冻结技能与敌人，重开清空动作，开场与对白不能触发。
    def test_pause_reset_and_blocked_requests(self) -> None:
        # 创建正式追逐并进入恢复中途。
        model = self.make_game()
        # 启动技能。
        model.request_dash(1, 0)
        # 累计0.4秒，处于第一轮喘息之后。
        self.advance(model, 0.4)
        # 快照同时包含技能、角色和时钟。
        before = (copy(model.hero), copy(model.slime), model.elapsed, model.dash_recovery_progress)
        # 暂停不能消耗敌人或恢复时间。
        model.paused = True
        # 暂停期间既更新也尝试E。
        model.update(0.05, 1, 0)
        # 请求被明确拒绝。
        self.assertFalse(model.request_dash(1, 0))
        # 比较完整暂停快照。
        self.assertEqual(before, (model.hero, model.slime, model.elapsed, model.dash_recovery_progress))
        # 重开创建新技能，恢复普通操作。
        model.reset()
        # 新局技能没有旧进度。
        self.assertEqual((model.dash_phase, model.dash_recovery_progress), ("ready", 0))
        # 正式对白激活后不能闪身跳过它。
        model.dialogue.start("intro")
        # 对话请求不修改角色或技能。
        self.assertFalse(model.request_dash(1, 0))
        # 首次开场也遵循同一阻塞边界。
        model.reset(play_intro=True)
        # 开场走路不具有正式追逐技能。
        self.assertFalse(model.request_dash(1, 0))
        # 非法数值不能因开场冻结被掩盖。
        with self.assertRaises(ValueError):
            # NaN请求必须被接口拒绝。
            model.request_dash(float("nan"), 0)

    # 真实E键长按不连发；恢复后松开再按才启动下一轮。
    def test_e_key_edges(self) -> None:
        # 留出足够空间，长按测试不受敌人抓住影响。
        model = self.make_game(startDelaySeconds=10)
        # 输入只需要字体语言字段，不启动窗口。
        controller = InputController(model, SimpleNamespace(font_path=None), 1)
        # 同一批事件先按右，再按E。
        controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d),
                                  # E沿刚刚建立的右向输入启动。
                                  pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)])
        # 技能请求确实到达正式模型。
        self.assertEqual(model.dash_phase, "dashing")
        # 完成技能，不松E。
        self.advance(model, 1)
        # 系统连发或重复KEYDOWN都不应该启动第二轮。
        controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)])
        # 保持可用状态，证明没有误触发新一轮。
        self.assertEqual(model.dash_phase, "ready")
        # 松开后再按才形成合法新边沿。
        controller.handle_events([pygame.event.Event(pygame.KEYUP, key=pygame.K_e),
                                  # 新按下事件不带系统repeat标记。
                                  pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)])
        # 可以再次使用技能。
        self.assertEqual(model.dash_phase, "dashing")

    # 门开放时连续闪身也能正常离开，闭门时不能提前成功。
    def test_focus_loss_does_not_leave_e_stuck(self) -> None:
        # 保留足够起跑时间，让输入焦点测试不会被敌人抓住。
        model = self.make_game(startDelaySeconds=10)
        # 正式输入控制器拥有物理E按下状态。
        controller = InputController(model, SimpleNamespace(font_path=None), 1)
        # 首次E触发，之后假定松键发生在另一个窗口里。
        controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)])
        # 技能已经结束，但没有收到配对KEYUP。
        self.advance(model, 1)
        # 失焦必须清理物理按键状态，同时冻结游戏。
        controller.handle_events([pygame.event.Event(pygame.WINDOWFOCUSLOST)])
        # 空格恢复正式游戏。
        controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)])
        # 回来后第一次真正按E就应有效。
        controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)])
        # 不需要先空按一次才解除旧按下标记。
        self.assertEqual(model.dash_phase, "dashing")

    # 门开放时连续闪身也能正常离开，闭门时不能提前成功。
    def test_dash_preserves_door_timing(self) -> None:
        # 从门左侧水平进入门槛，敌人等待以独立验证出口。
        for is_open in (False, True):
            # 两种门状态分别构建独立游戏。
            model = self.make_game(heroSpawn=[490, 305], startDelaySeconds=10)
            # 只用公开计时状态控制当前有效游戏时间。
            model.elapsed = 60 if is_open else 0
            # 闪身直接朝向门槛。
            model.request_dash(1, 0)
            # 处理一次足够跨门槛的高速移动。
            model.update(0.05)
            # 出口仍由正式门时钟决定。
            self.assertEqual(model.escaped, is_open)
            # 成功以后不能请求新技能取消结局。
            if is_open:
                # 胜利状态技能请求被拒绝。
                self.assertFalse(model.request_dash(1, 0))

    # 两次明显起伏的渲染不同于待机，重复绘制不推进任何世界状态。
    def test_breath_rendering_is_read_only_and_has_two_cycles(self) -> None:
        # 字体系统只用于内存绘制，不创建显示或音频设备。
        pygame.font.init()
        # 独立测试技能不受追击干扰。
        model = self.make_game(startDelaySeconds=10)
        # 正式基础资源也能表现技能，不依赖私有美术。
        renderer = Renderer(model)
        # 启动闪身并推进至恢复起点。
        model.request_dash(1, 0)
        # 精确进入喘息阶段。
        self.advance(model, 0.2)
        # 恢复起点与每轮中间位置采样。
        frames = []
        # 四个0.1秒间隔对应起点、第一次峰值、谷底、第二次峰值。
        for _ in range(4):
            # 保存绘制前模型事实，重复绘制必须完全只读。
            before = (copy(model.hero), model.elapsed, model.dash_recovery_progress)
            # 真正绘制办公室与角色。
            renderer.draw()
            # 只比较勇者所在小区域，排除时钟变化。
            frames.append(pygame.image.tobytes(renderer.surface.subsurface((330, 175, 70, 70)), "RGBA"))
            # 同一个时刻再次绘制。
            renderer.draw()
            # 绘图不能推进喘息或运动。
            self.assertEqual(before, (model.hero, model.elapsed, model.dash_recovery_progress))
            # 前进至下一采样时刻。
            self.advance(model, 0.1)
        # 起点与中间谷底是同一姿态。
        self.assertEqual(frames[0], frames[2])
        # 两次峰值是同一喘息姿态，确实重复两次。
        self.assertEqual(frames[1], frames[3])
        # 峰值明显改变画面，不能只是冻结待机帧。
        self.assertNotEqual(frames[0], frames[1])

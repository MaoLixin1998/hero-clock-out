"""用受控真实事件验证输入切换边界，不启动窗口或读取私人美术。"""

# 简单命名空间提供点击区域与语言，不需要建立实际绘制资源。
from types import SimpleNamespace
# 标准测试框架核对真实控制器产生的模型行为。
import unittest

# 使用真实事件和按键常量，避免测试另造一套输入协议。
import pygame

# 输入控制器是本组受测对象。
from hero_game.app.input_controller import InputController
# 应用工厂读取正式数据后组装真实暂停、对话与运动模型。
from hero_game.app.game_factory import create_game
# 正式规则可按公开配置注入短时长，让通关输入回归快速跨过真实开门边界。
from hero_game.config import load_game_rules


# 每项验证跨输入与模型的边界行为，台词来自包内正式配置而非测试硬编码。
class InputControllerChecks(unittest.TestCase):
    # 建立足够处理点击的受控界面视图，整个测试不创建窗口。
    def setUp(self) -> None:
        # 跳过正式开场，让多数测试直接关注追逐和输入切换。
        self.model = create_game(play_intro=False)
        # 只提供控制器实际查询的矩形和字体语言字段。
        self.view = SimpleNamespace(
            # 对话框使用独立逻辑区域，鼠标显示坐标随后按二倍缩放。
            dialogue_rect=pygame.Rect(154, 244, 476, 108),
            # 跳过按钮与正文区域相互分离。
            skip_rect=pygame.Rect(546, 12, 82, 25),
            # 无中文字体时控制器应按英文全文长度确认。
            font_path=None,
        )
        # 同一模型和视图交给真实控制器，缩放采用合法二倍。
        self.controller = InputController(self.model, self.view, scale=2)

    # 失焦清空旧键并暂停，恢复当帧冻结且必须重新按键才移动。
    def test_focus_pause_drops_held_key_and_resume_does_not_drift(self) -> None:
        # 先按右键，使控制器持有一个实际方向。
        self.controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)])
        # 查询确认右向输入确实已建立，后续不是对空集合做无效检查。
        self.assertEqual(self.controller.direction(), (1, 0))
        # 真实失焦事件必须暂停世界并要求本帧冻结。
        is_running, freeze_frame = self.controller.handle_events([pygame.event.Event(pygame.WINDOWFOCUSLOST)])
        # 失焦不是退出事件，应用还应继续显示。
        self.assertTrue(is_running)
        # 切焦当帧必须保持原位置。
        self.assertTrue(freeze_frame)
        # 模型进入暂停且旧方向完全清除。
        self.assertTrue(self.model.paused)
        # 清空持续输入可防止回到窗口后自动漂移。
        self.assertEqual(self.controller.direction(), (0, 0))
        # 空格恢复，但切换当帧仍然不推进。
        _, freeze_frame = self.controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)])
        # 暂停确实解除，后续可继续游戏。
        self.assertFalse(self.model.paused)
        # 恢复当帧不补走后台经过的时间。
        self.assertTrue(freeze_frame)
        # 保存实际坐标检查没有残留方向。
        before = (self.model.hero.x, self.model.hero.y)
        # 下一帧正常推进但没有新方向键。
        self.model.update(0.025, *self.controller.direction())
        # 角色没有继承旧按键移动。
        self.assertEqual((self.model.hero.x, self.model.hero.y), before)
        # 重新按D之后，下一帧才允许真实移动。
        self.controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)])
        # 使用正常模型更新，不由测试修改坐标模拟移动。
        self.model.update(0.025, *self.controller.direction())
        # 正常速度每秒160像素，0.025秒恰好移动4像素。
        self.assertAlmostEqual(self.model.hero.x - before[0], 4)

    # 对话点击按窗口缩放换算，第一次补全而不是直接吞掉当前句。
    def test_scaled_click_reveals_and_next_click_advances(self) -> None:
        # 明确启动正式场景，当前句尚未出现文字。
        self.model.dialogue.start("intro")
        # 选择对话框内的逻辑点，再按二倍换成窗口像素。
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(400, 560))
        # 第一次点击真实进入控制器的命中流程。
        _, freeze_frame = self.controller.handle_events([event])
        # 确认当帧应冻结，避免点击结束台词后立即位移。
        self.assertTrue(freeze_frame)
        # 初次确认仍在第一句，没有直接跳过正文。
        self.assertEqual(self.model.dialogue.index, 0)
        # 控制器按当前语言补全英文，字数可能与中文不同。
        self.assertEqual(self.model.dialogue.visible_text(True), self.model.dialogue.text(True))
        # 第二次点击才应进入下一句。
        self.controller.handle_events([event])
        # 正文索引实际前进，不只是显示时间发生变化。
        self.assertEqual(self.model.dialogue.index, 1)
        # 下一句从空文字开始重新逐字显示。
        self.assertEqual(self.model.dialogue.visible_text(True), "")

    # 跳过失败对白不解除失败，只有明确R重开才恢复新局。
    def test_skipping_capture_text_does_not_revive_until_restart(self) -> None:
        # 玩家原地等待，让正式追击逻辑自然触发接触。
        for _ in range(100):
            # 不直接伪造 caught 标志，确保输入面对真实结果状态。
            self.model.update(0.05)
        # 测试前提是实际被抓，排除空对白的假通过。
        self.assertTrue(self.model.caught)
        # 失败也是终态，失焦不能把结果盖成普通暂停。
        self.controller.handle_events([pygame.event.Event(pygame.WINDOWFOCUSLOST)])
        # 结果冻结由caught承担，失焦不额外建立暂停状态。
        self.assertFalse(self.model.paused)
        # 失败后没有有效持续移动输入。
        self.assertEqual(self.controller.direction(), (0, 0))
        # 按Tab跳过正在显示的结果对白。
        self.controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB)])
        # 文字已经结束，玩家无需继续翻页。
        self.assertFalse(self.model.dialogue.active)
        # 结果状态仍保留，跳过正文不等于复活。
        self.assertTrue(self.model.caught)
        # 明确按R重开，状态切换当帧必须冻结。
        _, freeze_frame = self.controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)])
        # 重开动作已经解除旧结果。
        self.assertFalse(self.model.caught)
        # 出生当帧不因旧按键或旧时间立刻移动。
        self.assertTrue(freeze_frame)
        # 重试回到正式出生点，并默认跳过首次开场。
        self.assertEqual((self.model.hero.x, self.model.hero.y), tuple(self.model.rules["heroSpawn"]))
        # 重试从正常追逐开始，不要求重新完成开场路径。
        self.assertFalse(self.model.opening_active)

    # 真正进入已开放门槛后，移动、暂停和失焦不解除成功，R重开与Q退出均有效。
    def test_success_keeps_terminal_state_until_restart_or_quit(self) -> None:
        # 正式规则注入仅缩短测试等待，不直接修改结果字段。
        rules = load_game_rules()
        # 以0.1秒完成一个正常游戏分钟，第二帧恰好开门。
        rules["gameSecondsPerMinute"] = 0.1
        # 门槛左侧出生，持续向右会通过正常移动进入区域。
        rules["heroSpawn"] = [516, 305]
        # 较长起跑保护排除本项无关的接触结果。
        rules["startDelaySeconds"] = 2
        # 使用真实模型公开接口执行开门与通关。
        model = create_game(rules=rules, play_intro=False)
        # 控制器仍使用正常点击区域与语言视图。
        controller = InputController(model, self.view, scale=2)
        # 勇者按D向门槛前进，而不是由测试直接写坐标。
        controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)])
        # 闭门时第一帧走入门槛，仍然不能通关。
        model.update(0.05, *controller.direction())
        # 时间与门槛两个真实条件均成立前不显示成功。
        self.assertFalse(model.escaped)
        # 第二帧到点并在门槛内，模型自然产生成功。
        model.update(0.05, *controller.direction())
        # 测试确实面对实际成功状态，而不是一个手工布尔标志。
        self.assertTrue(model.escaped)
        # 控制器查询立即冻结旧D输入，不依赖下一次主循环清键。
        self.assertEqual(controller.direction(), (0, 0))
        # 保存真实终态的坐标与有效时间。
        before = (model.hero.x, model.hero.y, model.elapsed)
        # 成功时失焦、恢复键和方向输入均只会维持结果。
        _, freeze_frame = controller.handle_events([
            # 失焦仍需要清除旧键，但不能建立普通暂停。
            pygame.event.Event(pygame.WINDOWFOCUSLOST),
            # 空格在成功面板中不能恢复移动或切换暂停。
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),
            # Esc同样不能把成功面板变成暂停。
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE),
            # 新方向键也必须被终态丢弃。
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a),
        ])
        # 状态处理当帧应保持冻结。
        self.assertTrue(freeze_frame)
        # 失焦与暂停键不改变正式成功结果。
        self.assertTrue(model.escaped)
        # 结果状态始终优先，不能遗留一个普通暂停标志。
        self.assertFalse(model.paused)
        # 正常模型更新也继续保持终态，无位置或计时漂移。
        model.update(0.05, *controller.direction())
        # 动作和时钟均停在成功瞬间。
        self.assertEqual((model.hero.x, model.hero.y, model.elapsed), before)
        # Q仍能在成功结果中直接请求退出窗口循环。
        is_running, freeze_frame = controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q)])
        # 退出事件不被终态吞掉。
        self.assertFalse(is_running)
        # 退出同时要求本帧不再推进世界。
        self.assertTrue(freeze_frame)
        # R明确重开同一个真实模型。
        _, freeze_frame = controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)])
        # 重开恢复新的正常一局，结果字段回到默认状态。
        self.assertFalse(model.escaped)
        # 新生时间归零且门重新关闭。
        self.assertEqual(model.elapsed, 0)
        # 已结束的一局不能把开放状态带入下一局。
        self.assertFalse(model.door_open)
        # 状态切换当帧不能沿用旧方向。
        self.assertTrue(freeze_frame)
        # 重新开始后仍需重新按方向键。
        self.assertEqual(controller.direction(), (0, 0))

    # 开场从行走进入登场后清掉旧方向，结束对白也不能沿旧键自动继续走。
    def test_entrance_and_dialogue_require_fresh_movement_input(self) -> None:
        # 本项使用完整正式开场而不是直接追逐。
        model = create_game()
        # 视图仍只提供受控区域与语言，无须真实渲染器。
        controller = InputController(model, self.view, scale=2)
        # 按下D并保持，模拟玩家走到触发距离。
        controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)])
        # 二十三帧足以从行走切换到跳出阶段。
        for _ in range(23):
            # 按真实应用顺序先更新模型，再清理阻塞阶段的输入。
            model.update(0.05, *controller.direction())
            # 控制器不能在跳跃期间保留旧方向键。
            controller.clear_blocked_input()
        # 确认已自然进入登场，测试没有直接设置阶段字符串。
        self.assertEqual(model.intro_phase, "entrance")
        # 持续输入已被消耗，跳出后必须重新按方向。
        self.assertEqual(controller.direction(), (0, 0))
        # 再推进足够时间，正式对白应开始。
        for _ in range(18):
            # 无方向输入不影响世界位置，只推进演出。
            model.update(0.05, *controller.direction())
            # 对话同样隔离旧方向输入。
            controller.clear_blocked_input()
        # 当前确实进入正式对白，不是还停在动画中。
        self.assertTrue(model.dialogue.active)
        # Tab结束对白，仍需等待新按键。
        controller.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB)])
        # 保存勇者当前位置检查下一帧没有自动续走。
        before = (model.hero.x, model.hero.y)
        # 恢复追逐后的正常帧仍不带旧方向。
        model.update(0.05, *controller.direction())
        # 开场方向没有泄漏到追逐阶段。
        self.assertEqual((model.hero.x, model.hero.y), before)

    # 缩放是坐标换算的输入边界，零、负数、小数和布尔值均不能接受。
    def test_invalid_scale_is_rejected_before_mouse_events(self) -> None:
        # 每个输入都能独立引出清楚的构造错误。
        for scale in (0, -1, 1.5, True):
            # 标记具体错误值，便于定位失败边界。
            with self.subTest(scale=scale):
                # 无效缩放在构造时拒绝，不能等到鼠标点击除零才暴露。
                with self.assertRaises(ValueError):
                    # 使用真实控制器验证公开接口，不在测试里重复校验逻辑。
                    InputController(self.model, self.view, scale=scale)

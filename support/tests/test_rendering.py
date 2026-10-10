"""在虚拟显示中验证默认游戏绘制与状态边界。"""

# 虚拟显示驱动让受控绘图检查不占用真实桌面。
import os
# 标准测试框架提供绘图断言与生命周期回调。
import unittest
# 记录正式绘制器的文字调用，核对真实状态选择的中英提示。
from unittest.mock import patch

# pygame 执行真实画布绘制，而不是测试中另画参考场景。
import pygame

# 固定逻辑画布由包内配置模块定义。
from hero_game.config import LOGICAL_SIZE, load_game_presentation, load_game_rules
# 应用工厂显式组装默认游戏，模型只提供绘制状态。
from hero_game.app.game_factory import create_game
# 默认绘制器使用可随仓库分发的程序资源。
from hero_game.rendering.renderer import Renderer
# 技术占位资源用于验证结局底图注入，不依赖本机美术。
from hero_game.rendering.generated_resources import create_generated_resources
# 绘制器初始化边界拒绝错误画布。
from hero_game.rendering.ending_renderer import EndingRenderer


# 渲染回归使用仓库默认资源，并在每例后显式释放pygame模块。
class RenderingChecks(unittest.TestCase):
    # 可选底图实际进入正式胜利画面，缓存与外部可变画布互相隔离。
    def test_injected_ending_background_is_used_without_mutating_resources(self) -> None:
        # 真实出口判定负责启动结局，测试不直接写入成功状态。
        rules = load_game_rules()
        # 出生点位于开门范围内，便于受控触发正常胜利。
        rules["heroSpawn"] = [530, 305]
        # 只缩短时间比例，门、角色与结局机制均用正式逻辑。
        rules["gameSecondsPerMinute"] = 0.1
        # 防止敌人接触先于本项的成功事件。
        rules["startDelaySeconds"] = 4
        # 从正式工厂组装模型。
        model = create_game(rules=rules, play_intro=False)
        # 占位画布替代可选外部图，颜色能明确识别绘制结果。
        resources = create_generated_resources()
        # 同一资源协议允许已解码的完整底图。
        resources.ending_background = pygame.Surface(LOGICAL_SIZE)
        # 纯色仅用于技术回归，不代表最终场景内容。
        resources.ending_background.fill((29, 61, 93))
        # 夜景端点与白天颜色可明确区分，验证实际渐变输入。
        resources.ending_night_background = pygame.Surface(LOGICAL_SIZE)
        # 不读取任何本机生成美术。
        resources.ending_night_background.fill((8, 16, 24))
        # 实际Renderer接收该资源，验证组装链而非只测试独立绘图器。
        renderer = Renderer(model, resources=resources)
        # 初始化后修改原始画布，不能污染绘制器持有的结局缓存。
        resources.ending_background.fill((200, 1, 2))
        # 夜景端点同样隔离调用者之后的修改。
        resources.ending_night_background.fill((201, 2, 3))
        # 足够的正式帧更新跨过开门与完整结局。
        for _ in range(200):
            # 输入保持中立，门槛内到点自动触发成功。
            model.update(0.05)
        # 测试确实到达完整门外状态。
        self.assertEqual(model.ending_phase, "complete")
        # 空白角落应来自传入底图，而不是默认场景。
        self.assertEqual(tuple(renderer.draw().get_at((639, 359)))[:3], (8, 16, 24))
        # 角色和文字叠画不能反向写入资源缓存。
        self.assertEqual(tuple(resources.ending_background.get_at((320, 240)))[:3], (200, 1, 2))
        # 叠画不能改变外部夜景缓存。
        self.assertEqual(tuple(resources.ending_night_background.get_at((320, 240)))[:3], (201, 2, 3))
        # 直接组合时同样拒绝错误尺寸或错误类型。
        for invalid in (pygame.Surface((1, 1)), "invalid"):
            # 错误不能被缩放后悄悄放行。
            with self.assertRaises(ValueError):
                # 初始化就报告边界错误。
                EndingRenderer(invalid)
            # 夜景参数也在同一构造边界拒绝错误输入。
            with self.assertRaises(ValueError):
                # 不能只验证第一张底图而漏掉夜景。
                EndingRenderer(night_background=invalid)

    # 每次画面检查前准备无桌面依赖的pygame显示环境。
    def setUp(self) -> None:
        # 强制使用虚拟显示，检查时不占用真实窗口。
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        # 初始化显示模块，图片转换需要当前显示格式。
        pygame.display.init()
        # 初始化字体模块，绘制器仍会加载正式游戏字体。
        pygame.font.init()
        # 建立逻辑尺寸窗口，让真实绘制器正常转换图片。
        pygame.display.set_mode(LOGICAL_SIZE)

    # 完成检查后释放模块，避免影响其他窗口或检查。
    def tearDown(self) -> None:
        # 清理虚拟显示与字体资源。
        pygame.quit()

    # 显式注入的文字也必须在构造阶段校验，不能拖到首次暂停才暴露缺字段。
    def test_injected_presentation_is_validated_before_first_draw(self) -> None:
        # 独立读取正式显示结构，测试不复制任何游戏或视频正文。
        supplied = load_game_presentation()
        # 缺少暂停标题会使较晚的状态绘制失败，必须提前拒绝。
        del supplied["pausedTitle"]
        # 构造本身应抛明确ValueError，无须先制造暂停或捕获。
        with self.assertRaisesRegex(ValueError, "Presentation"):
            # 调用真实绘制器构造，确认注入路径实际经过共享校验器。
            Renderer(create_game(), presentation=supplied)

    # 倒计时模板须在构造时拒绝未知变量、格式转换和损坏花括号。
    def test_countdown_templates_are_checked_before_rendering(self) -> None:
        # 每个错误模板都使用其余正式界面字段，避免因缺字段误判。
        for template in ("{unknown}", "{seconds!r}", "{seconds:02}", "{seconds", "no countdown"):
            # 分别报告格式错误的输入边界。
            with self.subTest(template=template):
                # 取得独立正式映射，只替换当前受测模板。
                presentation = load_game_presentation()
                # 中文字段也在无中文字体时检查，不能到切换设备才失败。
                presentation["doorCountdown"] = template
                # 真正构造绘制器，确认显式注入路径执行共享校验。
                with self.assertRaisesRegex(ValueError, "Presentation countdown"):
                    # 当前模型使用正常正式规则，不伪造渲染状态。
                    Renderer(create_game(), presentation=presentation)
        # 显式空模板保留原接口的合法空字符串语义。
        presentation = load_game_presentation()
        # 关闭倒计时文字时不要求额外的秒数变量。
        presentation["doorCountdown"] = ""
        # 真正构造成功才能证明空模板未被校验误拒绝。
        self.assertEqual(Renderer(create_game(), presentation=presentation).presentation["doorCountdown"], "")

    # 分钟钟面未变化时，真实有效游戏时间仍须每秒更新倒计时文字和像素。
    def test_chase_countdown_changes_before_clock_minute_changes(self) -> None:
        # 跳过开场后直接走正常计时路径，不由测试写入elapsed。
        model = create_game(play_intro=False)
        # 使用正式程序资源，验证实际游戏的绘制输出。
        renderer = Renderer(model)
        # 强制选择正式英文备用字段，测试不依赖宿主系统是否安装中文字体。
        renderer.font_path = None
        # 保存时钟下方提示区域，排除角色行走对画面比较的干扰。
        hint_area = (180, 70, 280, 18)
        # 标签调用和像素检查共同确认提示来自正式文字且确实画在场景中。
        with patch.object(renderer, "label", wraps=renderer.label) as labels:
            # 首帧必须已经告诉玩家需要等待多少秒。
            first = pygame.image.tobytes(renderer.draw().subsurface(hint_area), "RGB")
            # 按当前正式规则生成期望值，不在测试复制正文。
            expected = renderer.presentation["doorCountdownEnglish"].format(seconds=60)
            # 真实绘制调用包含完整秒数提示。
            self.assertIn(expected, [call.args[0] for call in labels.call_args_list])
        # 原地等待略超过一秒，不足以在默认游戏中被追上。
        for _ in range(21):
            # 有效游戏时间由模型每帧正常推进。
            model.update(0.05)
        # 数字钟仍在17:29，倒计时须让玩家看出时间已经推进。
        self.assertEqual(model.clock_text, "17:29")
        # 再检查实际文字与像素，不能只断言一个时长属性。
        with patch.object(renderer, "label", wraps=renderer.label) as labels:
            # 第二维画面必须从60秒变为59秒。
            second = pygame.image.tobytes(renderer.draw().subsurface(hint_area), "RGB")
            # 模板以真实剩余秒数对应的59秒绘制。
            expected = renderer.presentation["doorCountdownEnglish"].format(seconds=59)
            # 英文备用提示与真实计时一致。
            self.assertIn(expected, [call.args[0] for call in labels.call_args_list])
        # 可视变化证明玩家能看到秒数在走，而非只有内部计时改变。
        self.assertNotEqual(first, second)

    # 到点后动态门、可达门槛与操作说明同时改变，背景缓存不得被改写。
    def test_real_shift_completion_opens_door_without_mutating_background(self) -> None:
        # 缩短正式时间比例，仅加速测试，不直接伪造door_open。
        rules = load_game_rules()
        # 一个游戏分钟只耗0.1秒，精确跨过正常开门边界。
        rules["gameSecondsPerMinute"] = 0.1
        # 起跑保护足够覆盖本项时间，结果不会受敌人碰撞干扰。
        rules["startDelaySeconds"] = 2
        # 默认出生点不在门槛内，开门时应继续允许玩家行走。
        model = create_game(rules=rules, play_intro=False)
        # 同一绘制器先画关闭状态，再画真实开放状态。
        renderer = Renderer(model)
        # 保存原背景完整字节，动态门只允许画到目标surface。
        background = pygame.image.tobytes(renderer.background, "RGB")
        # 原门区域保持原尺寸和位置。
        door_area = (579, 243, 32, 70)
        # 保存闭门图像，之后必须有明显像素变化。
        closed = pygame.image.tobytes(renderer.draw().subsurface(door_area), "RGB")
        # 两次正常更新使游戏分钟刚好走完。
        model.update(0.05)
        # 到点前门仍按模型规则保持关闭。
        self.assertFalse(model.door_open)
        # 第二帧到点后真正解锁门。
        model.update(0.05)
        # 门开放和通关是独立状态，远处玩家不能自动胜利。
        self.assertTrue(model.door_open)
        # 玩家仍在出生点，结果必须等待进入门槛。
        self.assertFalse(model.escaped)
        # 正常时间更新完成0.8秒开门动作，不能仅靠逻辑开放断言门板已展开。
        for _ in range(16):
            # 起跑保护足够覆盖完整开门，玩家仍在远处。
            model.update(0.05)
        # 切换成英文备用文字，验证回退路径实际可用。
        renderer.font_path = None
        # 核对开门时绘制的正式指引，同时保留实际输出像素。
        with patch.object(renderer, "label", wraps=renderer.label) as labels:
            # 开门后的图像来自同一正常绘制路径。
            opened = pygame.image.tobytes(renderer.draw().subsurface(door_area), "RGB")
            # 操作说明必须使用正式配置中的开放提示。
            self.assertIn(renderer.presentation["doorOpenInstructionEnglish"],
                          # 从所有实际标签调用中找出该提示，不另造参考文字。
                          [call.args[0] for call in labels.call_args_list])
        # 门从完整棕色门面变成开放通道，玩家可以直接辨认。
        self.assertNotEqual(closed, opened)
        # 门前判定区域和原门之间保持场景底图，不露出辅助方框与连接线。
        floor_area = pygame.Rect(515, 285, 61, 47)
        # 比较完整区域而非单点，防止只去掉方框却残留横线。
        self.assertEqual(pygame.image.tobytes(renderer.surface.subsurface(floor_area), "RGB"),
                         # 此测试角色位于远处，区域内应只有未改写的原背景。
                         pygame.image.tobytes(renderer.background.subsurface(floor_area), "RGB"))
        # 两次draw都没有修改共享背景，其他绘制器不会继承过期门状态。
        self.assertEqual(background, pygame.image.tobytes(renderer.background, "RGB"))

    # 玩家通过真实移动成功后先跨门，最终只留下无文字的门外夜景。
    def test_entering_open_exit_shows_outside_ending(self) -> None:
        # 正式规则只调整时间与出生位置，通关仍由模型公开更新决定。
        rules = load_game_rules()
        # 短游戏分钟让测试快速进入真实开放状态。
        rules["gameSecondsPerMinute"] = 0.1
        # 勇者从门槛左侧开始，第一帧实际走入门槛。
        rules["heroSpawn"] = [516, 305]
        # 保留安全起跑保护，避免无关接触结果抢占成功。
        rules["startDelaySeconds"] = 2
        # 从正常追逐阶段运行真实模型。
        model = create_game(rules=rules, play_intro=False)
        # 第一帧只走入关闭门槛，不能提前通关。
        model.update(0.05, 1, 0)
        # 到点前的真实进入不构成下班成功。
        self.assertFalse(model.escaped)
        # 在门槛上等待到点，模型自然产生成功结果。
        model.update(0.05)
        # 测试前提由规则触发，不是直接写escaped标志。
        self.assertTrue(model.escaped)
        # 成功先进入过门，立即弹结果面板不能代替完整动作。
        self.assertEqual(model.ending_phase, "crossing")
        # 正式过场通过同一更新接口自然结束。
        for _ in range(200):
            # 方向输入不再控制追逐或取消跨门。
            model.update(0.05, -1, 0)
        # 正式结果状态交给正常绘制器消费。
        renderer = Renderer(model)
        # 无中文字体时也不能附加英文结果文字。
        renderer.font_path = None
        # 记录真实文字调用，确认结局没有调用字幕接口。
        with patch.object(renderer, "label", wraps=renderer.label) as labels:
            # 使用普通draw完成夜景，不由测试替换画面。
            renderer.draw()
            # 收集真正传给字体绘制的文字。
            rendered = [call.args[0] for call in labels.call_args_list]
        # 门外结局不绘制标题、对白或操作字幕。
        self.assertEqual(rendered, [])
        # 过场确实完成，办公室画面已切换为安全门外。
        self.assertEqual(model.ending_phase, "complete")

    # 检查史莱姆与对话UI没有提前显示，呼吸确实改变画面而不改位置。
    def test_opening_is_clean_and_hero_breathes_without_moving(self) -> None:
        # 使用正常开场，原地不走时史莱姆不会提前出现。
        model = create_game()
        # 载入默认程序资源和绘制逻辑。
        renderer = Renderer(model)
        # 在t=0绘制首帧并保存字节；画布会复用，因此不能只保存引用。
        before = pygame.image.tobytes(renderer.draw(), "RGB")
        # 检查史莱姆区域、右上跳过按钮与底部对话框区域保持纯背景。
        for area in ((288, 192, 64, 64), (546, 12, 82, 25), (10, 300, 500, 48)):
            # 取出当前画面对应区域的实际像素。
            actual = pygame.image.tobytes(renderer.surface.subsurface(area), "RGB")
            # 取出默认背景相同区域的像素。
            expected = pygame.image.tobytes(renderer.background.subsurface(area), "RGB")
            # 完全相等说明没有提前叠加史莱姆、台词框或跳过提示。
            self.assertEqual(actual, expected)
        # 保存勇者脚底坐标，动画过程中必须保持不变。
        position = (model.hero.x, model.hero.y)
        # 经过半个呼吸周期，使高度起伏达到最高点。
        for _ in range(15):
            # 每次推进0.05秒，总计0.75秒。
            model.update(0.05)
        # 真实画面应变化，确认勇者不是静态PNG伪装的动画。
        self.assertNotEqual(before, pygame.image.tobytes(renderer.draw(), "RGB"))
        # 动作只来自绘制，勇者的世界坐标没有发生移动。
        self.assertEqual(position, (model.hero.x, model.hero.y))

    # 面前跳出期间只显示身体与落地效果，台词框要在回弹结束后出现。
    def test_entrance_changes_picture_before_dialogue_appears(self) -> None:
        # 通过真实走路触发登场，再交给正式绘制器。
        model = create_game()
        # 创建正常游戏绘制器，避免另造参考画面。
        renderer = Renderer(model)
        # 累积到触发距离，史莱姆刚开始从地面弹起。
        for _ in range(23):
            # 提供向右移动输入，累积到触发登场所需的实际距离。
            model.update(0.05, 1, 0)
        # 保存刚弹出时的完整画面。
        first = pygame.image.tobytes(renderer.draw(), "RGB")
        # 再推进到空中，检查实际动画而非静态角色替换。
        for _ in range(5):
            # 这一阶段不需要继续移动勇者。
            model.update(0.05)
        # 史莱姆的身体高度与尺寸已经变化。
        self.assertNotEqual(first, pygame.image.tobytes(renderer.draw(), "RGB"))
        # 空中时尚未开始史莱姆台词。
        self.assertFalse(model.dialogue.active)
        # 底部对话区域仍保持默认背景。
        area = (10, 300, 500, 48)
        # 逐像素比较，不只检查台词播放器的状态字段。
        self.assertEqual(pygame.image.tobytes(renderer.surface.subsurface(area), "RGB"),
                         # 同一区域的纯背景作为预期结果。
                         pygame.image.tobytes(renderer.background.subsurface(area), "RGB"))

    # 检查正常追逐画面不残留旧底栏、角色标签或选择圈。
    def test_scene_has_no_footer_or_character_labels(self) -> None:
        # 建立与游戏同尺寸的虚拟显示，供图片格式转换使用。
        pygame.display.set_mode(LOGICAL_SIZE)
        # 创建跳过开场的游戏绘制器，检查正常追逐中的干净场景。
        renderer = Renderer(create_game(play_intro=False))
        # 绘制当前场景，得到真实游戏画布，而不是另造一张参考图。
        image = renderer.draw()
        # 确认逻辑画布是 640×360，没有多出的底部工具栏高度。
        self.assertEqual(image.get_size(), LOGICAL_SIZE)
        # 选取底部及角色脚下几块区域，分别检查旧提示、名字与选择圈是否残留。
        for area in ((0, 330, 640, 30),
                     # 勇者已移到左侧起点，检查区跟随实际脚底，避免误把角色本体当旧标签。
                     (round(renderer.model.hero.x) - 28, round(renderer.model.hero.y) + 1, 56, 25),
                     # 史莱姆改在中央登场，标签检查也使用当前真实位置。
                     (round(renderer.model.slime.x) - 24, round(renderer.model.slime.y) + 1, 48, 22)):
            # 把这些区域转成 RGB 字节与纯背景逐像素比较，确认没有叠加旧 UI。
            self.assertEqual(pygame.image.tobytes(image.subsurface(area), "RGB"),
                             # 取同一块默认背景作参考；两边 RGB 字节完全相等才算没有旧提示或标签。
                             pygame.image.tobytes(renderer.background.subsurface(area), "RGB"))

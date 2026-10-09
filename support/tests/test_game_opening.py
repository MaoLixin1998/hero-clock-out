"""验证正常游戏的移动触发、登场、对话与追逐顺序。"""

# 标准测试框架检查正常游戏阶段与登场边界。
import unittest

# 每个案例获取独立且已经校验的正式游戏规则。
from hero_game.config import load_game_rules
# 应用工厂提供默认正式依赖，不加载任何本机拍摄场景。
from hero_game.app.game_factory import create_game


# 开场回归只覆盖正式游戏，不加载本机拍摄扩展。
class GameOpeningChecks(unittest.TestCase):
    # 在不同位置、不同走路方向触发，史莱姆都应落在当时的勇者面前。
    def test_landing_tracks_trigger_position_and_facing(self) -> None:
        # 每个案例给出起点、输入、预期落点与面对勇者的史莱姆朝向。
        cases = (
            # 两个向右的位置都应在右前方登场，不能沿用固定办公室中央。
            ([100, 200], (1, 0), (180, 200), "left"),
            # 右侧较远的起点也按当前位置计算落点。
            ([400, 280], (1, 0), (480, 280), "left"),
            # 向左时史莱姆挡在左前方，并朝右看勇者。
            ([300, 220], (-1, 0), (220, 220), "right"),
            # 改变纵向位置后，落点应一起改变。
            ([500, 280], (-1, 0), (420, 280), "right"),
            # 向上时史莱姆应出现在勇者上方，仍留在活动边界内。
            ([240, 252], (0, -1), (240, 172), "down"),
            # 另一个向上起点验证不是写死某条水平线。
            ([420, 290], (0, -1), (420, 210), "down"),
            # 向下时落点位于勇者下方，史莱姆朝上看。
            ([260, 248], (0, 1), (260, 328), "up"),
            # 另一个向下位置同样根据真实触发点计算。
            ([450, 210], (0, 1), (450, 290), "up"),
        )
        # 逐个走真实移动入口，检查落点设置发生在走够距离的那一帧。
        for origin, movement, expected, slime_facing in cases:
            # 标记失败案例，便于区分方向或位置问题。
            with self.subTest(origin=origin, movement=movement):
                # 缩短触发距离到8像素，单帧即可检查移动后的坐标。
                rules = {**load_game_rules(), "heroSpawn": origin, "introWalkSteps": 1, "introStepPixels": 8}
                # 按这个起点建立真实开场状态。
                model = create_game(rules=rules)
                # 160像素/秒乘0.05秒等于8像素，恰好触发登场。
                model.update(0.05, *movement)
                # 史莱姆的脚底必须在指定前方落点。
                self.assertEqual((model.slime.x, model.slime.y), expected)
                # 朝向也要对着勇者，不能背着对话角色登场。
                self.assertEqual(model.slime.direction, slime_facing)
                # 落点设置后进入跳跃阶段，台词仍需等待落稳。
                self.assertEqual(model.intro_phase, "entrance")

    # 贴墙、四角和室内位置均要保证完整间距，且不挪动勇者身体。
    def test_edges_and_corners_keep_landing_in_front_without_moving_hero(self) -> None:
        # 四向单位向量用于检查落点与最终朝向的几何关系。
        vectors = {"right": (1, 0), "left": (-1, 0), "up": (0, -1), "down": (0, 1)}
        # 横向覆盖两侧墙、贴墙内侧和房间中部。
        for x in (80, 81, 314, 547, 548):
            # 纵向覆盖上下墙、贴墙内侧和房间中部。
            for y in (172, 173, 250, 327, 328):
                # 每个位置都检查全部四种原朝向。
                for facing in vectors:
                    # 输出具体位置与朝向，定位边界场景。
                    with self.subTest(position=(x, y), facing=facing):
                        # 建立真实游戏对象，单独检查落点选择规则。
                        model = create_game()
                        # 设置当前位置，模拟走路触发时可能出现的任意边界位置。
                        model.hero.x, model.hero.y = x, y
                        # 设置最后走路朝向，允许落点不足时转向室内。
                        model.hero.direction = facing
                        # 使用真实落点计算，不在检查中实现另一份挑选算法。
                        model.place_slime_in_front()
                        # 勇者身体必须留在原处，不能为放史莱姆而瞬移。
                        self.assertEqual((model.hero.x, model.hero.y), (x, y))
                        # 最终朝向给出前方的几何方向。
                        dx, dy = vectors[model.hero.direction]
                        # 最终落点必须保持72像素间距，不能贴墙后夹成重叠。
                        self.assertEqual((model.slime.x - x, model.slime.y - y), (dx * 72, dy * 72))
                        # 落点横坐标完整留在活动区域内。
                        self.assertTrue(80 <= model.slime.x <= 548)
                        # 落点纵坐标也完整留在活动区域内。
                        self.assertTrue(172 <= model.slime.y <= 328)
                        # 两人朝向相反，史莱姆看向勇者。
                        self.assertEqual(vectors[model.slime.direction], (-dx, -dy))

    # 前后空间都不足时应转向侧面，避免参数调整后出现无法放置的落点。
    def test_side_direction_is_used_when_forward_and_back_do_not_fit(self) -> None:
        # 100像素超过活动区半高，中央向上或向下都放不下。
        model = create_game(rules={**load_game_rules(), "slimeEntranceDistance": 100})
        # 把勇者放在中央，检查空间不足的两个纵向候选。
        model.hero.x, model.hero.y = 314, 250
        # 原先向下看，向下和转身向上都不足100像素。
        model.hero.direction = "down"
        # 真实选择规则应该找到可用的侧面空地。
        model.place_slime_in_front()
        # 使用侧面后仍保持完整间距与面对面，不改变勇者位置。
        self.assertEqual((model.hero.x, model.hero.y, model.hero.direction), (314, 250, "left"))
        # 史莱姆在勇者最终朝向的前方100像素处。
        self.assertEqual((model.slime.x, model.slime.y, model.slime.direction), (214, 250, "right"))

    # 没有真实位移时，等待再久也不应该出现史莱姆。
    def test_idle_and_wall_push_do_not_trigger_entrance(self) -> None:
        # 创建正常游戏，起点只有勇者。
        model = create_game()
        # 模拟长时间原地等待，确认已不再按三秒倒计时登场。
        for _ in range(100):
            # 零方向只让勇者待机，不算走路。
            model.update(0.05)
        # 等待没有积累任何步数。
        self.assertEqual(model.walk_distance, 0)
        # 史莱姆尚未出现，也没有提前说话。
        self.assertFalse(model.slime_visible or model.dialogue.active)
        # 将勇者放在右边界，专门检查贴墙按键。
        model.hero.x = model.bounds[2]
        # 在墙边持续按右，输入方向不能冒充实际位移。
        for _ in range(100):
            # 边界夹紧后位置不变，因此步数也不应增加。
            model.update(0.05, 1, 0)
        # 贴墙输入仍未触发登场。
        self.assertEqual((model.walk_distance, model.intro_phase), (0, "walk"))

    # 先走够距离，再跳出，再落稳说话，最后才允许追逐。
    def test_walk_jump_dialogue_and_chase_are_separate(self) -> None:
        # 正常游戏开始时没有史莱姆或台词框。
        model = create_game()
        # 记录最初的勇者位置，用实际位移检查触发距离。
        origin = model.hero.x
        # 1.1秒只走出176像素，尚未到180像素触发点。
        for _ in range(22):
            # 向右行走，史莱姆仍不能提前出现。
            model.update(0.05, 1, 0)
        # 检查步数不足时仍只显示勇者。
        self.assertFalse(model.slime_visible)
        # 下一帧跨过180像素，剩余时间应该推进跳跃。
        model.update(0.05, 1, 0)
        # 勇者恰好走到触发点，没有多走一帧。
        self.assertAlmostEqual(model.hero.x - origin, 180)
        # 史莱姆已现身，但是落地前没有台词框。
        self.assertTrue(model.slime_visible)
        # 当前处于登场动画，不能提前播放对话。
        self.assertEqual(model.intro_phase, "entrance")
        # 检查正常时间边界切分后的跳跃进度。
        self.assertAlmostEqual(model.entrance_elapsed, 0.025)
        # 登场期间双方身体位置不再受输入影响。
        before = (vars(model.hero).copy(), vars(model.slime).copy())
        # 推进到落稳，使用有限循环防止错误逻辑让检查一直等待。
        for _ in range(18):
            # 即使持续按方向，登场期间也不能开始追逐。
            model.update(0.05, 1, 0)
        # 双方仍保持触发时的身体位置和动画字段。
        self.assertEqual(before, (vars(model.hero), vars(model.slime)))
        # 史莱姆现在开始固定对话。
        self.assertTrue(model.dialogue.active)
        # 第一位说话者是史莱姆，而非提前进入失败台词。
        self.assertEqual(model.dialogue.current["speaker"], "slime")
        # 真正落地只产生一次声音事件。
        self.assertEqual(model.landing_serial, 1)
        # 开场演出没有消耗追击的有效时间。
        self.assertEqual(model.elapsed, 0)
        # 对话后的起跑缓冲完整保留。
        self.assertEqual(model.start_delay, load_game_rules()["startDelaySeconds"])
        # 跳过对话后进入逃跑，勇者先走、敌人等待。
        model.dialogue.skip()
        # 向右走一小段，检查追逐确实可以继续。
        model.update(0.05, 1, 0)
        # 勇者已恢复移动。
        self.assertGreater(model.hero.x, before[0]["x"])
        # 敌人此刻仍处于起跑缓冲。
        self.assertEqual(vars(model.slime), before[1])

    # 比较不同刷新率，触发距离和跳跃进度不能随帧数变化。
    def test_distance_trigger_and_jump_are_frame_rate_independent(self) -> None:
        # 保存每种帧率下两秒后的结果。
        results = []
        # 使用30、60、120 FPS进行同一段连续行走。
        for frames_per_second in (30, 60, 120):
            # 每种帧率从相同的真实起点开始。
            model = create_game()
            # 两秒包含走路、弹起和大部分落地回弹。
            for _ in range(2 * frames_per_second):
                # 单帧时间取刷新间隔，向右输入保持相同。
                model.update(1 / frames_per_second, 1, 0)
            # 收集实际身体位置、演出时间和落地次数。
            results.append((model.hero.x, model.walk_distance, model.entrance_elapsed, model.landing_serial))
        # 逐项比较后两种帧率与首个结果。
        for result in results[1:]:
            # 配对每个状态值，避免只检查人物横坐标。
            for expected_value, actual_value in zip(results[0], result):
                # 浮点运算允许微小误差，实际行为应一致。
                self.assertAlmostEqual(expected_value, actual_value, places=7)

    # 横走与斜走使用同一种距离计算，斜走不额外增加步数。
    def test_diagonal_distance_is_not_double_counted(self) -> None:
        # 扩大测试边界，避免这一检查被上下墙干扰。
        rules = {**load_game_rules(), "heroSpawn": [300, 180], "movementBounds": [0, 0, 640, 360]}
        # 使用实际开场规则，仅调整检查场地。
        model = create_game(rules=rules)
        # 移动半秒，应累积80像素而非两个坐标变化的简单相加。
        for _ in range(10):
            # 同时向右下走，验证归一化后的距离。
            model.update(0.05, 1, 1)
        # 斜走总距离与横走一致。
        self.assertAlmostEqual(model.walk_distance, 80)

    # 暂停必须冻结走路、呼吸、跳跃和落地声音事件。
    def test_pause_freezes_entrance(self) -> None:
        # 创建正常游戏并实际走到登场阶段。
        model = create_game()
        # 23次更新会触发史莱姆跳出。
        for _ in range(23):
            # 通过真实输入进入演出，不伪造阶段字段。
            model.update(0.05, 1, 0)
        # 记录全部演出计时和声音编号。
        before = (model.opening_elapsed, model.entrance_elapsed, model.walk_distance, model.landing_serial)
        # 模拟切到后台导致暂停。
        model.paused = True
        # 暂停期间仍尝试提供方向和时间。
        for _ in range(100):
            # 暂停入口必须拦住所有演出推进。
            model.update(0.05, 1, 0)
        # 对比状态，暂停没有跳过落地或偷偷播放事件。
        self.assertEqual(before, (model.opening_elapsed, model.entrance_elapsed, model.walk_distance, model.landing_serial))

    # 普通失败重试直接逃跑，不用再次走路等待登场。
    def test_retry_skips_opening(self) -> None:
        # 创建正常首次开场。
        model = create_game()
        # 模拟失败后使用真实重开入口。
        model.reset()
        # 重试已处于正常追逐阶段。
        self.assertFalse(model.opening_active)
        # 史莱姆直接在场，但不重播开场对话。
        self.assertTrue(model.slime_visible)
        # 重试没有残留台词。
        self.assertFalse(model.dialogue.active)
        # 检查起跑缓冲内勇者能立即移动。
        model.update(0.05, 1, 0)
        # 实际横坐标已经增加。
        self.assertGreater(model.hero.x, load_game_rules()["heroSpawn"][0])

    # 史莱姆可能在勇者身边落地，缓冲期间必须允许先跑。
    def test_start_grace_allows_escape_from_landing_contact(self) -> None:
        # 跳过演出，专门检查追逐开始前的保护时间。
        model = create_game(play_intro=False)
        # 让勇者恰好与史莱姆重合，检查起跑保护不依赖落点是否曾与勇者接近。
        model.hero.x, model.hero.y = model.slime.x, model.slime.y
        # 起跑缓冲内向右走，不能刚恢复移动就被判失败。
        model.update(0.05, 1, 0)
        # 即使仍在碰撞半径内，也有完整缓冲可逃出。
        self.assertFalse(model.caught)
        # 勇者已经实际离开重合的起点。
        self.assertGreater(model.hero.x, model.slime.x)

    # 拒绝无法正常完成登场动作的参数。
    def test_invalid_entrance_rules_are_rejected(self) -> None:
        # 覆盖零步数、负距离以及没有回弹时间的三种错误。
        for change in ({"introWalkSteps": 0}, {"introStepPixels": -1}, {"slimeEntranceSeconds": 0.6},
                       # 不能将落点贴到碰撞半径内，也不能要求超过房间容量的间距。
                       {"slimeEntranceDistance": 22}, {"slimeEntranceDistance": 240}):
            # 每个错误配置都应立即报告明确异常。
            with self.assertRaises(ValueError):
                # 使用真实初始化校验。
                create_game(rules={**load_game_rules(), **change})

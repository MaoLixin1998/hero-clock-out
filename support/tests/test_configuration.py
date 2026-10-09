"""验证配置边界、合法零值与嵌套状态的实例隔离。"""

# 标准测试框架记录每种非法配置对应的实际异常。
import unittest

# 真实配置入口负责包内数据解析、边界校验与独立副本。
from hero_game.config import MIN_RETARGET_SECONDS, load_game_presentation, load_game_rules, validate_game_presentation, validate_game_rules
# 应用工厂组装默认对白，游戏实例独立持有传入的规则。
from hero_game.app.game_factory import create_game


# 通过公开配置入口检查数值边界，不以类型标注替代运行时验证。
class ConfigurationChecks(unittest.TestCase):
    # 非有限速度、时长、坐标和布尔数值不能进入游戏状态。
    def test_nonfinite_and_boolean_values_are_rejected(self) -> None:
        # 每种数值都应在进入运动循环前失败。
        for invalid in (float("nan"), float("inf"), -float("inf"), True, 10 ** 400):
            # 分别覆盖正数规则与允许零的起跑延迟。
            for field in ("heroSpeed", "retargetSeconds", "startDelaySeconds"):
                # 记录具体字段和输入类型，不打印任何剧情内容。
                with self.subTest(field=field, invalid=repr(invalid)):
                    # 每个子案例读取自己的规则，避免相互污染。
                    rules = load_game_rules()
                    # 只替换要验证的一个参数。
                    rules[field] = invalid
                    # 非法数值必须明确失败，而不是悄悄采用默认值。
                    with self.assertRaises(ValueError):
                        # 使用真实正式配置校验入口。
                        validate_game_rules(rules)
            # 二维坐标同样拒绝非有限数与布尔值。
            with self.subTest(field="heroSpawn", invalid=repr(invalid)):
                # 默认坐标列表由此案例独立持有。
                rules = load_game_rules()
                # 只污染横坐标，纵坐标保持合法以定位失败原因。
                rules["heroSpawn"][0] = invalid
                # 校验不能把非法坐标转换成零或字符串。
                with self.assertRaises(ValueError):
                    # 直接验证实际配置对象。
                    validate_game_rules(rules)

    # 两个有限正数相乘仍可溢出，触发距离必须在进入开场循环前明确拒绝。
    def test_overflowing_derived_walk_distance_is_rejected(self) -> None:
        # 每例使用独立正式规则，避免改变其他游戏的默认参数。
        rules = load_game_rules()
        # 两个单项都能作为有限浮点数表示，但乘积超出浮点范围。
        rules.update(introWalkSteps=1e200, introStepPixels=1e200)
        # 错误应表现为配置ValueError，而不是永久无法触发开场。
        with self.assertRaises(ValueError):
            # 真实配置入口负责派生数值检查。
            validate_game_rules(rules)

    # 微小反应周期必须大于模拟容差，合法最小边界则保持可推进。
    def test_reaction_interval_has_explicit_progress_boundary(self) -> None:
        # 低于下限的数值即使有限且为正，也不能用于时间切片。
        for invalid_interval in (MIN_RETARGET_SECONDS / 2, 1e-12, 5e-324):
            # 标记具体间隔便于定位数值边界。
            with self.subTest(interval=invalid_interval):
                # 默认规则只修改当前待验证的参数。
                rules = load_game_rules()
                # 不能把微小间隔擅自回退为默认0.2秒。
                rules["retargetSeconds"] = invalid_interval
                # 配置创建阶段即拒绝不可靠的时间步长。
                with self.assertRaises(ValueError):
                    # 校验真实正式规则，不在测试中实现时间循环。
                    validate_game_rules(rules)
        # 精确下限是合法值，不因小于常用帧间隔而被覆盖。
        rules = load_game_rules()
        # 使用公开命名常量作为已说明的接口边界。
        rules["retargetSeconds"] = MIN_RETARGET_SECONDS
        # 零起跑保护让本项直接进入反应切片，避免等待掩盖问题。
        rules["startDelaySeconds"] = 0
        # 正常游戏模型必须接受合法边界配置。
        model = create_game(rules=rules, play_intro=False)
        # 推进两个反应周期，验证当前帧能够实际消耗时间并退出。
        model.update(2 * MIN_RETARGET_SECONDS)
        # 有效追逐时间完整推进，没有卡在零长度切片。
        self.assertAlmostEqual(model.elapsed, 2 * MIN_RETARGET_SECONDS)

    # 默认文件和外部注入共用完整显示字段契约，空字符串合法且查询副本独立。
    def test_presentation_contract_preserves_empty_values_and_rejects_bad_fields(self) -> None:
        # 完整正式数据提供独立的合法结构。
        supplied = load_game_presentation()
        # 空标题是合法显示选择，与缺失字段分别处理。
        supplied["windowTitle"] = ""
        # 校验得到独立外层字典，字段值都是不可变字符串。
        actual = validate_game_presentation(supplied)
        # 不能用默认标题覆盖合法空值。
        self.assertEqual(actual["windowTitle"], "")
        # 修改调用方配置，校验结果应保持创建时的值。
        supplied["windowTitle"] = "changed"
        # 表明外部赋值无法回写实际显示配置。
        self.assertEqual(actual["windowTitle"], "")
        # 缺字段、额外字段和非字符串分别覆盖真实接口错误。
        invalid_settings = (
            # 空对象不能作为完整显示配置。
            {},
            # 额外字段通常代表拼错配置名，不默默忽略。
            {**load_game_presentation(), "unexpected": "value"},
            # 布尔开关不是合法界面正文。
            {**load_game_presentation(), "pausedTitle": True},
        )
        # 每份输入必须通过同一个公开校验入口失败。
        for settings in invalid_settings:
            # 错误不得推迟到首次暂停或被抓后才出现。
            with self.assertRaises(ValueError):
                # 不在测试中复制字段检查算法。
                validate_game_presentation(settings)

    # 零延迟是明确立即追击的合法设置，不能被默认延迟覆盖。
    def test_zero_delay_is_preserved_and_chase_starts_immediately(self) -> None:
        # 每例从正式规则产生独立字典。
        rules = load_game_rules()
        # 合法零值表示不提供起跑保护。
        rules["startDelaySeconds"] = 0
        # 跳过首次登场，直接观察追击规则。
        model = create_game(rules=rules, play_intro=False)
        # 保存敌人初始位置，作为行为预期的独立依据。
        initial_position = (model.slime.x, model.slime.y)
        # 推进一次真实更新，不直接调用敌人的移动函数。
        model.update(0.05)
        # 零延迟应完整保留。
        self.assertEqual(model.start_delay, 0)
        # 敌人已经追击，证明零没有被0.8秒默认值替换。
        self.assertNotEqual((model.slime.x, model.slime.y), initial_position)

    # 调用方和不同游戏实例不能通过嵌套列表互相改变运行参数。
    def test_nested_rules_are_independent_between_instances(self) -> None:
        # 保留一份独立的正式预期，避免用被修改对象验证自身。
        expected = load_game_rules()
        # 同一个输入字典可以供调用方构建多个独立游戏。
        provided_rules = load_game_rules()
        # 创建第一局游戏，模型应取得自己的配置所有权。
        first = create_game(rules=provided_rules, play_intro=False)
        # 第二局收到同一外部对象，但内部规则不应共享嵌套引用。
        second = create_game(rules=provided_rules, play_intro=False)
        # 外部调用方修改输入列表，不应改变已经创建的任何游戏。
        provided_rules["heroSpawn"][0] += 1
        # 第一局仍使用创建时的合法出生点。
        self.assertEqual(first.rules["heroSpawn"], expected["heroSpawn"])
        # 第二局也保持创建时的出生点。
        self.assertEqual(second.rules["heroSpawn"], expected["heroSpawn"])
        # 保存第一局对外提供的嵌套规则快照，检查查询是否泄漏内部引用。
        first_snapshot = first.rules
        # 修改查询结果不能回写第一局规则，也不能影响第二局。
        first_snapshot["slimeSpawn"][0] += 1
        # 第一局内部出生点仍与创建时一致。
        self.assertEqual(first.rules["slimeSpawn"], expected["slimeSpawn"])
        # 第二局也不得因别的实例查询结果被修改而改变。
        self.assertEqual(second.rules["slimeSpawn"], expected["slimeSpawn"])
        # 重新读取正式配置不得受到任何运行实例的修改影响。
        self.assertEqual(load_game_rules(), expected)

    # 时钟必须是可显示的真实HH:MM，错误值不能进入字形索引。
    def test_clock_format_rejects_invalid_hours_and_minutes(self) -> None:
        # 长度、分隔符、范围、非ASCII数字和类型分别覆盖实际边界。
        for invalid in ("24:00", "17:60", "1:29", "17-29", "１２:３０", None):
            # 明确记录失败的输入，方便定位格式问题。
            with self.subTest(clock=invalid):
                # 每例读取独立配置。
                rules = load_game_rules()
                # 替换唯一待验证字段。
                rules["clockText"] = invalid
                # 错误时钟必须在启动前抛出明确异常。
                with self.assertRaises(ValueError):
                    # 使用正式配置校验而非测试内自造正则。
                    validate_game_rules(rules)

    # 出生点越界、矩形反向和维度错误需要在创建游戏前失败。
    def test_invalid_spatial_configuration_is_rejected(self) -> None:
        # 每个覆盖只改变一个几何约束。
        invalid_changes = (
            # 出生点不能位于活动矩形之外。
            {"heroSpawn": [0, 0]},
            # 矩形的左右顺序不能反向。
            {"movementBounds": [548, 172, 80, 328]},
            # 二维坐标不能缺少纵坐标。
            {"slimeSpawn": [320]},
            # 两个接触半径都需要正值。
            {"collisionRadii": [0, 12]},
            # 出口图片在场地外不代表角色能走到，门槛必须完整位于活动区域。
            {"exitBounds": [558, 172, 618, 200]},
            # 反向门槛没有可进入的面积。
            {"exitBounds": [548, 172, 520, 200]},
            # 缺少边界值不能被默默补成默认出口。
            {"exitBounds": [520, 172, 548]},
            # 非有限出口会破坏连续轨迹判断。
            {"exitBounds": [520, 172, float("nan"), 200]},
        )
        # 独立检查每种配置错误。
        for change in invalid_changes:
            # 标记覆盖字段便于诊断。
            with self.subTest(change=change):
                # 不合法配置应明确阻止游戏实例建立。
                with self.assertRaises(ValueError):
                    # 合并独立默认规则与当前错误，不修改共享常量。
                    create_game(rules={**load_game_rules(), **change})

    # 下班目标和时间换算必须合法且可推进，错误不能拖到逐帧循环才失败。
    def test_invalid_shift_configuration_is_rejected(self) -> None:
        # 覆盖结束时间、零时长、非有限参数与派生乘积溢出。
        invalid_changes = (
            # 钟面格式与初始时间采用相同严格规则。
            {"shiftEndText": "17:60"},
            # 起止相同没有明确的一局时长。
            {"shiftEndText": "17:29"},
            # 不能用零秒表示一个游戏分钟。
            {"gameSecondsPerMinute": 0},
            # 负数不能让游戏时钟倒走。
            {"gameSecondsPerMinute": -1},
            # 布尔值不是秒数。
            {"gameSecondsPerMinute": True},
            # 非有限时长无法形成正常开门边界。
            {"gameSecondsPerMinute": float("inf")},
            # 时长小于模拟容差时必须明确拒绝。
            {"gameSecondsPerMinute": 1e-12},
            # 单项有限但跨多分钟后的总时长可能溢出。
            {"gameSecondsPerMinute": 1e308, "shiftEndText": "17:31"},
        )
        # 每次只验证一份独立错误配置。
        for change in invalid_changes:
            # 说明是哪一种时间边界未被拒绝。
            with self.subTest(change=change):
                # 使用真实创建路径，不能在测试里另写校验算法。
                with self.assertRaises(ValueError):
                    # 合并只作用于这份实例的规则。
                    create_game(rules={**load_game_rules(), **change})

"""纯游戏参数契约与校验；不读取文件、创建窗口或访问外部资源。"""

# 深拷贝隔离规则中的嵌套坐标，避免不同游戏实例共享可变状态。
from copy import deepcopy
# 映射与JSON边界类型明确输入契约，字段仍需真实校验。
from typing import Any, Mapping

# 共享纯数值校验处理NaN、无穷和极大整数溢出。
from hero_game.model.numeric import finite_number

# 图像布局目前为固定逻辑画布；其他分辨率通过窗口缩放实现。
LOGICAL_SIZE = (640, 360)
# 坐标字段的长度说明二维点、矩形和碰撞半径的格式。
VECTOR_LENGTHS = {"canvas": 2, "movementBounds": 4, "heroSpawn": 2, "slimeSpawn": 2,
                  # 这些可选或显示字段沿用同一二维坐标约定。
                  "collisionRadii": 2, "collisionCenterOffset": 2,
                  # 出口采用脚底坐标的左、上、右、下四条边。
                  "exitBounds": 4,
                  # 门框采用同一逻辑画布上的四边坐标。
                  "exitDoorBounds": 4}
# 正数参数直接参与除法、移动与动画进度，零值会使规则失效。
POSITIVE_FIELDS = ("heroSpeed", "slimeSpeed", "retargetSeconds", "introWalkSteps",
                   # 登场的距离与两个阶段时长均需要明确的正值。
                   "introStepPixels", "slimeJumpSeconds", "slimeEntranceSeconds",
                   # 高度和间距决定可见动作与独立落点。
                   "slimeJumpHeight", "slimeEntranceDistance",
                   # 一个游戏分钟对应的有效模拟秒数，默认按真实60秒推进。
                   "gameSecondsPerMinute",
                   # 闪身距离与运动、恢复时长属于正式技能规则。
                   "dashDistance", "dashSeconds", "dashRecoverySeconds")
# 反应周期至少一微秒，比模拟的1e-9秒浮点容差大1000倍，保证时间切片前进。
MIN_RETARGET_SECONDS = 1e-6
# 钟面按24小时循环，跨午夜的下班时间仍能向前计算。
MINUTES_PER_DAY = 24 * 60


# 将严格HH:MM钟面转换成当天分钟数；field用于指出错误的配置字段。
def parse_clock_minutes(value: object, field: str) -> int:
    # 数字范围与字符结构同时验证，保证字形查找和分钟换算安全。
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        # 不隐式接受日期、秒数或省略前导零的格式。
        raise ValueError(f"{field} must use HH:MM")
    # 时分必须为ASCII数字，不能让其他数字字符进入字形缓存。
    if not (value[:2].isascii() and value[:2].isdigit()
            # 分钟同样必须恰好为两位数字。
            and value[3:].isascii() and value[3:].isdigit()
            # 24小时钟面的合法范围为00:00到23:59。
            and int(value[:2]) < 24 and int(value[3:]) < 60):
        # 无效时间属于配置错误，在构造游戏前报告。
        raise ValueError(f"{field} must be a valid time")
    # 小时乘60后加分钟，返回不依赖系统时区的游戏时间。
    return int(value[:2]) * 60 + int(value[3:])


# 校验实际游戏参数并深拷贝返回，防止外部配置在运行中偷偷改变规则。
def validate_game_rules(rules: Mapping[str, Any]) -> dict[str, Any]:
    # 映射校验先于复制，不能把任意序列隐式解释为键值对。
    if not isinstance(rules, Mapping):
        # 非映射属于接口类型错误。
        raise TypeError("Game rules must be a mapping")
    # 嵌套坐标列表也独立复制，避免不同实例互相影响。
    actual = deepcopy(dict(rules))
    # 每个坐标字段都先核对维度再检查元素类型。
    for field, length in VECTOR_LENGTHS.items():
        # 必要字段缺失通过明确键名报错。
        value = actual[field]
        # 布尔值和字符串不能伪装坐标数组。
        if not isinstance(value, (list, tuple)) or len(value) != length:
            # 说明应提供的维度。
            raise ValueError(f"{field} must contain {length} coordinates")
        # 每个坐标单独校验，极大整数转浮点溢出也作为明确ValueError报告。
        for index, item in enumerate(value):
            # 校验结果不覆盖原整数，画布维度与像素参数保持原有类型。
            finite_number(item, f"{field}[{index}]")
    # 当前渲染布局只支持既定逻辑尺寸。
    if tuple(actual["canvas"]) != LOGICAL_SIZE:
        # 不接受会把对话框裁掉的未适配画布。
        raise ValueError("Logical canvas must be 640 by 360")
    # 门框必须有正面积并位于画布内，角色跨门可离开可玩边界。
    door_left, door_top, door_right, door_bottom = actual["exitDoorBounds"]
    # 同时保证绘制取纹理不会越出背景。
    if not (0 <= door_left < door_right <= LOGICAL_SIZE[0] and 0 <= door_top < door_bottom <= LOGICAL_SIZE[1]):
        # 非法门框在创建绘制器之前报错。
        raise ValueError("exitDoorBounds must fit inside the canvas")
    # 活动矩形必须有正宽和正高。
    left, top, right, bottom = actual["movementBounds"]
    # 游戏边界必须完整位于画布内部。
    if not (0 <= left < right <= LOGICAL_SIZE[0] and 0 <= top < bottom <= LOGICAL_SIZE[1]):
        # 非法边界会造成夹紧运动与落点选择失效。
        raise ValueError("Movement bounds must fit inside the canvas")
    # 出口整个门槛必须能被角色脚底实际走到，不能只落在背景门图片内。
    exit_left, exit_top, exit_right, exit_bottom = actual["exitBounds"]
    # 有正面积且位于活动边界内才是合法进入区域。
    if not (left <= exit_left < exit_right <= right and top <= exit_top < exit_bottom <= bottom):
        # 不通过放宽碰撞或移动边界掩盖无法到达的出口。
        raise ValueError("exitBounds must have positive area inside movement bounds")
    # 技能阶段不能短于时间切片的可靠精度。
    for field in ("dashSeconds", "dashRecoverySeconds"):
        # 拒绝过小秒数，避免阶段边界产生零时间循环。
        if finite_number(actual[field], field) < MIN_RETARGET_SECONDS:
            # 错误字段由配置入口明确报告。
            raise ValueError(f"{field} must be at least one microsecond")
    # 两个正式出生点均按相同边界验证。
    for field in ("heroSpawn", "slimeSpawn"):
        # 读取已经检查过维度与类型的二维点。
        x, y = actual[field]
        # 出生点不允许在房间外侧。
        if not (left <= x <= right and top <= y <= bottom):
            # 明确指出需要调整的配置字段。
            raise ValueError(f"{field} must be inside movement bounds")
    # 正数参数必须是真实有限数，避免除零和无限循环。
    for field in POSITIVE_FIELDS:
        # 必填参数不存在时不擅自默认，非有限值和极大整数在此明确失败。
        value = finite_number(actual[field], field)
        # 正值才能形成可推进的移动、反应或演出阶段。
        if value <= 0:
            # 每个失败都保留准确字段名。
            raise ValueError(f"{field} must be positive and finite")
    # 反应周期小于浮点容差时可能不断重瞄准却无法消耗帧时间，因此设明确下限。
    if actual["retargetSeconds"] < MIN_RETARGET_SECONDS:
        # 这是数值模拟的技术边界，与剧情和显示文案无关。
        raise ValueError(f"retargetSeconds must be at least {MIN_RETARGET_SECONDS} seconds")
    # 两个单项有限值相乘仍可能溢出，触发距离也必须保持有限。
    finite_number(actual["introWalkSteps"] * actual["introStepPixels"], "intro walk distance")
    # 起跑延迟允许零；共享检查拒绝布尔值、无穷和极大整数溢出。
    delay = finite_number(actual["startDelaySeconds"], "startDelaySeconds")
    # 负值不能代表等待时间，合法零值则完整保留。
    if delay < 0:
        # 合法零值不被其他默认值覆盖。
        raise ValueError("startDelaySeconds must be nonnegative and finite")
    # 两个碰撞半径均须为正，保证接触检测有实际范围。
    if any(radius <= 0 for radius in actual["collisionRadii"]):
        # 没有有效碰撞体时立即阻止运行。
        raise ValueError("Collision radii must be positive")
    # 跳跃必须先结束，再完成落地回弹。
    if actual["slimeJumpSeconds"] >= actual["slimeEntranceSeconds"]:
        # 防止渲染中的回弹时长分母变为零或负数。
        raise ValueError("Jump must finish before entrance settling")
    # 最大可用间距采用房间较长边的一半，保证始终存在候选方向。
    maximum_distance = max(right - left, bottom - top) / 2
    # 登场间距既要避开接触半径，也要在房间内放得下。
    if not sum(actual["collisionRadii"]) < actual["slimeEntranceDistance"] <= maximum_distance:
        # 不通过夹紧坐标偷偷缩短要求的距离。
        raise ValueError("Entrance distance must fit the room and exceed contact radius")
    # 开始和下班钟面共用严格格式，游戏模型只使用已校验的分钟数。
    start_minutes = parse_clock_minutes(actual["clockText"], "clockText")
    # 下班时间可以跨午夜，但不能与开始时间相同而产生歧义。
    end_minutes = parse_clock_minutes(actual["shiftEndText"], "shiftEndText")
    # 24小时取余得到向前经过的游戏分钟数。
    shift_minutes = (end_minutes - start_minutes) % MINUTES_PER_DAY
    # 零长度的一局没有等待开门的意义，明确拒绝而非猜测为全天。
    if shift_minutes == 0:
        # 让配置作者提供真实的起止时间。
        raise ValueError("shiftEndText must differ from clockText")
    # 过小的分钟时长会低于时间切片容差，导致边界无法可靠推进。
    if actual["gameSecondsPerMinute"] < MIN_RETARGET_SECONDS:
        # 采用与反应周期一致的最低模拟精度。
        raise ValueError("gameSecondsPerMinute must be at least one microsecond")
    # 两个有限值相乘仍可能溢出，完整下班时长也需要校验。
    finite_number(shift_minutes * actual["gameSecondsPerMinute"], "shift duration")
    # 返回已验证的实例副本。
    return actual

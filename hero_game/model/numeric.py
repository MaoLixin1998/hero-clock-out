"""模型边界的有限数值校验；纯函数不读取配置或启动窗口。"""

# 数学库检查无穷与非数字值，避免非法输入破坏运动循环。
import math
# Sequence 表达只需按顺序读取的点与边界，不要求调用方使用列表。
from collections.abc import Sequence


# 把整数或浮点输入转换为有限浮点数；布尔值虽然属于整数也明确拒绝。
# field_name 仅用于定位错误字段，不输出配置正文；失败抛出 ValueError。
def finite_number(value: object, field_name: str) -> float:
    # 仅接受真实数值，避免字符串被隐式转换或布尔开关冒充坐标。
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        # 在数据进入模型前指出类型错误，不能让后面的乘法得到意外结果。
        raise ValueError(f"{field_name} must be a finite number")
    # 极大整数可能超出浮点表示范围，保留为明确的输入边界错误。
    try:
        # 转成浮点便于后续统一比较、除法与时间累计。
        number = float(value)
    # 整数转浮点溢出也代表无法用于有限运动计算。
    except OverflowError as error:
        # 保留底层原因，不把非法输入静默回退为零。
        raise ValueError(f"{field_name} must be a finite number") from error
    # NaN 和无穷会令比较与循环边界失效，因此不作为合法模型输入。
    if not math.isfinite(number):
        # 明确报告非有限值，不默默回退为零。
        raise ValueError(f"{field_name} must be a finite number")
    # 返回经过类型与有限性检查的实际数值。
    return number


# 验证二维点或方向并返回独立元组；字符串不视为坐标序列。
def point_pair(value: Sequence[float], field_name: str) -> tuple[float, float]:
    # 两个分量分别对应横纵坐标，不允许缺失或多余值。
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
        # 用清楚的字段名指出结构错误，避免后面索引越界。
        raise ValueError(f"{field_name} must contain two coordinates")
    # 分别校验两个轴，返回不可变坐标对。
    return (
        # 横向坐标必须是有限数值。
        finite_number(value[0], f"{field_name}[0]"),
        # 纵向坐标采用相同的有限数值边界。
        finite_number(value[1], f"{field_name}[1]"),
    )


# 验证左、上、右、下四条活动边界，返回独立且有序的元组。
def movement_bounds(value: Sequence[float]) -> tuple[float, float, float, float]:
    # 四个分量固定采用屏幕坐标的左上右下顺序。
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 4:
        # 拒绝错误维度，而不是在移动时遗漏一条边界。
        raise ValueError("Movement bounds must contain four coordinates")
    # 逐项把边界转换为有限数值，确保后面的夹紧比较有效。
    left, top, right, bottom = (
        # 左边界限制最小横坐标。
        finite_number(value[0], "movementBounds[0]"),
        # 上边界限制最小纵坐标。
        finite_number(value[1], "movementBounds[1]"),
        # 右边界限制最大横坐标。
        finite_number(value[2], "movementBounds[2]"),
        # 下边界限制最大纵坐标。
        finite_number(value[3], "movementBounds[3]"),
    )
    # 横纵方向都必须留有实际活动空间，颠倒或零宽区域都属于错误配置。
    if left >= right or top >= bottom:
        # 保留明确的边界原因，调用方可在应用入口显示错误。
        raise ValueError("Movement bounds must have positive width and height")
    # 元组不与调用方原列表共享可变状态。
    return left, top, right, bottom

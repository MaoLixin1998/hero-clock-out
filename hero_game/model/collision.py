"""连续几何判定；返回首次事件比例，按真实运动顺序比较接触与过门。"""

# 数学库计算最近点距离，不依赖角色图片的透明边缘或尺寸。
import math
# Sequence 表达二维相对坐标的只读输入契约。
from collections.abc import Sequence

# 共享有限数值与二维点校验，非法输入不参与几何判断。
from hero_game.model.numeric import finite_number, movement_bounds, point_pair


# 判断相对运动线段是否进入两角色碰撞半径之和，返回明确布尔结果。
# start/end 为角色甲减角色乙的逻辑像素坐标，radius 为非负逻辑像素。
def crossed_capture_radius(
    # 本小段运动开始时的二维相对位置。
    start: Sequence[float],
    # 本小段运动结束时的二维相对位置。
    end: Sequence[float],
    # 两角色接触半径之和，与图片宽高没有对应关系。
    radius: float,
) -> bool:
    # 原有布尔接口复用首次接触查询，保留含边界接触与输入校验行为。
    return capture_contact_fraction(start, end, radius) is not None


# 查询相对运动线段首次进入接触圆的比例，范围为0到1，未接触返回None。
# start/end为角色甲减角色乙的二维坐标，radius为非负逻辑像素；起点在圆内返回0。
def capture_contact_fraction(
    # 本小段开始时两角色的二维相对位置。
    start: Sequence[float],
    # 本小段结束时两角色的二维相对位置。
    end: Sequence[float],
    # 两角色接触半径之和，零值表示只检测是否经过同一点。
    radius: float,
) -> float | None:
    # 先校验相对起点，防止 NaN 令后面的比较错误地返回未接触。
    start_x, start_y = point_pair(start, "start")
    # 终点采用同样的二维有限坐标契约。
    end_x, end_y = point_pair(end, "end")
    # 半径必须是有限数值，之后再检查它的非负范围。
    contact_radius = finite_number(radius, "radius")
    # 负半径没有几何含义，不通过绝对值偷偷修改调用方输入。
    if contact_radius < 0:
        # 在判定前报告错误，调用方可定位不合法的碰撞配置。
        raise ValueError("Capture radius must be nonnegative")
    # 起点已在圆内或边界上时，事件发生在本小段开始，不等待再次进入。
    if math.hypot(start_x, start_y) <= contact_radius:
        # 比例为零明确表示已经接触，不能与没有事件的None混用。
        return 0.0
    # 按最大绝对坐标统一缩放，避免极大或极小有限输入在平方时溢出或下溢。
    scale = max(abs(start_x), abs(start_y), abs(end_x), abs(end_y), contact_radius)
    # 起点不在圆内保证scale大于零，因此可以安全换算成无单位坐标。
    start_x, start_y = start_x / scale, start_y / scale
    # 终点和半径使用同一比例，不改变线段与接触圆的几何关系。
    end_x, end_y, contact_radius = end_x / scale, end_y / scale, contact_radius / scale
    # 相对终点减起点得到线段方向，缩放后每个分量都在有限范围内。
    vector_x, vector_y = end_x - start_x, end_y - start_y
    # 长度平方把后面的距离换算为沿当前线段的比例。
    length_squared = vector_x * vector_x + vector_y * vector_y
    # 没有有效位移且起点在圆外时，这一小段永远不会产生接触。
    if length_squared == 0:
        # 不进行除以零运算，也不把静止误判为首次进入。
        return None
    # 原点投影到无限直线上，比例可在线段外；最终仍只接受0到1之间的事件。
    projection = -(start_x * vector_x + start_y * vector_y) / length_squared
    # 从投影点直接求垂距，避免用两个接近的大平方数相减而把擦肩误判为相切。
    distance = math.hypot(start_x + projection * vector_x, start_y + projection * vector_y)
    # 即使无限直线也没有进入接触圆时，有限线段更不可能接触。
    if distance > contact_radius:
        # 无接触以None表达，调用方可以区分真正发生在起点的事件。
        return None
    # 半弦长度除以线段长度得到从投影位置退回到首次圆周接触的比例。
    half_chord_fraction = math.sqrt((contact_radius - distance) * (contact_radius + distance) / length_squared)
    # 沿运动方向先遇到靠近起点的圆周交点，而不是离开圆时的另一个交点。
    entry_fraction = projection - half_chord_fraction
    # 只保留当前运动线段内的事件，延长线上的接触不能改变本帧结果。
    if 0 <= entry_fraction <= 1:
        # 返回明确的时间比例，供模型比较捕获和过门谁先发生。
        return entry_fraction
    # 圆位于起点后方或终点之外时，本小段没有接触。
    return None


# 查询点线段首次进入含边界矩形的比例，范围为0到1，未进入返回None。
# bounds采用左、上、右、下顺序且必须有正宽高；非法维度或非有限数抛ValueError。
def rectangle_entry_fraction(
    # 运动开始时的二维位置，通常是勇者脚底坐标。
    start: Sequence[float],
    # 运动结束时的二维位置，与start使用相同逻辑像素单位。
    end: Sequence[float],
    # 矩形的左上右下边界，边缘和四角均包含在区域内。
    bounds: Sequence[float],
) -> float | None:
    # 点坐标复用同一有限数值契约，字符串和布尔值不能伪装成几何输入。
    start_x, start_y = point_pair(start, "start")
    # 终点在任何提前返回之前同样经过完整校验。
    end_x, end_y = point_pair(end, "end")
    # 复用有正宽高要求的矩形校验，返回独立不可变边界。
    left, top, right, bottom = movement_bounds(bounds)
    # 两个轴都必须允许同一时间比例，初始候选覆盖整个当前线段。
    entry_fraction, exit_fraction = 0.0, 1.0
    # 分别求穿过横向和纵向条带的时间，再取两个有效时间段的交集。
    for origin, destination, lower, upper in (
        # 横向条带由左、右两条竖线限定。
        (start_x, end_x, left, right),
        # 纵向条带由上、下两条横线限定。
        (start_y, end_y, top, bottom),
    ):
        # 方向可为负，两个边界的到达顺序会在后面统一排序。
        direction = destination - origin
        # 与某条带平行或完全静止时，坐标必须已经位于该条带中。
        if direction == 0:
            # 平行轨迹在条带外时永远不能进入整个矩形。
            if origin < lower or origin > upper:
                # 其余轴无法补救当前轴始终位于区域之外的问题。
                return None
            # 当前轴不限制进入时间，继续检查另一条带。
            continue
        # 两个相反极大坐标相减可能溢出，统一缩放后再求同一个时间比例。
        if not math.isfinite(direction):
            # 这一分支的端点必有非零绝对值，缩放不会产生除零。
            scale = max(abs(origin), abs(destination), abs(lower), abs(upper))
            # 在保留相对几何关系的有限坐标下继续计算。
            origin, destination, lower, upper = origin / scale, destination / scale, lower / scale, upper / scale
            # 缩放后的方向落在有限范围内，不再以无穷参与除法。
            direction = destination - origin
        # 分别求到达两个边界的时间比例，向左或向上移动时顺序会颠倒。
        first_boundary, second_boundary = (lower - origin) / direction, (upper - origin) / direction
        # 取较早边界作为进入、较晚边界作为离开，再收紧当前有效时间区间。
        entry_fraction = max(entry_fraction, min(first_boundary, second_boundary))
        # 离开时间也要满足此前轴的限制，不能把只在延长线上相交算作过门。
        exit_fraction = min(exit_fraction, max(first_boundary, second_boundary))
        # 两个条带没有公共时间时，整段轨迹不曾位于矩形内部或边界上。
        if entry_fraction > exit_fraction:
            # 立即返回无事件，避免把只先后经过两个条带误判为经过矩形。
            return None
    # 初始时间区间已限制为0到1，返回的首次进入比例一定属于当前线段。
    return entry_fraction

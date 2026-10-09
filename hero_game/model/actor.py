"""角色运动状态；不依赖图像、窗口或本机素材。"""

# 数学库计算方向长度与实际位移，斜走时据此保持相同速度。
import math
# Sequence 允许移动接口接收列表或元组形式的活动边界。
from collections.abc import Sequence
# 数据类只负责生成字段初始化，不加入资源或界面副作用。
from dataclasses import dataclass

# 统一校验运动参数和活动边界，避免数值错误污染坐标。
from hero_game.model.numeric import finite_number, movement_bounds

# 浮点位移小于此逻辑像素阈值时视为静止，防止贴墙残差触发行走动画。
MOVEMENT_EPSILON_PIXELS = 1e-9


# 持有单个角色的脚底坐标、四向朝向与行走计时；Game 创建并推进实例。
# x/y 的单位为逻辑像素，phase 为行走秒数，方向仅决定使用哪组动画。
# 自动生成初始化方法，所有可变运行字段均属于当前角色实例。
@dataclass
class Actor:
    # 稳定角色编号用于查找资源，不通过显示姓名判断角色身份。
    kind: str
    # 脚底横坐标保留浮点精度，避免低速帧丢失不足一像素的位移。
    x: float
    # 脚底纵坐标采用屏幕坐标，数值增大表示向下移动。
    y: float
    # 缺省朝下；有输入时按占比更大的轴选择四向朝向。
    direction: str = "down"
    # 实际产生位移才播放行走动画，贴墙按键仍视为静止。
    moving: bool = False
    # 连续行走的累计秒数用于选择动画帧，停下时清零。
    phase: float = 0.0

    # 数据类完成字段初始化后校验初始状态，非法位置不能留待绘制时才暴露。
    def __post_init__(self) -> None:
        # 稳定角色 ID 必须是非空字符串，不根据显示姓名推导身份。
        if not isinstance(self.kind, str) or not self.kind:
            # 创建失败时不生成一个无法匹配资源的角色。
            raise ValueError("Actor kind must be a nonempty string")
        # 坐标是有限逻辑像素；活动区域由 move 或配置入口另外限制。
        self.x = finite_number(self.x, "actor.x")
        # 纵坐标采用同样的数值边界，不接受布尔或非数字值。
        self.y = finite_number(self.y, "actor.y")
        # 当前只支持四向朝向，未知字符串不能进入动画查询。
        if self.direction not in ("down", "up", "left", "right"):
            # 错误朝向不擅自回退为下方，保留配置问题。
            raise ValueError("Actor direction must identify one of four directions")
        # 移动标记必须是真实布尔值，数字不作为隐式开关。
        if not isinstance(self.moving, bool):
            # 保持状态字段的类型契约明确。
            raise ValueError("Actor moving state must be a boolean")
        # 行走计时以非负秒数表示，避免初始动画倒放或非有限索引。
        self.phase = finite_number(self.phase, "actor.phase")
        # 已经经过的时间不能为负，但合法零值保持不变。
        if self.phase < 0:
            # 不通过绝对值或默认值掩盖错误初态。
            raise ValueError("Actor phase must be nonnegative")

    # 按方向、每秒速率和帧时长推进位置，斜向输入先归一化再夹紧活动边界。
    # dt 为非负秒数、speed 为非负逻辑像素/秒；非法数值或边界抛出 ValueError。
    def move(
        # 操作当前角色自身的运动状态。
        self,
        # 横向输入为任意有限数值，正值向右、负值向左。
        dx: float,
        # 纵向输入为任意有限数值，正值向下、负值向上。
        dy: float,
        # 当前需要处理的非负模拟秒数。
        dt: float,
        # 当前位置每秒移动的逻辑像素数，零速用于明确停止。
        speed: float,
        # 左、上、右、下四条活动边界采用逻辑像素。
        bounds: Sequence[float],
    ) -> None:
        # 逐项校验方向与时间，拒绝布尔值、NaN 和无穷。
        horizontal = finite_number(dx, "dx")
        # 纵向方向与横向方向采用相同的有限数值要求。
        vertical = finite_number(dy, "dy")
        # 帧时长只接受有限值，不在底层运动接口里猜测缺失时长。
        duration_seconds = finite_number(dt, "dt")
        # 每秒速度同样先转换成经过校验的实际数值。
        speed_pixels_per_second = finite_number(speed, "speed")
        # 负时间或负速度会倒放运动，调用方必须明确纠正输入。
        if duration_seconds < 0 or speed_pixels_per_second < 0:
            # 提前终止，保证错误调用不会部分修改角色状态。
            raise ValueError("Movement duration and speed must be nonnegative")
        # 将四边转换为有序的独立元组，后面只需读取合法边界。
        left, top, right, bottom = movement_bounds(bounds)
        # 根据输入计算方向长度，归一化后横走与斜走的速度相同。
        direction_length = math.hypot(horizontal, vertical)
        # 两个合法但极大分量的长度也可能溢出，先等比缩小再归一化。
        if not math.isfinite(direction_length):
            # 以最大轴缩放可保留方向比例，不会将向量错误归一化成零。
            maximum_component = max(abs(horizontal), abs(vertical))
            # 缩放后的两个分量都位于正负一内，平方和可以安全计算。
            horizontal, vertical = horizontal / maximum_component, vertical / maximum_component
            # 重新求安全长度，后续与普通方向采用完全相同的归一化规则。
            direction_length = math.hypot(horizontal, vertical)
        # 零方向明确表示停止输入，而不是保持上一帧的运动方向。
        self.moving = direction_length > 0
        # 停止输入不应执行除法，也不应继续累计行走动画时间。
        if not self.moving:
            # 下次重新走路时从当前方向的动画周期开始。
            self.phase = 0.0
            # 当前帧没有位移，运动接口到此结束。
            return
        # 除以向量长度，把任意方向输入转换成单位方向。
        horizontal, vertical = horizontal / direction_length, vertical / direction_length
        # 横向占比较大时使用左右素材，位置仍保留纵向分量。
        if abs(horizontal) > abs(vertical):
            # 横向正值朝右，负值朝左。
            self.direction = "right" if horizontal > 0 else "left"
        # 纵向占比较大或两轴相等时延续原来的上下优先规则。
        else:
            # 屏幕纵向正值向下，负值向上。
            self.direction = "down" if vertical > 0 else "up"
        # 保存移动前位置，用夹紧后的真实位移判断是否仍在行走。
        previous_x, previous_y = self.x, self.y
        # 方向乘每秒速率再乘秒数，得到本帧应增加的横向距离。
        self.x = max(left, min(right, self.x + horizontal * speed_pixels_per_second * duration_seconds))
        # 纵向采用同样的位移公式，并限制在上下活动边界内。
        self.y = max(top, min(bottom, self.y + vertical * speed_pixels_per_second * duration_seconds))
        # 贴墙后没有真实位移时停止动画，不能把按键输入当成移动事实。
        self.moving = math.hypot(self.x - previous_x, self.y - previous_y) > MOVEMENT_EPSILON_PIXELS
        # 只有真实移动才累计行走秒数，否则将动画恢复到待机状态。
        self.phase = self.phase + duration_seconds if self.moving else 0.0

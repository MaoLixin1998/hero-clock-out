"""闪身技能的运动阶段与两次喘息计时，不持有角色或绘图资源。"""

# 数学库检查由距离和秒数换算的速率是否仍为有限值。
import math

# 技能参数和更新秒数沿用模型的严格数值契约。
from hero_game.model.numeric import finite_number

# 阶段边界吸收累计时间的浮点尾差，不按帧数计算动作。
PHASE_EPSILON_SECONDS = 1e-9
# 两次喘息属于技能恢复规则，不由绘制器决定次数。
BREATH_COUNT = 2


# Game组合此对象；技能独占阶段、阶段秒数和本次锁定方向。
class DashSkill:
    # 距离为逻辑像素，两个阶段时长为正秒数，拒绝过小或溢出的配置。
    def __init__(self, distance: float, dash_seconds: float, recovery_seconds: float) -> None:
        # 参数先校验，错误配置不会生成半初始化技能。
        distance = finite_number(distance, "dashDistance")
        # 闪身时长参与速率除法。
        self._dash_seconds = finite_number(dash_seconds, "dashSeconds")
        # 恢复时长平均分给两次喘息。
        self._recovery_seconds = finite_number(recovery_seconds, "dashRecoverySeconds")
        # 计时必须明显大于浮点边界容差，保证切片能够前进。
        if distance <= 0 or min(self._dash_seconds, self._recovery_seconds) < 1e-6:
            # 非法数值不能通过夹紧或默认值掩盖。
            raise ValueError("Dash distance must be positive and durations at least one microsecond")
        # 距离除以秒数得到闪身期间的实际速率。
        self._speed = distance / self._dash_seconds
        # 两个有限数相除仍可能溢出，提前拒绝无穷速率。
        if not math.isfinite(self._speed):
            # 防止角色坐标被非法位移污染。
            raise ValueError("Dash speed must be finite")
        # 新技能从可触发状态开始。
        self._phase = "ready"
        # 秒数只属于当前阶段，每次切换归零。
        self._elapsed_seconds = 0.0
        # 尚未触发时没有锁定的运动方向。
        self._direction = (0.0, 0.0)

    # 触发一次闪身；忙碌时返回False，方向必须是有限的非零向量。
    def start(self, dx: float, dy: float) -> bool:
        # 横向数值在任何状态下都校验。
        horizontal = finite_number(dx, "dash.dx")
        # 纵向数值采用同一契约。
        vertical = finite_number(dy, "dash.dy")
        # 静止方向没有可执行的闪身，调用方应传入当前朝向。
        if horizontal == 0 and vertical == 0:
            # 错误输入不修改原技能阶段。
            raise ValueError("Dash direction must be nonzero")
        # 闪身和喘息期间不允许重新触发。
        if self._phase != "ready":
            # 不重置已经进行的动作。
            return False
        # 保存本次方向，后续方向键不会在闪身途中转弯。
        self._direction = (horizontal, vertical)
        # 进入高速运动阶段。
        self._phase = "dashing"
        # 新动作从零秒开始。
        self._elapsed_seconds = 0.0
        # 返回真实触发结果供输入层或外部用例查询。
        return True

    # 提供当前段的方向与速率，普通阶段沿用输入，喘息期间完全停止。
    def motion(self, dx: float, dy: float, normal_speed: float) -> tuple[float, float, float]:
        # 普通输入也在此公开接口守住有限数值边界。
        horizontal = finite_number(dx, "dash.dx")
        # 两轴都不能因当前阶段未使用而隐藏错误。
        vertical = finite_number(dy, "dash.dy")
        # 普通速率必须是非负有限逻辑像素每秒。
        speed = finite_number(normal_speed, "normal_speed")
        # 负速率不擅自转换为反向运动。
        if speed < 0:
            # 查询失败不改变技能状态。
            raise ValueError("Normal movement speed must be nonnegative")
        # 只有闪身阶段使用锁定方向与技能速率。
        if self._phase == "dashing":
            # Actor负责最终归一化与墙面夹紧。
            return *self._direction, self._speed
        # 喘息不能用方向键取消或继续行走。
        if self._phase == "recovering":
            # 明确零速和零方向，角色行走动画也停止。
            return 0.0, 0.0, 0.0
        # 已恢复时立即使用仍按住的方向键。
        return horizontal, vertical, speed

    # 消耗至多一个阶段的有效秒数；Game先在阶段边界切分世界更新。
    def advance(self, dt: float) -> None:
        # 更新接口拒绝非有限或负时长。
        duration = finite_number(dt, "dash.dt")
        # 不允许倒放或越过阶段边界而丢掉中途的追击时间。
        if duration < 0 or duration > self.seconds_until_boundary + PHASE_EPSILON_SECONDS:
            # 保持当前技能状态不变，报告调用契约错误。
            raise ValueError("Dash advance must stay within the current phase")
        # 可触发状态没有需要累计的动作秒数。
        if self._phase == "ready":
            # 普通移动时间不占用下一次技能。
            return
        # 当前段只累计真实模拟过的时间。
        self._elapsed_seconds += duration
        # 剩余时间大于容差时继续当前动作。
        if self.seconds_until_boundary > PHASE_EPSILON_SECONDS:
            # 不提前转入喘息或恢复移动。
            return
        # 闪身结束后进入喘息，喘息结束后恢复可触发状态。
        self._phase = "recovering" if self._phase == "dashing" else "ready"
        # 新阶段拥有独立的零起点计时。
        self._elapsed_seconds = 0.0

    # 阶段字符串只读，绘制器不能通过赋值跳过恢复。
    @property
    def phase(self) -> str:
        # 唯一阶段状态由技能持有。
        return self._phase

    # 当前运动段最多可推进的秒数，ready没有额外切片边界。
    @property
    def seconds_until_boundary(self) -> float:
        # 普通移动由追逐自身的其他边界限制。
        if self._phase == "ready":
            # 无穷只用作min的上限，不进入位置或时间状态。
            return math.inf
        # 根据当前阶段选择完整时长。
        total = self._dash_seconds if self._phase == "dashing" else self._recovery_seconds
        # 防止浮点尾差返回负剩余时间。
        return max(0.0, total - self._elapsed_seconds)

    # 恢复进度从零到一，绘制可据此同步两次喘息。
    @property
    def recovery_progress(self) -> float:
        # 非恢复阶段没有喘息动作。
        if self._phase != "recovering":
            # 普通角色帧保持原样。
            return 0.0
        # 两端夹紧保证绘图不会超出预设姿态。
        return min(1.0, self._elapsed_seconds / self._recovery_seconds)

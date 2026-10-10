"""成功后的单向过门与安全门外状态，不参与追逐碰撞。"""

# 演出角色独立复制，不能改动胜负判定时的真实角色快照。
from copy import copy

# 角色只保存逻辑坐标与步态，核心不依赖绘图框架。
from hero_game.model.actor import Actor
# 秒数入口拒绝非有限数，避免结局阶段永远无法结束。
from hero_game.model.numeric import finite_number, movement_bounds

# 完整过门保留可见步态，避免成功时直接消失。
CROSSING_SECONDS = 1.4
# 门外向右走完后保留短暂空景，完成离开公司的结局。
OUTSIDE_WALK_SECONDS = 6.0
# 光照从夕阳过渡到夜晚，角色离画后仍继续到完整夜景。
DUSK_SECONDS = 7.0
# 秒数相加会有浮点舍入，十亿分之一秒内的尾差视为完成。
FINISH_EPSILON_SECONDS = 1e-9
# 角色中心越过门框后，整个身体才能被门框遮挡。
PORTAL_CLEARANCE_PIXELS = 40
# 门外起点位于左侧唯一出口的台阶，坐标采用脚底锚点。
OUTSIDE_START = (84.0, 232.0)
# 64像素角色的左边缘也要越过640像素画布，才算完全离画。
OUTSIDE_END = (680.0, 240.0)


# 只在真实成功后启动，独占结局角色、阶段与秒数。
class EndingSequence:
    # 新局没有结局角色，也不保存上一局的阶段。
    def __init__(self) -> None:
        # inactive明确区别于正在跨门或门外行走。
        self._phase = "inactive"
        # 已经过的结局秒数不计入追逐时钟。
        self._elapsed_seconds = 0.0
        # 角色在成功触发时才复制。
        self._actor: Actor | None = None
        # 起终点仅供成功后的轨迹插值使用。
        self._start = (0.0, 0.0)
        # 门框右侧的终点允许离开办公室活动边界。
        self._target = (0.0, 0.0)

    # 从真实门前位置开始跨门，door_bounds采用逻辑画布的四条门框边。
    def start(self, actor: Actor, door_bounds: tuple[float, float, float, float]) -> None:
        # 公开启动接口拒绝错误角色类型，不创建部分演出状态。
        if not isinstance(actor, Actor):
            # 门前状态必须来自真实角色模型。
            raise TypeError("Ending actor must be an Actor")
        # 四边先确认有限且有序，再修改当前组件。
        checked_door = movement_bounds(door_bounds)
        # 复制角色完整步态，成功不导致脚步突然归零。
        self._actor = copy(actor)
        # 起点使用碰撞判定提交后的真实脚底位置。
        self._start = (actor.x, actor.y)
        # 穿过门框后完全遮挡，再切换到安全门外。
        self._target = (checked_door[2] + PORTAL_CLEARANCE_PIXELS, checked_door[3])
        # 每次成功从跨门阶段开始。
        self._phase = "crossing"
        # 新事件不继承前一次结局时间。
        self._elapsed_seconds = 0.0

    # 推进独立演出，忽略玩家方向；暂停由Game在调用前统一处理。
    def update(self, dt: float) -> None:
        # 即使结局未启动也校验外部时间契约。
        duration = finite_number(dt, "ending dt")
        # 负时间不允许倒放状态。
        if duration < 0:
            # 错误发生前不修改任何阶段。
            raise ValueError("Ending duration must be nonnegative")
        # 未开始与已结束时不继续推进角色。
        if self._actor is None or self._phase == "complete":
            # 查询绘制或重复更新不会重启结局。
            return
        # 夜景完整出现后停止累计，终态保持确定。
        self._elapsed_seconds = min(CROSSING_SECONDS + DUSK_SECONDS, self._elapsed_seconds + duration)
        # 固定帧率完整运行七秒时不能因舍入余量永远留在outside。
        if CROSSING_SECONDS + DUSK_SECONDS - self._elapsed_seconds < FINISH_EPSILON_SECONDS:
            # 吸收纯数值尾差，不提前跳过任何可见动画帧。
            self._elapsed_seconds = CROSSING_SECONDS + DUSK_SECONDS
        # 过门完成前沿真实起点到门洞方向推进。
        if self._elapsed_seconds < CROSSING_SECONDS:
            # 归一化进度只控制独立演出，不更改真实追逐坐标。
            progress = self._elapsed_seconds / CROSSING_SECONDS
            # 横向逐渐走出门框，角色不会突然消失。
            self._actor.x = self._start[0] + (self._target[0] - self._start[0]) * progress
            # 脚底自然收拢到门洞底部。
            self._actor.y = self._start[1] + (self._target[1] - self._start[1]) * progress
            # 出口在右侧，整个跨门过程使用向右步态。
            self._actor.direction = "right"
            # 实际位移期间播放已有行走帧。
            self._actor.moving = True
            # 与真实游戏相同，以秒选取步态帧。
            self._actor.phase += duration
            # 尚未跨出时保持办公室场景。
            return
        # 门外的局部秒数与办公室跨门时间分开计算。
        outside_seconds = self._elapsed_seconds - CROSSING_SECONDS
        # 行走进度按秒夹紧，跨帧更新也会得到同一终点。
        progress = min(1.0, outside_seconds / OUTSIDE_WALK_SECONDS)
        # 从左侧门口持续走向画布右侧，不能跳到中央待机。
        self._actor.x = OUTSIDE_START[0] + (OUTSIDE_END[0] - OUTSIDE_START[0]) * progress
        # 最初半秒走下台阶，随后保持同一滨江步道水平线。
        self._actor.y = OUTSIDE_START[1] + (OUTSIDE_END[1] - OUTSIDE_START[1]) * min(1.0, outside_seconds / 0.5)
        # 整个门外路段面向右侧，不再转向屏幕显示对白。
        self._actor.direction = "right"
        # 完全离画前继续播放已有四向行走帧。
        self._actor.moving = progress < 1.0
        # 绝对阶段秒数选帧，避免不同帧率累计误差改变脚步节奏。
        self._actor.phase = min(outside_seconds, OUTSIDE_WALK_SECONDS)
        # 行走结束后夜景继续完成，最后留下稳定空景。
        self._phase = "complete" if self._elapsed_seconds >= CROSSING_SECONDS + DUSK_SECONDS else "outside"

    # 查询当前单向阶段，不允许绘制器改写状态。
    @property
    def phase(self) -> str:
        # 阶段由当前序列独占。
        return self._phase

    # 查询已过去的结局秒数，单位不同于追逐elapsed。
    @property
    def elapsed_seconds(self) -> float:
        # 返回纯数值不产生更新。
        return self._elapsed_seconds

    # 只读的光照进度独立于资源，0代表夕阳、1代表完整夜晚。
    @property
    def night_progress(self) -> float:
        # 未跨门前固定夕阳，门外按合法模拟秒数逐渐进入夜晚。
        return max(0.0, min(1.0, (self._elapsed_seconds - CROSSING_SECONDS) / DUSK_SECONDS))

    # 返回角色快照，界面不能通过查询修改模型中的演出角色。
    @property
    def actor(self) -> Actor | None:
        # Actor只含标量字段，浅复制足以隔离可变状态。
        return None if self._actor is None else copy(self._actor)

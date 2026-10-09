"""正式游戏开场的距离触发与登场状态；不包含拍摄或定格模式。"""

# 数学库用真实坐标差累计距离，贴墙输入不能冒充行走。
import math
# Mapping 声明规则只需读取，不要求调用方提供某种字典实现。
from collections.abc import Mapping
# 深拷贝隔离嵌套配置，外部改列表不会改变正在进行的演出。
from copy import deepcopy
# Any 只用于经过配置模块校验的 JSON 结构边界。
from typing import Any

# 角色模型负责真实位移，本类只决定阶段顺序和登场位置。
from hero_game.model.actor import Actor
# 共享数值与边界校验，公开更新入口拒绝非法时间和位置。
from hero_game.model.numeric import finite_number, movement_bounds

# 时间与距离比较的微小容差只吸收浮点累计误差，不改变游戏节拍。
SEQUENCE_EPSILON = 1e-9
# 四向单位向量与朝向 ID 对应，坐标系向右、向下为正。
DIRECTION_VECTORS = {"down": (0, 1), "up": (0, -1), "left": (-1, 0), "right": (1, 0)}
# 面对面时两角色朝向相反，与显示姓名或台词正文无关。
OPPOSITE_DIRECTIONS = {"down": "up", "up": "down", "left": "right", "right": "left"}


# 独占开场阶段、累计距离和跳跃时间；Game 根据一次性事件启动正式对话。
# 更新只操作传入的角色，不读取本机文件、不播放声音，也不创建绘制资源。
class OpeningSequence:
    # 保存独立的正式规则并初始化开场；play_intro=False 直接处于完成状态。
    def __init__(self, rules: Mapping[str, Any], play_intro: bool = True) -> None:
        # 规则由应用配置入口校验，本对象持有自己的嵌套副本。
        self._rules = deepcopy(dict(rules))
        # 将活动边界转换成不可变四元组，后面只读取合法边界。
        self._bounds = movement_bounds(self._rules["movementBounds"])
        # 首次状态和重开使用同一条初始化路径，避免字段遗漏。
        self.reset(play_intro)

    # 清除当前开场的所有计时与事件状态，不修改 Game 的累计落地事件编号。
    def reset(self, play_intro: bool = True) -> None:
        # 开场开关必须是明确布尔值，不能把任意非空对象当成模式选择。
        if not isinstance(play_intro, bool):
            # 错误发生在状态修改前，当前合法演出不会被部分重置。
            raise ValueError("play_intro must be a boolean")
        # 正式开场先走路；重试跳过演出后直接进入正常游戏。
        self._phase = "walk" if play_intro else "done"
        # 只累计经过边界夹紧后的真实移动距离，单位为逻辑像素。
        self._walk_distance = 0.0
        # 史莱姆跳出与回弹的累计时间，单位为秒。
        self._entrance_elapsed = 0.0
        # 当前演出尚未发出落地事件，跨过落地边界后只切换一次。
        self._entrance_landed = False
        # 待机呼吸使用自己的秒数，不消耗追击时间或起跑缓冲。
        self._opening_elapsed = 0.0

    # 查询当前阶段 ID，绘制器据此选择走路、跳出或正式游戏画面。
    # 属性只返回不可变字符串，不向外提供内部状态的修改入口。
    @property
    def phase(self) -> str:
        # 完成阶段使用稳定 ID，台词正文不会参与状态判断。
        return self._phase

    # 查询真实累计行走距离，单位为逻辑像素。
    # 属性查询不会推进角色、计时或任何事件。
    @property
    def walk_distance(self) -> float:
        # 数值快照可供画面和测试读取，无需复制可变容器。
        return self._walk_distance

    # 查询跳出与回弹累计秒数，绘制层据此计算高度和缩放。
    # 演出时间由本对象独占，绘制器不能通过查询修改它。
    @property
    def entrance_elapsed(self) -> float:
        # 返回当前合法时间，不在查询时进行时间更新。
        return self._entrance_elapsed

    # 查询本轮是否已跨过落地边界，防止声音重复触发。
    # 只读布尔值表达当前演出事实。
    @property
    def entrance_landed(self) -> bool:
        # 重开后会恢复为 False，但 Game 的累计事件编号仍继续递增。
        return self._entrance_landed

    # 查询开场呼吸累计秒数，与游戏有效时间分别计时。
    # 属性不加载资源，也不隐藏任何状态更新。
    @property
    def opening_elapsed(self) -> float:
        # 返回可直接用于绘制呼吸周期的秒数。
        return self._opening_elapsed

    # 查询是否仍处于正式开场，完成后由 Game 接管对话与追逐。
    # 稳定阶段 ID 是唯一来源，不另存容易失步的活动开关。
    @property
    def active(self) -> bool:
        # walk 和 entrance 都属于开场，done 表示已移交正常游戏。
        return self._phase != "done"

    # 按勇者当下位置与朝向选择史莱姆的完整落点，前方不足时尝试转身和侧面。
    # hero/slime 由 Game 持有；本方法只修改落点与面对面的朝向，非法位置抛 ValueError。
    def place_slime_in_front(self, hero: Actor, slime: Actor) -> None:
        # 校验实际角色坐标，外部测试或调试改状态也不能把 NaN 带入几何选择。
        hero_x = finite_number(hero.x, "hero.x")
        # 纵坐标采用同样的合法值要求。
        hero_y = finite_number(hero.y, "hero.y")
        # 拆出四边，候选落点必须完整落在活动区域内。
        left, top, right, bottom = self._bounds
        # 勇者自身必须已在活动范围中，不能为修复坏状态而悄悄瞬移。
        if not (left <= hero_x <= right and top <= hero_y <= bottom):
            # 明确指出位置边界错误，保留当前双方坐标不变。
            raise ValueError("Hero must be inside movement bounds")
        # 四向素材只接受已知方向，错误字符串不应该变成字典 KeyError。
        if hero.direction not in DIRECTION_VECTORS:
            # 给出朝向输入的稳定错误含义，不读取或输出剧情正文。
            raise ValueError("Hero direction must identify one of four directions")
        # 优先使用最后走路朝向，保持角色当下动作和登场位置一致。
        facing = hero.direction
        # 前方不足时尝试背面；其余方向保持原来的下上左右候选顺序。
        candidates = [facing, OPPOSITE_DIRECTIONS[facing]]
        # 只补尚未尝试的侧面，不重复检查原方向和反方向。
        for direction in DIRECTION_VECTORS:
            # 确保侧面候选与已加入的前后方向不同。
            if direction not in candidates:
                # 保存侧面方向，之后按固定顺序选择首个合法落点。
                candidates.append(direction)
        # 距离来自正式游戏规则，单位与脚底坐标同为逻辑像素。
        entrance_distance = self._rules["slimeEntranceDistance"]
        # 按前方、背面、侧面的优先顺序寻找完整空间。
        for direction in candidates:
            # 当前候选向量的分量只取零或正负一。
            horizontal, vertical = DIRECTION_VECTORS[direction]
            # 以勇者实时横坐标为基准计算落点，不使用房间中央固定位置。
            landing_x = hero_x + horizontal * entrance_distance
            # 纵向同样使用实时脚底位置和规定间距。
            landing_y = hero_y + vertical * entrance_distance
            # 完整检查落点，不用边界夹紧把规定间距压缩成贴身重叠。
            if left <= landing_x <= right and top <= landing_y <= bottom:
                # 合法落点找到后才更新史莱姆位置，错误候选不改状态。
                slime.x, slime.y = landing_x, landing_y
                # 临墙转向只改变勇者朝向，不修改勇者的脚底位置。
                hero.direction = direction
                # 史莱姆朝向勇者，落稳后两角色面对面。
                slime.direction = OPPOSITE_DIRECTIONS[direction]
                # 采用第一个可用方向后结束，不覆盖为后续候选。
                return
        # 合法配置保证至少一个方向可放，走到这里说明参数或状态被破坏。
        raise ValueError("Entrance distance cannot fit inside movement bounds")

    # 推进开场并返回 (本次是否落地, 本次是否完成)；事件仅在跨过对应边界时为 True。
    # dt 为非负秒数，dx/dy 为运动方向；同一帧跨阶段时保留剩余时间处理跳跃。
    def update(
        # 本对象独占演出阶段和计时。
        self,
        # 非负模拟时长由 Game 先限制到最大帧间隔。
        dt: float,
        # 横向移动输入只在 walk 阶段生效。
        dx: float,
        # 纵向移动输入与正常游戏使用同一套归一化规则。
        dy: float,
        # 勇者由 Game 持有，本对象在开场中推进其位移。
        hero: Actor,
        # 史莱姆的世界位置在落点确定后冻结，跳跃只由绘制层表现。
        slime: Actor,
    ) -> tuple[bool, bool]:
        # 更新入口拒绝非有限时间，避免演出永久卡在错误阶段。
        duration_seconds = finite_number(dt, "dt")
        # 开场本身不倒放，负值须由外层显式处理。
        if duration_seconds < 0:
            # 错误时不修改演出或角色状态。
            raise ValueError("Opening duration must be nonnegative")
        # 已完成的开场不再推进呼吸时间，也不会重复发出完成事件。
        if not self.active:
            # 两种事件都为假，Game 不需要补发对话或声音。
            return False, False
        # 呼吸时间独立推进，原地等待不会因此增加真实步数。
        self._opening_elapsed += duration_seconds
        # 记录本次是否跨过落地边界，不能由查询过程产生事件。
        did_land = False
        # 剩余秒数让低帧率也能准确拆到行走终点与跳跃时刻。
        remaining_seconds = duration_seconds
        # 只处理当前开场剩余部分，完成后不偷跑追击或文字。
        while remaining_seconds > SEQUENCE_EPSILON and self.active:
            # 行走阶段只移动勇者，史莱姆仍保持隐藏。
            if self._phase == "walk":
                # 步数估计乘每步像素，得到实际触发所需的路径长度。
                target_distance = self._rules["introWalkSteps"] * self._rules["introStepPixels"]
                # 最多走到精确触发点，低帧率不能让勇者多走一截。
                step_seconds = min(
                    # 当前帧尚未处理的时间是第一个上限。
                    remaining_seconds,
                    # 剩余逻辑像素除每秒速度得到到达触发点所需秒数。
                    max(0.0, target_distance - self._walk_distance) / self._rules["heroSpeed"],
                )
                # 保存移动前真实坐标，贴墙后未发生的位移不能计入距离。
                before_x, before_y = hero.x, hero.y
                # 复用正式运动接口，斜向速度、朝向和边界完全一致。
                hero.move(dx, dy, step_seconds, self._rules["heroSpeed"], self._bounds)
                # 累加实际位移长度，而不是方向键数量或等待时间。
                self._walk_distance += math.hypot(hero.x - before_x, hero.y - before_y)
                # 从当前帧剩余时间里扣掉这段行走，后续可推进跳出。
                remaining_seconds -= step_seconds
                # 达到规定距离时才切换阶段，微小容差仅吸收浮点残差。
                if self._walk_distance >= target_distance - SEQUENCE_EPSILON:
                    # 对齐精确触发距离，方便不同帧率得到一致结果。
                    self._walk_distance = target_distance
                    # 此刻根据勇者位置与朝向选择落点，不提前写死世界坐标。
                    self.place_slime_in_front(hero, slime)
                    # 下一段进入跳出，绘制层现在才显示史莱姆。
                    self._phase = "entrance"
                    # 勇者停下看登场，不延续持续按键造成的行走动画。
                    hero.move(0.0, 0.0, 0.0, 0.0, self._bounds)
                # 未走够时结束本帧，原地等待或贴墙不能在循环中强行补距离。
                else:
                    # 当前只可能没有事件，直接交还 Game 等下一次输入。
                    return did_land, False
            # 登场阶段只推进跳跃与回弹，不改变双方碰撞坐标。
            else:
                # 正式规则规定完整演出时长，包括空中和落地回弹。
                entrance_duration = self._rules["slimeEntranceSeconds"]
                # 只处理到演出结束边界，完成后保留完整起跑缓冲。
                step_seconds = min(remaining_seconds, entrance_duration - self._entrance_elapsed)
                # 推进独立演出时间，绘制器使用此值计算身体高度。
                self._entrance_elapsed += step_seconds
                # 已处理的时间不在同一帧内重复使用。
                remaining_seconds -= step_seconds
                # 首次跨过跳跃结束才产生落地事件，回弹期间不重复产生。
                if not self._entrance_landed and self._entrance_elapsed >= self._rules["slimeJumpSeconds"] - SEQUENCE_EPSILON:
                    # 锁定本轮已落地状态，重开前不会再次触发。
                    self._entrance_landed = True
                    # 将一次性事件交给 Game 维护累计事件编号。
                    did_land = True
                # 回弹完成后才允许正式对话，动作期间没有台词框遮挡。
                if self._entrance_elapsed >= entrance_duration - SEQUENCE_EPSILON:
                    # 对齐最后时刻，身体恢复正常高度与缩放。
                    self._entrance_elapsed = entrance_duration
                    # 正式开场只有完成态，不混入拍摄定格或隐藏分支。
                    self._phase = "done"
                    # 本次完成只报告一次，后续更新已在入口返回无事件。
                    return did_land, True
        # 本帧尚未完成演出，只可能刚落地或没有事件。
        return did_land, False

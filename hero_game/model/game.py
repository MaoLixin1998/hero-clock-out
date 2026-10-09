"""正式游戏状态协调：开场、对话、计时追逐与下班结果分别推进。"""

# Mapping 表达外部注入的配置只需读取，不要求某种可变字典实现。
from collections.abc import Mapping
# 深拷贝隔离清单和规则，防止实例之间共享嵌套状态。
from copy import copy, deepcopy
# Any 只用于经过明确校验的 JSON 配置边界。
from typing import Any

# 角色模型只负责归一化位移与边界夹紧。
from hero_game.model.actor import Actor
# 连续接触与门槛检测提供首次进入比例，用真实先后顺序决定结果。
from hero_game.model.collision import capture_contact_fraction, rectangle_entry_fraction
# 对话播放器独占正文与逐字状态，不控制追逐。
from hero_game.model.dialogue import Dialogue
# 成功后的跨门与门外行走由独立组件持有，不恢复追逐。
from hero_game.model.ending_sequence import EndingSequence
# 数值入口先拒绝非有限值，防止时间循环失效。
from hero_game.model.numeric import finite_number, movement_bounds
# 开场组件独占距离触发和跳跃阶段，核心不包含拍摄模式分支。
from hero_game.model.opening_sequence import OpeningSequence
# 纯规则契约只校验内存数据，模型不依赖JSON或文件读取适配器。
from hero_game.model.rules import MINUTES_PER_DAY, parse_clock_minutes, validate_game_rules

# 每次更新最多处理 0.05 秒，限制卡顿后的单次位移并保持原游戏节奏。
MAX_UPDATE_SECONDS = 0.05
# 时间切片微小容差吸收浮点残差，避免反应边界出现零时长循环。
TIME_EPSILON_SECONDS = 1e-9


# 持有一局的角色、追逐计时和结果，组合开场与对话组件，不创建窗口或资源。
# 正式游戏规则和正文必须显式注入，默认文件读取由应用组装层完成。
class Game:
    # 创建独立游戏模型；manifest 仅兼容外部清单查询，缺省为空且不读资源文件。
    def __init__(
        # 当前实例是所有本局运行状态的持有者。
        self,
        # 正式规则由应用或受控测试注入，模型只负责内存校验。
        rules: Mapping[str, Any],
        # 对话数据必须明确提供，核心不会为了补默认值读取磁盘。
        dialogue_data: Mapping[str, Any],
        # 可选资源清单仅兼容查询，模型不加载其中引用的媒体。
        manifest: Mapping[str, Any] | None = None,
        # 首次启动通常播放开场，重试可明确跳过。
        play_intro: bool = True,
    ) -> None:
        # 显式资源清单必须是映射，不把任意键值序列偷偷转换成配置。
        if manifest is not None and not isinstance(manifest, Mapping):
            # 在保存任何本局状态前指出接口类型错误。
            raise TypeError("Game manifest must be a mapping")
        # 清单缺省为空字典，不能因传入合法空字典而读本机素材。
        self._manifest = deepcopy(dict({} if manifest is None else manifest))
        # 纯规则入口校验类型、范围、有限性，并取得独立嵌套副本。
        self._rules = validate_game_rules(rules)
        # 角色共用不可变边界，外部规则列表变化不能改变当前场地。
        self._bounds = movement_bounds(self._rules["movementBounds"])
        # 出口门槛使用同一逻辑脚底坐标，绘制和判定只查询此唯一来源。
        self._exit_bounds = tuple(self._rules["exitBounds"])
        # 游戏钟从正式开始时间推进，不读取电脑的真实系统时间。
        self._clock_start_minutes = parse_clock_minutes(self._rules["clockText"], "clockText")
        # 跨午夜仍按向前的分钟差计算完整一局时长。
        shift_minutes = (parse_clock_minutes(self._rules["shiftEndText"], "shiftEndText") - self._clock_start_minutes) % MINUTES_PER_DAY
        # 有效追逐秒数是时钟和门状态共同使用的唯一计时。
        self._shift_duration_seconds = shift_minutes * self._rules["gameSecondsPerMinute"]
        # 对话实例复制并校验显式正文，不从模型内部寻找默认文件。
        self.dialogue = Dialogue(dialogue_data)
        # 落地编号属于整个 Game 生命周期，重开一局也不归零以免漏播事件。
        self.landing_serial = 0
        # 初始化所有本局状态，首次和重开共用同一条路径。
        self.reset(play_intro)

    # 查询兼容资源清单快照，核心模型不加载清单引用的图片或声音。
    # 嵌套字段复制后返回，界面不能通过它改写模型持有的数据。
    @property
    def manifest(self) -> dict[str, Any]:
        # 清单读取只有内存复制，没有隐式磁盘访问。
        return deepcopy(self._manifest)

    # 查询当前校验规则的独立快照，修改结果不会改变正在运行的一局。
    # 游戏内部只使用单一 _rules 来源，不从界面配置反推状态。
    @property
    def rules(self) -> dict[str, Any]:
        # 嵌套列表也分离，避免浅拷贝造成不同游戏相互影响。
        return deepcopy(self._rules)

    # 查询不可变的左、上、右、下活动边界，单位为逻辑像素。
    # 边界由正式规则校验后建立，运行中不由绘制器修改。
    @property
    def bounds(self) -> tuple[float, float, float, float]:
        # 元组可直接共享查询，不泄露可变配置列表。
        return self._bounds

    # 重置当前一局；默认重试直接进入追逐，不重复正式开场与对话。
    # play_intro 必须是布尔值，错误时保持原一局状态不变。
    def reset(self, play_intro: bool = False) -> None:
        # 模式选择必须明确，不能以任意对象的真假决定是否播放开场。
        if not isinstance(play_intro, bool):
            # 在创建角色或清空计时前报告输入错误。
            raise ValueError("play_intro must be a boolean")
        # 根据正式出生点创建勇者，预览坐标不进入正常游戏规则。
        self.hero = Actor("hero", *self._rules["heroSpawn"])
        # 重试从正式敌人出生点开始，首次开场会在触发时重新选落点。
        self.slime = Actor("slime", *self._rules["slimeSpawn"])
        # 新局取消暂停，恢复当前阶段的正常更新。
        self.paused = False
        # 清除旧接触结果，只有新的一局可以重新移动。
        self.caught = False
        # 离开成功是独立终态，重开后必须重新等到下班时间。
        self.escaped = False
        # 新局不继承旧结局轨迹或门外停留时间。
        self._ending = EndingSequence()
        # 本局有效追逐秒数归零，开场、对话与暂停不计入此时间。
        self.elapsed = 0.0
        # 恢复完整起跑缓冲，给玩家保留先移动的机会。
        self.start_delay = self._rules["startDelaySeconds"]
        # 首次追逐时立即重新瞄准，不继承上一局的转向倒计时。
        self.retarget_in = 0.0
        # 清除旧目标方向，避免敌人沿上一局方向先走一步。
        self.chase_direction = (0.0, 0.0)
        # 开场组件独占演出状态，正常核心只支持 walk/entrance/done。
        self._opening = OpeningSequence(self._rules, play_intro)
        # 清除上一段尚未结束的正文，但保留对话配置供新事件使用。
        self.dialogue.skip()

    # 把按当前位置选择面前落点委托给正式开场组件，保留旧调用接口。
    # 只改变落点和双方朝向，不移动勇者身体或启动追逐。
    def place_slime_in_front(self) -> None:
        # 传入当前局角色，组件不会创建第二份角色或保存资源引用。
        self._opening.place_slime_in_front(self.hero, self.slime)

    # 推进正式开场并处理一次性落地、完成事件，不消耗追逐计时与起跑缓冲。
    def update_intro(self, dt: float, dx: float, dy: float) -> None:
        # 演出组件返回事件事实，本对象决定如何通知对话和累计落地编号。
        did_land, did_complete = self._opening.update(dt, dx, dy, self.hero, self.slime)
        # 一次更新可能跨过落地边界，累计编号供声音播放器去重。
        if did_land:
            # 重开后编号继续增加，每次真实落地都能被外部检测到。
            self.landing_serial += 1
        # 正式演出完整落稳后才启动配置中的开场对白。
        if did_complete:
            # 本帧不推进文字，下一帧才开始逐字显示。
            self.dialogue.start("intro")

    # 推进一帧游戏；dt 为秒，dx/dy 为有限方向数值，负时间夹零且最大处理 0.05 秒。
    # 暂停、开场、对话、结果、追逐按互斥阶段更新，非有限输入抛 ValueError。
    def update(self, dt: float, dx: float = 0.0, dy: float = 0.0) -> None:
        # 输入先做类型和有限性校验，非法数据不能因暂停状态被隐藏。
        duration_seconds = finite_number(dt, "dt")
        # 横向方向传给开场与追逐同一套运动接口。
        horizontal = finite_number(dx, "dx")
        # 纵向方向同样拒绝布尔值、无穷和 NaN。
        vertical = finite_number(dy, "dy")
        # 暂停连文字和呼吸都冻结，不推进任何当前阶段。
        if self.paused:
            # 不让后台或暂停期间的秒数消耗起跑机会。
            return
        # 负秒数按零处理，卡顿后过大的帧时长不会一次跨过整个房间。
        frame_seconds = max(0.0, min(duration_seconds, MAX_UPDATE_SECONDS))
        # 成功后只推进独立结局，方向输入不会再改变真实角色或敌人。
        if self.escaped:
            # 游戏时钟和追逐快照保持冻结，过场计时独立推进。
            self._ending.update(frame_seconds)
            # 结局不会落回开场、对话或追逐流程。
            return
        # 正式开场先处理真实走路与跳出，此时不能提前追逐。
        if self.opening_active:
            # 把同一方向输入交给正式开场，没有视频隐藏或定格分支。
            self.update_intro(frame_seconds, horizontal, vertical)
            # 开场完成的同一帧仍不推进文字或追击。
            return
        # 对话阶段只推进逐字显示，双方坐标与反应倒计时保持不变。
        if self.dialogue.active:
            # 文字播放器只负责正文，不修改有效游戏时间。
            self.dialogue.update(frame_seconds)
            # 对话更新后直接结束，避免同一帧继续执行移动。
            return
        # 结果状态在对白结束后仍保持冻结，必须明确重开才解除。
        if self.caught or self.escaped:
            # 跳过结果文字不能让玩家自动复活。
            return
        # 正常追逐使用按秒切分的反应周期，保持不同帧率规则一致。
        self._update_chase(frame_seconds, horizontal, vertical)

    # 推进正常追逐并按缓冲、转向边界拆分当前帧，同时检测连续相对接触。
    # 只由 update 在合法追逐阶段调用，不处理对话或开场演出。
    def _update_chase(self, dt: float, dx: float, dy: float) -> None:
        # 保存本帧剩余秒数，跨转向边界时继续处理下一小段。
        remaining_seconds = dt
        # 极小残差不再处理，避免浮点差值造成无意义循环。
        while remaining_seconds > TIME_EPSILON_SECONDS:
            # 起跑等待只冻结敌人，玩家仍可正常移动。
            is_waiting = self.start_delay > TIME_EPSILON_SECONDS
            # 等待阶段最多处理到缓冲结束边界。
            if is_waiting:
                # 剩余等待之后的时间留给下一轮正常追逐。
                step_seconds = min(remaining_seconds, self.start_delay)
            # 缓冲结束后按照敌人反应间隔重新瞄准。
            else:
                # 倒计时耗尽才读取玩家新位置，不让敌人每帧瞬间转向。
                if self.retarget_in <= TIME_EPSILON_SECONDS:
                    # 保存此刻玩家减敌人的方向，直到下一次反应时刻都保持它。
                    self.chase_direction = (self.hero.x - self.slime.x, self.hero.y - self.slime.y)
                    # 重新装满反应间隔，单位为秒而不是帧数。
                    self.retarget_in = self._rules["retargetSeconds"]
                # 一小段不能越过下一次反应时刻，以免低帧率延迟转向。
                step_seconds = min(remaining_seconds, self.retarget_in)
            # 闭门段必须在开门时刻截断，不能把更早经过门口误算为离开。
            if not self.door_open:
                # 当前段至多消耗完剩余上班时间。
                step_seconds = min(step_seconds, self.remaining_shift_seconds)
            # 试算只操作独立的纯角色副本，不把尚未确定的整段移动写入本局。
            hero_end, slime_end = copy(self.hero), copy(self.slime)
            # 保留真实起点，供连续门槛检测和相对接触计算使用。
            hero_start = (self.hero.x, self.hero.y)
            # 相对起点中共同的碰撞中心偏移会抵消。
            before = (self.hero.x - self.slime.x, self.hero.y - self.slime.y)
            # 候选终点遵守与正式移动相同的归一化和墙面边界。
            hero_end.move(dx, dy, step_seconds, self._rules["heroSpeed"], self._bounds)
            # 缓冲期间敌人保持零速，其他时间沿已保存的目标方向前进。
            slime_direction = (0.0, 0.0) if is_waiting else self.chase_direction
            # 单次候选推进只为查询本段最早事件，不修改原角色。
            slime_end.move(*slime_direction, step_seconds, 0.0 if is_waiting else self._rules["slimeSpeed"], self._bounds)
            # 相对终点和起点共同形成双方这一小段的运动轨迹。
            after = (hero_end.x - slime_end.x, hero_end.y - slime_end.y)
            # 起跑保护免除接触，其余时间查询本段首次被抓的比例。
            capture_fraction = None if is_waiting else capture_contact_fraction(before, after, sum(self._rules["collisionRadii"]))
            # 门已打开时检查完整轨迹，包括两端都在门槛外的高速穿越。
            exit_fraction = rectangle_entry_fraction(hero_start, (hero_end.x, hero_end.y), self._exit_bounds) if self.door_open else None
            # 闭门段恰好到点且仍在入口内时，离开只能发生在段末开门时刻。
            if not self.door_open and self.elapsed + step_seconds + TIME_EPSILON_SECONDS >= self._shift_duration_seconds:
                # 用零长度查询确认开门瞬间的脚底确实位于门槛内。
                if rectangle_entry_fraction((hero_end.x, hero_end.y), (hero_end.x, hero_end.y), self._exit_bounds) is not None:
                    # 此前的闭门轨迹不能触发成功。
                    exit_fraction = 1.0
            # 接触与过门同刻时保留被抓结果，其他情况由更早事件决定。
            is_captured = capture_fraction is not None and (exit_fraction is None or capture_fraction * step_seconds <= exit_fraction * step_seconds + TIME_EPSILON_SECONDS)
            # 本段没有事件时处理完整时长，有事件时只推进到它真正发生的位置。
            event_fraction = capture_fraction if is_captured else exit_fraction
            # 比例为零也是有效事件，不能用真假判断把它替换成完整段。
            processed_seconds = step_seconds * (1.0 if event_fraction is None else event_fraction)
            # 正式角色只提交确定处理的时间，不越过已经发生的结果。
            self.hero.move(dx, dy, processed_seconds, self._rules["heroSpeed"], self._bounds)
            # 敌人也推进到同一事件时刻，终态以后不会继续追击。
            self.slime.move(*slime_direction, processed_seconds, 0.0 if is_waiting else self._rules["slimeSpeed"], self._bounds)
            # 起跑等待和反应倒计时只扣除实际发生的秒数。
            if is_waiting:
                # 合法零等待会在下段直接转入追逐。
                self.start_delay = max(0.0, self.start_delay - processed_seconds)
            # 正常追逐只更新本轮重瞄准计时。
            else:
                # 不把结果之后的剩余帧时间计入敌人反应。
                self.retarget_in = max(0.0, self.retarget_in - processed_seconds)
            # 所有正式计时共用这一实际发生的有效游戏秒数。
            self.elapsed += processed_seconds
            # 本帧尚未消费的秒数留给下一次时间边界切片。
            remaining_seconds -= processed_seconds
            # 最早事件是接触时进入失败，跳过文字也不会解除结果。
            if is_captured:
                # 记录接触结果，后续帧即使跳过文字也保持冻结。
                self.caught = True
                # 正文来自正式场景数据，核心只发出稳定事件 ID。
                self.dialogue.start("caught")
                # 接触之后不再消耗本帧剩余时间。
                return
            # 到达开放门槛时结束本局，门外不再继续进行接触判断。
            if exit_fraction is not None:
                # 结果独立于显示文字，绘制器只读取这个事实。
                self.escaped = True
                # 从本次真实门前位置连续跨出，门外不再进行碰撞。
                self._ending.start(self.hero, self.exit_door_bounds)
                # 不把离开之后的时间或移动写入本局。
                return

    # 兼容绘制器的开场阶段查询，唯一状态由 OpeningSequence 持有。
    # 不在 Game 额外复制阶段字符串，避免状态不同步。
    @property
    def intro_phase(self) -> str:
        # 正式阶段只包含 walk、entrance 和 done。
        return self._opening.phase

    # 查询开场是否仍活动，供输入和绘制统一判断。
    # 这里只读组件状态，不隐藏拍摄模式或加载操作。
    @property
    def opening_active(self) -> bool:
        # 完成开场后按对话和追逐状态继续游戏。
        return self._opening.active

    # 查询史莱姆是否已登场；走路阶段保持隐藏，其余正式阶段可见。
    # 可见性从阶段推导，不另存容易遗漏重置的开关。
    @property
    def slime_visible(self) -> bool:
        # 对话、追逐和结果都沿用已登场的角色。
        return self._opening.phase != "walk"

    # 查询正式开场实际累计距离，供绘制与兼容检查读取。
    # 状态由演出组件独占，Game 不保存第二份距离。
    @property
    def walk_distance(self) -> float:
        # 返回逻辑像素数，原地或贴墙都不会增加。
        return self._opening.walk_distance

    # 查询登场累计秒数，绘制器用它计算跳跃高度与回弹。
    # 读取不会推进演出或发出落地事件。
    @property
    def entrance_elapsed(self) -> float:
        # 对齐演出组件的唯一时间来源。
        return self._opening.entrance_elapsed

    # 查询本轮开场是否已落地，累计事件编号仍由 Game 持有。
    # 重开本局会清除此事实但不会把 landing_serial 归零。
    @property
    def entrance_landed(self) -> bool:
        # 返回布尔事实，不播放声音或改变动画。
        return self._opening.entrance_landed

    # 查询开场呼吸秒数，区别于追逐有效时间。
    # 正常游戏完成开场后此计时停止。
    @property
    def opening_elapsed(self) -> float:
        # 组件是唯一持有者，绘制器只读数值。
        return self._opening.opening_elapsed

    # 查询可达门槛的不可变坐标，界面与判定使用相同入口。
    # 左、上、右、下采用角色脚底的逻辑像素坐标。
    @property
    def exit_bounds(self) -> tuple[float, float, float, float]:
        # 元组不泄露内部可变规则列表。
        return self._exit_bounds

    # 查询门框四边，模型轨迹与绘制使用相同的正式布局。
    @property
    def exit_door_bounds(self) -> tuple[float, float, float, float]:
        # 四边元组不泄露可修改的规则列表。
        return tuple(self._rules["exitDoorBounds"])

    # 查询结局阶段，界面不能通过它提前进入安全场景。
    @property
    def ending_phase(self) -> str:
        # 当前阶段唯一来源为结局组件。
        return self._ending.phase

    # 查询结局秒数，用于门外行走与光照表现，不影响开门时刻。
    @property
    def ending_elapsed(self) -> float:
        # 只返回累计秒数，不推进任何角色。
        return self._ending.elapsed_seconds

    # 查询夕阳到夜晚的归一化进度，界面不能自行推进时间。
    @property
    def ending_night_progress(self) -> float:
        # 纯模型计算进度，绘制资源不反向影响阶段。
        return self._ending.night_progress

    # 查询独立演出角色快照，不改动胜负时冻结的真实角色。
    @property
    def ending_actor(self) -> Actor | None:
        # 结局组件负责复制并保护状态所有权。
        return self._ending.actor

    # 查询到点后的展示秒数，成功过场继续开门而追逐时钟仍冻结。
    @property
    def door_open_seconds(self) -> float:
        # 相同计时边界确保门板动作不会在成功瞬间停在闭合姿态。
        return max(0.0, self.elapsed - self._shift_duration_seconds) + self.ending_elapsed

    # 查询距离开门还剩多少有效游戏秒数，开门后始终返回零。
    # 暂停、开场、对白和终态不会改变唯一计时elapsed。
    @property
    def remaining_shift_seconds(self) -> float:
        # 先取得相同模拟时间来源的真实差值。
        remaining_seconds = self._shift_duration_seconds - self.elapsed
        # 开门容差以内统一归零，界面不会显示微小残差或负秒数。
        return 0.0 if remaining_seconds <= TIME_EPSILON_SECONDS else remaining_seconds

    # 查询门是否已经开放，只由与钟面相同的有效游戏时间推导。
    # 微小容差消除60FPS累计到60秒时的浮点余量。
    @property
    def door_open(self) -> bool:
        # 显示与通行不会因分别计时而出现到点仍锁门的分歧。
        return self.remaining_shift_seconds <= TIME_EPSILON_SECONDS

    # 查询本局钟面，逐个游戏分钟推进，到下班后保持在结束时间。
    # 时钟不使用系统墙上时间，暂停和重开可以完全确定地验证。
    @property
    def clock_text(self) -> str:
        # 开门与钟面共用同一边界，避免浮点余量使门开了仍显示上一分钟。
        if self.door_open:
            # 下班后时钟停止，不继续跳到17:31而使目标变得含糊。
            return self._rules["shiftEndText"]
        # 尚未到点时只显示已经完整经过的分钟数。
        elapsed_minutes = int((self.elapsed + TIME_EPSILON_SECONDS) / self._rules["gameSecondsPerMinute"])
        # 跨午夜后回到00:00，不依赖真实日期或时区。
        clock_minutes = (self._clock_start_minutes + elapsed_minutes) % MINUTES_PER_DAY
        # 保留两位时分格式，直接兼容现有独立数字字形。
        return f"{clock_minutes // 60:02d}:{clock_minutes % 60:02d}"

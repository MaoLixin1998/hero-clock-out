"""拥有窗口按键集合，将事件转换为模型操作。"""

# 事件序列既可由窗口也可由受控测试提供。
from typing import Iterable

# 使用框架真实的事件与按键常量。
import pygame

# 输入层依赖模型接口，不实现位移规则。
from hero_game.model.game import Game
# 点击区域与字体语言由绘制器提供。
from hero_game.rendering.renderer import Renderer


# 每个窗口拥有一个控制器，状态切换时清空残留按键。
class InputController:
    # 窗口比例必须为正整数，正式交互策略为失焦暂停及胜负终态重开。
    def __init__(self, model: Game, renderer: Renderer, scale: int) -> None:
        # 比例是窗口像素到逻辑像素的除数，拒绝零、布尔值与小数。
        if type(scale) is not int or scale <= 0:
            # 校验发生在任何状态保存或点击事件之前。
            raise ValueError("Input scale must be a positive integer")
        # 模型状态由应用持有。
        self.model = model
        # 绘制器提供命中区域与语言。
        self.renderer = renderer
        # 鼠标显示坐标需要除以窗口缩放倍数。
        self.scale = scale
        # 控制器独占持续按键集合。
        self.held: set[int] = set()
        # E的物理按下状态独立于方向集合，避免系统连发重复触发。
        self._dash_key_down = False

    # 按事件顺序处理，返回继续运行标记和当帧冻结标记。
    def handle_events(self, events: Iterable[pygame.event.Event]) -> tuple[bool, bool]:
        # 任意状态切换都可冻结当帧时间。
        freeze_frame = False
        # 保持事件真实先后顺序。
        for event in events:
            # 关闭和Q优先结束循环。
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                # 退出后不再改变世界。
                return False, True
            # 失焦与最小化都清空旧方向。
            if event.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWMINIMIZED):
                # 防止回来后沿旧方向继续走。
                self.held.clear()
                # 失焦可能收不到松E事件，清除物理标记避免回来后第一下失效。
                self._dash_key_down = False
                # 胜负终态已经冻结，失焦只能清键，不能覆盖结果状态。
                if not (self.model.caught or self.model.escaped):
                    # 正常游戏失焦时统一冻结角色和打字。
                    self.model.paused = True
                # 切换焦点当帧不移动。
                freeze_frame = True
            # 松键移除对应持续输入。
            elif event.type == pygame.KEYUP:
                # 没有配对按下事件时也安全。
                self.held.discard(event.key)
                # 松开E才允许下一次新按下触发。
                if event.key == pygame.K_e:
                    # 恢复键沿检测，不改变正在执行的技能。
                    self._dash_key_down = False
            # 按键由当前模型状态解释。
            elif event.type == pygame.KEYDOWN:
                # 按住E或系统重复事件不能排队生成下一轮闪身。
                if event.key == pygame.K_e and (self._dash_key_down or getattr(event, "repeat", False)):
                    # 其他按键仍按原事件顺序处理。
                    continue
                # 任何阶段按下E都记录物理状态，不能从对白中带入连发。
                if event.key == pygame.K_e:
                    # 此标记只能由真实松键事件解除。
                    self._dash_key_down = True
                # 已有冻结请求不能被后面的移动键取消。
                freeze_frame = self.handle_key(event.key) or freeze_frame
            # 左键只在活动对话中有作用。
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # 暂停期间不允许继续对话。
                if self.model.dialogue.active and not self.model.paused:
                    # 换算成对话区域采用的逻辑坐标。
                    point = (event.pos[0] / self.scale, event.pos[1] / self.scale)
                    # 跳过按钮先于正文命中。
                    if self.renderer.skip_rect.collidepoint(point):
                        # 跳过台词不解除失败。
                        self.model.dialogue.skip()
                    # 点击正文补全或翻页。
                    elif self.renderer.dialogue_rect.collidepoint(point):
                        # 当前字体决定正文语言。
                        self.model.dialogue.advance(english=not self.renderer.font_path)
                    # 对话结束后要求重新按方向键。
                    self.held.clear()
                    # 切换当帧仍保持原位置。
                    freeze_frame = True
        # 没有退出事件时继续下一帧。
        return True, freeze_frame

    # 解释按键并返回是否冻结当帧，优先级为暂停、开场、对话、追逐。
    def handle_key(self, key: int) -> bool:
        # 胜负结果优先于暂停；终态不能通过空格、Esc或方向键继续移动。
        if self.model.caught or self.model.escaped:
            # 终态丢弃旧方向，重开之后必须重新按键。
            self.held.clear()
            # 明确按R才开启新一局，失败正文尚未结束也可直接重试。
            if key == pygame.K_r:
                # 正式重试默认直接回到追逐，不重复首次开场。
                self.model.reset()
            # 失败正文仍可补全或翻页，但该操作不会解除失败状态。
            elif self.model.caught and self.model.dialogue.active:
                # 确认键使用当前显示语言的全文长度。
                if key in (pygame.K_RETURN, pygame.K_SPACE):
                    # 只推进失败文字，不推进角色与时钟。
                    self.model.dialogue.advance(english=not self.renderer.font_path)
                # Tab与Esc允许跳过结果正文。
                elif key in (pygame.K_TAB, pygame.K_ESCAPE):
                    # 跳过对白仍然停在失败面板，等待明确重开。
                    self.model.dialogue.skip()
            # 结果处理和重开当帧都不补走时间。
            return True
        # 暂停时仅处理恢复键。
        if self.model.paused:
            # 空格或Esc恢复模拟。
            if key in (pygame.K_SPACE, pygame.K_ESCAPE):
                # 下一帧才继续推进。
                self.model.paused = False
            # 丢弃暂停期间的方向输入。
            self.held.clear()
            # 恢复当帧不补走。
            return True
        # 开场走路可以接收方向，跳跃不能带入残留输入。
        if self.model.opening_active:
            # 正式游戏开场仍允许暂停。
            if key in (pygame.K_SPACE, pygame.K_ESCAPE):
                # 冻结当前开场阶段。
                self.model.paused = True
                # 清除移动状态。
                self.held.clear()
                # 暂停当帧不推进。
                return True
            # 只有walk阶段收集按键。
            if self.model.intro_phase == "walk":
                # 移动查询会过滤非方向键。
                self.held.add(key)
            # 跳跃或展示阶段丢弃输入。
            else:
                # 阶段结束后必须重新按键。
                self.held.clear()
            # 普通开场移动不冻结。
            return False
        # 对话确认优先于暂停和重开。
        if self.model.dialogue.active:
            # 回车与空格补全或进入下一句。
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                # 备用语言使用对应全文长度。
                self.model.dialogue.advance(english=not self.renderer.font_path)
            # Tab与Esc跳过当前段落。
            elif key in (pygame.K_TAB, pygame.K_ESCAPE):
                # 被抓状态不会因此恢复。
                self.model.dialogue.skip()
            # 不将对话期间的移动带入追逐。
            self.held.clear()
            # 确认当帧不推进世界。
            return True
        # 正常追逐时空格与Esc暂停，胜负终态已在前面统一处理。
        if key in (pygame.K_SPACE, pygame.K_ESCAPE):
            # 模型后续更新进入冻结分支。
            self.model.paused = True
            # 清除旧移动。
            self.held.clear()
            # 状态切换当帧保持原位。
            return True
        # 正常追逐中的E调用正式技能接口，不加入方向集合。
        if key == pygame.K_e:
            # 有方向键时沿输入，无方向时模型选择当前朝向。
            self.model.request_dash(*self.direction())
            # 技能请求不冻结双方的模拟时间。
            return False
        # 普通追逐的按键集合归当前控制器拥有。
        self.held.add(key)
        # 普通输入不阻止模拟。
        return False

    # 查询八向输入，模型负责归一化速度。
    def direction(self) -> tuple[int, int]:
        # 输入查询本身也守住冻结边界，不依赖主循环稍后清键才停止移动。
        if (self.model.paused or self.model.caught or self.model.escaped or self.model.dialogue.active
                # 开场仅真实走路阶段允许方向输入。
                or (self.model.opening_active and self.model.intro_phase != "walk")):
            # 任何阻塞状态都没有有效移动方向。
            return 0, 0
        # 左右同时按时互相抵消。
        dx = int(bool(self.held & {pygame.K_d, pygame.K_RIGHT})) - int(bool(self.held & {pygame.K_a, pygame.K_LEFT}))
        # 屏幕向下为正，上下同时按时抵消。
        dy = int(bool(self.held & {pygame.K_s, pygame.K_DOWN})) - int(bool(self.held & {pygame.K_w, pygame.K_UP}))
        # 查询不改变持续输入。
        return dx, dy

    # 暂停、登场、对话或胜负终态主动清除残留方向。
    def clear_blocked_input(self) -> None:
        # 所有冻结阶段共用同一输入隔离边界，恢复和重开都需要新按键。
        if (self.model.paused or self.model.caught or self.model.escaped or self.model.dialogue.active
                # 正式开场只有walk阶段允许玩家持续移动。
                or (self.model.opening_active and self.model.intro_phase != "walk")):
            # 必须在恢复移动后重新按键。
            self.held.clear()

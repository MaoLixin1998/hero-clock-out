"""只读取模型与资源缓存进行绘制，不控制游戏时间或加载本机素材。"""

# 数学函数用于计算展示弹性和尘土轨迹。
import math

# pygame 提供内存画布与绘制操作。
import pygame

# 统一逻辑尺寸与正式文字的读取入口。
from hero_game.config import LOGICAL_SIZE, load_game_presentation, validate_game_presentation
# 角色类型标明绘制对象的坐标和朝向接口。
from hero_game.model.actor import Actor
# 游戏模型提供只读展示状态。
from hero_game.model.game import Game
# 动态门只读取正式门框位置，不承担出口规则。
from hero_game.rendering.door_renderer import DoorRenderer
# 安全门外绘图独立于办公室的追逐画面。
from hero_game.rendering.ending_renderer import EndingRenderer
# 纯代码资源支持无私人文件运行。
from hero_game.rendering.generated_resources import create_generated_resources
# 资源容器区分游戏状态和绘图依赖。
from hero_game.rendering.resource_bundle import ResourceBundle


# 把状态画到一个小画布。绘制本身不改变角色位置或胜负。
class Renderer:

    # 建立画布并预先加载当前游戏需要的全部图像与字体。
    # 绑定模型和预先准备的资源；缺省使用内存基础图形，不读取私人美术。
    # presentation 是正式界面文字或调用者注入的独立映射。
    def __init__(self, model: Game, resources: ResourceBundle | None = None,
                 # 省略界面文字时读取包内正式配置。
                 presentation: dict[str, str] | None = None) -> None:
        # 模型由应用拥有，绘制器只读取游戏状态。
        self.model = model
        # 每个绘制器持有一个资源容器；注入资源不会被复制或修改。
        self.resources = create_generated_resources() if resources is None else resources
        # 显式注入和包内文字都先校验全部字段与倒计时模板，不等状态切换后才发现错误。
        self.presentation = validate_game_presentation(load_game_presentation() if presentation is None else presentation)
        # 游戏使用固定逻辑画布，窗口缩放由应用处理。
        self.surface = pygame.Surface(LOGICAL_SIZE)
        # 背景只绘制到目标画布，不改变缓存图片。
        self.background = self.resources.background
        # 原门纹理缓存与正式门框位置在初始化时对齐。
        self.door_renderer = DoorRenderer(self.background, self.model.exit_door_bounds, self.resources.baked_exit_door)
        # 安全场景只准备一次，不逐帧生成完整背景。
        self.ending_renderer = EndingRenderer(self.resources.ending_background, self.resources.ending_night_background)
        # 帧缓存保留各帧真实时长。
        self.animations = self.resources.animations
        # 呼吸姿态基于正面待机帧，不改写原图。
        idle_frames, idle_meta = self.animations["hero", "down"]
        # 三种高度供轻微呼吸循环使用。
        self.opening_poses = [pygame.transform.scale(idle_frames[idle_meta["idle_frame"]], (64, 64 + extra))
                              # 每个版本只增加零到两个逻辑像素。
                              for extra in range(3)]
        # 界面缓存来自资源工厂，绘制过程不读文件。
        self.ui = self.resources.ui
        # 字体路径决定是否采用英文备用文字。
        self.font_path = self.resources.font_path
        # 状态标题使用较大字号。
        self.font = pygame.font.Font(self.font_path, 18)
        # 按钮与姓名使用小字号。
        self.small = pygame.font.Font(self.font_path, 12)
        # 正文有独立字号以保证阅读。
        self.body_font = pygame.font.Font(self.font_path, 16)
        # 对话图形与正文数据分离。
        self.dialogue_ui = self.resources.dialogue_ui
        # 派生立绘缓存属于当前绘制器。
        self.portraits = {}
        # 已解码的立绘按说话者 ID 缩放。
        for speaker, original in self.resources.portraits.items():
            # 完全透明的立绘不能计算有效缩放比例。
            bounds = original.get_bounding_rect()
            # 提前报告空图，避免除以零。
            if bounds.width == 0 or bounds.height == 0:
                # 只报告角色 ID，不输出素材内容。
                raise ValueError(f"Portrait has no visible pixels: {speaker}")
            # 裁去留白后复制，避免派生操作修改缓存原图。
            portrait = original.subsurface(bounds).copy()
            # 使用较小比例，确保图像同时适合宽高约束。
            scale = min(146 / portrait.width, 194 / portrait.height)
            # 取整后至少保留一个像素。
            size = (max(1, round(portrait.width * scale)), max(1, round(portrait.height * scale)))
            # 一次缩放后重复绘制，不逐帧计算立绘。
            self.portraits[speaker] = pygame.transform.scale(portrait, size)
        # 点击矩形使用逻辑坐标。
        self.dialogue_rect = pygame.Rect(154, 244, 476, 108)
        # 跳过按钮的绘制区域与点击区域使用同一矩形。
        self.skip_rect = pygame.Rect(546, 12, 82, 25)

    # 在逻辑画布画一段文字，支持小字号和横向居中。
    def label(self, text: str, x: int, y: int, color: tuple[int, int, int] = (235, 231, 208),
              # small 选择字号，centered 表示以给定横坐标居中。
              small: bool = False, centered: bool = False) -> None:
        # 按 small 选择字体，把文字变成有透明背景的图片；True 开启文字抗锯齿。
        surface = (self.small if small else self.font).render(text, True, color)
        # 把文字图片画到画布；居中时横坐标减去文字宽度的一半。
        self.surface.blit(surface, (x - surface.width // 2 if centered else x, y))

    # 按各帧真实时长选图。史莱姆各帧时长不同，不能简单除以帧数。
    def draw_actor(self, actor: Actor) -> None:
        # 按角色类型和当前朝向，取出缓存的图片列表与播放配置。
        frames, meta = self.animations[actor.kind, actor.direction]
        # 先选择待机帧；角色没有移动时直接使用这个编号。
        index = meta["idle_frame"]
        # 角色真的在移动时，才根据行走时间切换动画帧。
        if actor.moving:
            # 取出每张帧图片的毫秒时长，保持资源清单指定的运动节奏。
            durations = [f["duration_ms"] for f in meta["frames"]]
            # 把行走秒数转成毫秒，再对一个完整周期取余，让动画循环播放。
            t = (actor.phase * 1000) % sum(durations)
            # 依次查看每帧占据的时间段，找到当前时间落在哪一帧。
            for index, duration in enumerate(durations):
                # 剩余时间小于当前帧时长，说明这一刻应该显示当前帧。
                if t < duration:
                    # 结束找帧循环，保留刚刚找到的帧编号。
                    break
                # 当前帧时间段已走完，就扣掉它的时长，继续寻找后面的帧。
                t -= duration
        # 渲染前把小数坐标四舍五入；模拟中的精确小数位置仍保留。
        x, y = round(actor.x), round(actor.y)
        # 读取图片内的脚底锚点，确定图片左上角相对角色坐标的偏移。
        ax, ay = self.resources.anchors[actor.kind]
        # 默认仍使用实际行走或静止帧，只有安静开场的勇者才做呼吸展示。
        frame = frames[index]
        # 展示动画只改变画出来的姿态，不改变角色数据或碰撞位置。
        if (actor.kind == "hero" and not actor.moving and actor.direction == "down"
                # 开场与安全门外都可呼吸，正常追逐不附加此表现。
                and (self.model.opening_active or self.model.ending_phase in ("outside", "complete"))):
            # 每 1.5 秒完成一轮起伏；周期结束后自然连续循环。
            cycle = (self.model.ending_elapsed if self.model.escaped else self.model.opening_elapsed) / 1.5
            # 余弦波从 0 到 2 再回到 0，取整后选择三个像素高度之一。
            extra = round(1 - math.cos(2 * math.pi * cycle))
            # 选择已经缓存的呼吸姿态，避免每帧重新读取或缩放图片。
            frame = self.opening_poses[extra]
            # 按高度比同步换算脚底锚点，让脚底保持在原来的地面位置。
            ay = round(ay * frame.height / frames[index].height)
        # 登场中的史莱姆使用同一张透明帧做弹跳和压扁，世界坐标保持在勇者面前的落点。
        if actor.kind == "slime" and self.model.intro_phase == "entrance":
            # 读取跳跃时长，用它区分空中动作和落地回弹。
            jump = self.model.rules["slimeJumpSeconds"]
            # 当前跳跃秒数由规则层更新；绘制层只读取，重复画图不会加速动画。
            t = self.model.entrance_elapsed
            # 跳跃尚未结束时，让史莱姆从勇者面前的地面逐渐长大并向上弹出。
            if t < jump:
                # p 从 0 走到 1，是当前空中动作的完成比例。
                p = t / jump
                # 抛物线在中途达到最高点，两端都回到原地面高度。
                lift = 4 * self.model.rules["slimeJumpHeight"] * p * (1 - p)
                # 最初约 0.1 秒从小点长成完整身体，避免凭空瞬间贴一张图。
                grow = min(1.0, p / 0.18)
                # 空中稍瘦稍高，强调从地面弹起的弹性。
                sx, sy = grow * (0.88 + 0.12 * p), grow * (1.12 - 0.12 * p)
            # 跳跃结束后，先压扁再回弹，最后恢复正常形状。
            else:
                # 把落地后的时间换算为 0 到 1 的回弹进度。
                p = (t - jump) / (self.model.rules["slimeEntranceSeconds"] - jump)
                # 带衰减的余弦先压扁、再拉长；结束处乘零，保证没有姿态突变。
                squash = math.cos(3 * math.pi * p) * (1 - p) ** 2
                # 横向变宽和纵向变扁同时发生，第一帧是明显的 duang 落地。
                sx, sy = 1 + 0.35 * squash, 1 - 0.35 * squash
                # 回弹始终站在地面，不能把史莱姆实际坐标向上移动。
                lift = 0
            # 最近邻缩放保留像素边缘；至少 1 像素，防止零尺寸图片。
            scaled = (max(1, round(frame.width * sx)), max(1, round(frame.height * sy)))
            # 同步缩放脚底锚点，压扁和拉高时脚底仍准确对齐。
            ax, ay = round(ax * sx), round(ay * sy)
            # 用现有 PNG 帧缩放，不替换原始四向行走动画素材。
            frame = pygame.transform.scale(frame, scaled)
            # 把空中高度只应用到画面位置，不改变后续追击的出生点。
            y -= round(lift)
        # 把图片中的脚底锚点对齐角色坐标，换帧时就不会横向漂移。
        self.surface.blit(frame, (x - ax, y - ay))

    # 在脚下画落点影子与像素尘土，帮助看清在勇者面前跳出的动作。
    def draw_entrance_effects(self) -> None:
        # 缩短名字，后面仍只读取模型状态，不修改游戏规则。
        m = self.model
        # 特效仅在登场期间出现，正常追逐不残留脚下圆圈或选择框。
        if m.intro_phase != "entrance":
            # 非登场状态立即结束，保持原有场景干净。
            return
        # 取得史莱姆地面锚点，而不是已经抬高的图片顶部。
        x, y = round(m.slime.x), round(m.slime.y)
        # 使用独立透明层，让地面影子柔和但保留像素块形状。
        effects = pygame.Surface(LOGICAL_SIZE, pygame.SRCALPHA)
        # 阴影从小落点快速长到正常大小，帮助确认本次登场的固定落点。
        width = max(2, round(36 * min(1, m.entrance_elapsed / 0.12)))
        # 画 8 像素高的椭圆阴影，角色随后画在阴影上面。
        pygame.draw.ellipse(effects, (19, 26, 40, 100), (x - width // 2, y - 4, width, 8))
        # 落地后才开始扬尘；空中阶段不出现提前撞击的效果。
        dust_age = m.entrance_elapsed - m.rules["slimeJumpSeconds"]
        # 尘土存在 0.22 秒，落稳前收掉，不遮住后面的台词。
        if 0 <= dust_age < 0.22:
            # 尘土比例从 0 到 1，控制向四周扩散的距离和透明度。
            p = dust_age / 0.22
            # 八个方向的方块形成一圈冲击，数目固定且每次登场一致。
            for index in range(8):
                # 将一整圈分成八个角度，单位是弧度。
                angle = index * math.tau / 8
                # 粒子横向扩散比纵向大，视觉上贴在办公室地面。
                px, py = x + round(math.cos(angle) * (20 + 24 * p)), y + round(math.sin(angle) * (5 + 10 * p))
                # 方块边长随时间缩小，至少保留 1 像素直到消失。
                size = max(1, round(5 * (1 - p)))
                # 用浅米色尘土和逐渐降低的透明度表现落地冲击。
                pygame.draw.rect(effects, (230, 211, 160, round(220 * (1 - p))), (px, py, size, size))
        # 把特效叠到地面，下一步再绘制双方角色。
        self.surface.blit(effects, (0, 0))

    # 按实际字宽换行，既支持中文，也尊重台词里主动写入的换行。
    def draw_wrapped_text(self, text: str, position: tuple[int, int], width: int) -> None:
        # lines 收集已经换好的行，current 累积尚未输出的当前行。
        lines, current = [], ""
        # 逐字处理已显示台词，让中文和英文都能按实际字宽换行。
        for char in text:
            # 遇到显式换行符时，直接结束当前行，不再等待宽度用满。
            if char == "\n":
                # 把当前行加入待绘制列表，保留台词中的主动断行。
                lines.append(current)
                # 清空当前行，下一字符将从新的一行开始。
                current = ""
            # 如果再加入这个字就会超出允许宽度，也需要换行。
            elif self.body_font.size(current + char)[0] > width:
                # 先收下尚未超宽的原行，避免最后一个字挤出对话框。
                lines.append(current)
                # 把超宽的这个字放到下一行开头，既不丢字也不重复。
                current = char
            # 这个字不会超宽，也不是换行符，可以接在当前行末尾。
            else:
                # 把字符追加到当前行，继续累积完整台词。
                current += char
        # 循环结束后收下最后一行；没有换行符结尾时也不会漏掉正文。
        lines.append(current)
        # 按行号逐行绘制，行号用于计算每一行向下的偏移。
        for row, line in enumerate(lines):
            # 把这行文字渲染为深棕色图片，保证羊皮纸背景上的可读性。
            rendered = self.body_font.render(line, True, (52, 45, 35))
            # 画在正文起点，每一行向下移 23 像素，形成固定行距。
            self.surface.blit(rendered, (position[0], position[1] + row * 23))

    # 立绘位于左下，姓名牌压在纸质台词框上；文字由程序绘制。
    def draw_dialogue(self) -> None:
        # 取出台词播放器，后面的绘制只读取它，不推进播放进度。
        dialogue = self.model.dialogue
        # 从当前台词取出 speaker 编号，决定显示谁的姓名和立绘。
        speaker = dialogue.current["speaker"]
        # 取得说话者的姓名、英文备用姓名与立绘路径等信息。
        spec = dialogue.data["speakers"][speaker]
        # 读取已经缩放好的立绘，避免每一帧重新裁切或缩放原图。
        portrait = self.portraits[speaker]
        # 把立绘放在左侧区域居中且贴近画布底边，左侧至少留 3 像素。
        self.surface.blit(portrait, (max(3, (154 - portrait.width) // 2), 360 - portrait.height))
        # 将羊皮纸台词框画在正文区域，透明切角会露出后面的办公室。
        self.surface.blit(self.dialogue_ui["panel"], self.dialogue_rect)
        # 把姓名牌压在台词框上沿，形成角色姓名标签。
        self.surface.blit(self.dialogue_ui["nameplate"], (173, 225))
        # 有中文字体用中文名，否则用英文名，避免缺字显示方框。
        name = spec["name"] if self.font_path else spec["nameEnglish"]
        # 用小字在姓名牌中央绘制角色名。
        self.label(name, 295, 230, centered=True, small=True)
        # 取得当前已出现的文字，选择对应语言，在 436 像素正文宽度内换行。
        self.draw_wrapped_text(dialogue.visible_text(english=not self.font_path), (173, 261), 436)
        # 在纸框右下画向下箭头，让玩家看出这里可以继续对话。
        self.surface.blit(self.dialogue_ui["advance"], (606, 333))
        # 为当前字体选择中文或英文的继续提示。
        instruction = "Enter / 空格 继续" if self.font_path else "Enter / Space: next"
        # 在纸框内画居中的小字提示，位置为箭头留出间隔。
        self.label(instruction, 529, 330, color=(109, 93, 62), small=True, centered=True)
        # 绘制右上角跳过按钮的深色底，让按钮与场景区分开。
        pygame.draw.rect(self.surface, (23, 38, 46), self.skip_rect)
        # 把跳过提示画在按钮中央，有中文字体时使用中文。
        self.label("跳过 [Tab]" if self.font_path else "Skip [Tab]", 587, 17,
                   # 使用小字号并以给定横坐标居中，适配跳过按钮的窄宽度。
                   small=True, centered=True)

    # 原门的位置由正式规则提供，纹理与动态通道分开绘制。
    def draw_exit(self) -> None:
        # 当前模型只读提供门的通行状态与动作秒数。
        self.door_renderer.draw(self.surface, self.model.door_open_seconds, self.model.door_open)
        # 演出与对白期间不在地面叠加操作指引。
        if self.model.opening_active or self.model.dialogue.active or self.model.escaped:
            # 原门始终可见，操作箭头只服务正常追逐。
            return
        # 门前触发区保持完整位于可走边界中。
        left, top, right, bottom = self.model.exit_bounds
        # 绘制准确入口，不把高处门板直接作为碰撞区。
        threshold = pygame.Rect(round(left), round(top), round(right - left), round(bottom - top))
        # 开放入口用绿色边线，关闭时保持低对比。
        color = (126, 232, 160) if self.model.door_open else (122, 132, 115)
        # 地面短连接线指向同一原门，不创建第二个出口。
        pygame.draw.line(self.surface, color, threshold.midright, (self.door_renderer.rect.left, threshold.centery), 2)
        # 原门前可达触发区让玩家知道该走到哪里。
        pygame.draw.rect(self.surface, color, threshold, 2)

    # 正常追逐时给出逐秒剩余时间或开放后的门槛指引，文字来自正式配置。
    def draw_shift_instruction(self) -> None:
        # 开场、对白和冻结面板已有主要内容，此时不额外叠加抢眼提示。
        if (self.model.opening_active or self.model.dialogue.active or self.model.paused
                # 胜负终态使用各自面板，不保留追逐操作指引。
                or self.model.caught or self.model.escaped):
            # 提示出现的时机与真实可操作追逐阶段一致。
            return
        # 无中文字体时使用正式英文备用字段。
        suffix = "" if self.font_path else "English"
        # 门开放后改为指引玩家到达实际门槛。
        if self.model.door_open:
            # 直接读取已校验的开放操作说明，不由文字反推门状态。
            text = self.presentation[f"doorOpenInstruction{suffix}"]
        # 门尚未开放时按向上取整显示剩余整数秒。
        else:
            # 正数余量始终至少显示 1 秒，避免未开门时提前出现零。
            seconds = math.ceil(self.model.remaining_shift_seconds)
            # 模板已经在配置边界确认只有 seconds 变量。
            text = self.presentation[f"doorCountdown{suffix}"].format(seconds=seconds)
        # 指引使用小字号居中放在时钟下方，不遮挡人物或门口。
        self.label(text, 320, 72, color=(196, 220, 192), small=True, centered=True)

    # 按背景、时钟、角色、对话、状态提示顺序绘制一帧完整画面。
    def draw(self) -> pygame.Surface:
        # 用局部变量 m 简写游戏对象，减少重复的 self.model。
        m = self.model
        # 完整过门之后显示安全区，不再画史莱姆、办公室钟面或成功弹窗。
        if m.ending_phase in ("outside", "complete"):
            # 专用绘图通过公开角色与文字能力组合，不反向修改状态。
            self.ending_renderer.draw(self.surface, m, self.draw_actor)
            # 结局画布交给同一应用显示。
            return self.surface
        # 先用深色清空上一帧，避免移动的图片留在旧位置。
        self.surface.fill((10, 22, 32))
        # 在画布左上角铺办公室背景，重新建立干净的场景。
        self.surface.blit(self.background, (0, 0))
        # 墙门与地面门槛跟随模型状态，不能画进共享背景缓存。
        self.draw_exit()
        # 从素材配置取出时钟在场景中的左上角位置。
        x, y = self.resources.clock_position
        # 先画时钟外壳，数字和时间牌随后叠在它上面。
        self.surface.blit(self.ui["clock_housing"], (x, y))
        # 把下班时间牌放在时钟外壳内部偏下的位置。
        self.surface.blit(self.ui["shift_end_1730"], (x, y + 27))
        # 设置第一个时钟字符的横坐标，让整串时间居中于外壳。
        cursor = x + 27
        # 从左到右遍历时钟文字，一次绘制一个数字或冒号。
        for char in m.clock_text:
            # 冒号使用 colon 图，其余字符选对应 digit 图片。
            glyph = self.ui["colon" if char == ":" else f"digit_{char}"]
            # 在当前位置画这个字形，纵向放在外壳顶部以下 5 像素。
            self.surface.blit(glyph, (cursor, y + 5))
            # 把光标向右推进字形宽度加 2 像素，给下一个字形留间隔。
            cursor += glyph.width + 2
        # 时钟数字保留分钟显示，下面的实时秒数帮助玩家确认时间正在流动。
        self.draw_shift_instruction()
        # 登场时先画落点影子与尘土，史莱姆身体随后叠在它们上面。
        self.draw_entrance_effects()
        # 勇者走够距离后才显示史莱姆，台词仍要等它落地回弹完成。
        actors = (m.ending_actor, m.slime) if m.ending_phase == "crossing" else (m.hero, m.slime) if m.slime_visible else (m.hero,)
        # 脚底更靠下的角色后画，看起来会站在另一个角色前面。
        for actor in sorted(actors, key=lambda a: a.y):
            # 门框遮挡跨出角色右侧，保证角色逐步进入门洞。
            original_clip = self.surface.get_clip()
            # 跨门只裁角色，不裁整间办公室或敌人。
            if m.ending_phase == "crossing" and actor.kind == "hero":
                # 走到门框之外的身体不继续画在墙上。
                self.surface.set_clip((0, 0, round(m.exit_door_bounds[2]), LOGICAL_SIZE[1]))
            # 绘制当前排序位置上的角色，包括它的朝向与当前动画帧。
            self.draw_actor(actor)
            # 下一角色和UI恢复完整绘制区域。
            self.surface.set_clip(original_clip)
        # 还有台词在播放时，叠加对话 UI；正常追逐中不显示这块底部框。
        if m.dialogue.active:
            # 画当前说话者的立绘、姓名和已经出现的台词。
            self.draw_dialogue()
        # 下班成功立即显示结果；失败对白结束后和普通暂停显示各自冻结面板。
        if m.paused or (m.caught and not m.dialogue.active):
            # 创建能使用透明度的遮罩画布，尺寸覆盖整个游戏画面。
            shade = pygame.Surface(LOGICAL_SIZE, pygame.SRCALPHA)
            # 填充半透明深色；最后的 110 是透明度，0 全透明、255 不透明。
            shade.fill((5, 15, 25, 110))
            # 把遮罩叠到场景上，背景仍看得到，但突出中间的状态提示。
            self.surface.blit(shade, (0, 0))
            # 绘制中央面板的深色底，左上角为 (165,135)，大小为 310×82。
            pygame.draw.rect(self.surface, (15, 34, 46), (165, 135, 310, 82))
            # 给面板画 1 像素金色边线，区分提示与暗下来的场景。
            pygame.draw.rect(self.surface, (182, 152, 101), (165, 135, 310, 82), 1)
            # 结果状态优先于普通暂停，失焦也不能把成功面板替换成暂停。
            state = "escaped" if m.escaped else "caught" if m.caught else "paused"
            # 缺少中文字体时读取英文配置，避免中文缺字显示方框。
            language_suffix = "" if self.font_path else "English"
            # 按当前状态和语言读取标题；界面文字与程序逻辑分开保存。
            title = self.presentation[f"{state}Title{language_suffix}"]
            # 操作提示使用同一状态与语言，保持面板显示一致。
            instruction = self.presentation[f"{state}Instruction{language_suffix}"]
            # 把标题居中画到面板上半部。
            self.label(title, 320, 151, centered=True)
            # 把操作说明居中画到面板下半部，采用小字和较浅的颜色。
            self.label(instruction, 320, 183, color=(175, 197, 198), small=True, centered=True)
        # 返回已经画好的逻辑画布，由窗口显示或离线导出使用。
        return self.surface

"""用程序绘制基础游戏资源，保证纯代码安装包不依赖本机创作素材。"""

# 正弦波让基础行走帧具有轻微起伏。
import math
# 系统字体路径只有实际存在时才使用。
from pathlib import Path

# 所有图形都在显式准备资源时创建，普通导入不启动窗口。
import pygame

# 逻辑尺寸由运行规则模块统一提供。
from hero_game.config import LOGICAL_SIZE
# 资源容器只保存已准备的数据。
from hero_game.rendering.resource_bundle import ResourceBundle

# 四个方向同时供基础资源生成和外部资源校验使用。
DIRECTIONS = ("down", "left", "up", "right")
# 字体候选按当前支持的平台排列，不复制本机字体到发行包。
FONT_CANDIDATES = (
    # macOS 系统中文字体。
    "/System/Library/Fonts/STHeiti Medium.ttc",
    # Windows 系统中文字体。
    "C:/Windows/Fonts/msyh.ttc",
    # Linux 已安装的 Noto 中文字体。
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


# 寻找现有中文系统字体；缺失时由界面选择英文文本。
def find_font() -> str | None:
    # 只返回真实普通文件，不把不存在路径交给字体加载器。
    return next((path for path in FONT_CANDIDATES if Path(path).is_file()), None)


# 创建指定尺寸的透明画布，不将生成结果写入工作区。
def transparent_surface(size: tuple[int, int]) -> pygame.Surface:
    # SRCALPHA 保留角色和 UI 周围的透明区域。
    return pygame.Surface(size, pygame.SRCALPHA)


# 绘制一个基础角色姿态；kind 与 direction 是稳定 ID，phase 是周期弧度。
def actor_frame(kind: str, direction: str, phase: float) -> pygame.Surface:
    # 每帧保留同一尺寸和脚底锚点，切换时不发生横向漂移。
    frame = transparent_surface((64, 64))
    # 两像素起伏表达行走，保持脚底附近的整体位置稳定。
    lift = round(2 * math.sin(phase))
    # 两种角色使用不同轮廓，玩家无需靠文字识别。
    if kind == "hero":
        # 身体采用蓝色矩形，留出头部与脚部空间。
        pygame.draw.rect(frame, (72, 142, 194), (23, 29 - lift, 18, 23))
        # 头部使用圆形基础形状，不包含真人肖像。
        pygame.draw.circle(frame, (239, 205, 153), (32, 22 - lift), 11)
        # 两脚反向摆动，避免只有整张图上下浮动。
        pygame.draw.rect(frame, (46, 54, 67), (22, 50, 9, 8 - max(0, lift)))
        # 另一只脚使用相反的步态。
        pygame.draw.rect(frame, (46, 54, 67), (34, 50, 9, 8 + min(0, lift)))
    # 敌人使用圆润绿色形状，与主角明显区分。
    else:
        # 椭圆底边仍对齐脚底锚点附近。
        pygame.draw.ellipse(frame, (90, 191, 139), (12, 27 - lift, 40, 31 + lift))
    # 朝后时隐藏眼睛，其余朝向用位置变化表示。
    if direction != "up":
        # 左右朝向分别移动眼睛，正面则使用中央位置。
        offset = -5 if direction == "left" else 5 if direction == "right" else 0
        # 眼睛的纵坐标根据角色形状确定。
        eye_y = (22 if kind == "hero" else 39) - lift
        # 两个眼点使用深色，保证在基础颜色上可见。
        pygame.draw.circle(frame, (26, 36, 43), (28 + offset, eye_y), 2)
        # 第二个眼点与第一个保持固定间距。
        pygame.draw.circle(frame, (26, 36, 43), (36 + offset, eye_y), 2)
    # 返回独立图片，调用方缓存后不会再次绘制到这张图上。
    return frame


# 生成纯代码资源；调用前应用已初始化 pygame 字体子系统。
def create_generated_resources() -> ResourceBundle:
    # 背景先铺底色，所有生成图形只描述游戏房间。
    background = pygame.Surface(LOGICAL_SIZE)
    # 上半部分使用深蓝墙面。
    background.fill((32, 48, 63))
    # 地面覆盖活动区域与画布底部。
    pygame.draw.rect(background, (62, 76, 83), (0, 160, 640, 200))
    # 地砖线用于观察真实位移，间距为 32 逻辑像素。
    for x in range(0, 640, 32):
        # 只在地面区域绘制纵向线。
        pygame.draw.line(background, (68, 83, 90), (x, 160), (x, 360))
    # 横向线与纵向线共同组成参考网格。
    for y in range(160, 360, 32):
        # 细线保持背景不过度抢占角色注意力。
        pygame.draw.line(background, (68, 83, 90), (0, y), (640, y))
    # 帧缓存按角色和方向分别保存。
    animations = {}
    # 角色 ID 与正式对白保持一致。
    for kind in ("hero", "slime"):
        # 每个朝向都提供完整周期。
        for direction in DIRECTIONS:
            # 四帧使用等间隔周期相位，帧列表由当前资源实例拥有。
            frames = [actor_frame(kind, direction, index * math.tau / 4) for index in range(4)]
            # 元数据保持与外部帧清单一致的接口。
            metadata = {"idle_frame": 0, "frames": [{"duration_ms": 100} for _ in frames]}
            # 每个方向保存独立列表，绘制时只读取。
            animations[kind, direction] = (frames, metadata)
    # 基础时钟使用系统默认数字字体，无中文字体也能辨认。
    digit_font = pygame.font.Font(None, 27)
    # 时钟底板与其他 UI 一样缓存一次。
    housing = transparent_surface((112, 54))
    # 深色底板突出浅色数字。
    housing.fill((17, 28, 35))
    # 字形采用固定窄框，与原逻辑布局兼容。
    ui = {"clock_housing": housing, "shift_end_1730": transparent_surface((112, 20))}
    # 数字和冒号都是独立透明组件。
    for character in "0123456789:":
        # 冒号采用专用键，其余按数字命名。
        name = "colon" if character == ":" else f"digit_{character}"
        # 字形宽度固定，时间保持稳定位置。
        glyph = transparent_surface((10 if character != ":" else 5, 22))
        # 文字在字形画布上向上偏移，避免超出固定高度。
        glyph.blit(digit_font.render(character, True, (225, 221, 164)), (0, -1))
        # 保存生成字形供绘制器查表。
        ui[name] = glyph
    # 三个对话组件采用与既有界面相同的尺寸。
    dialogue_ui = {}
    # 基础面板只承担布局，不包含台词或视频标题。
    for name, size in (("panel", (476, 108)), ("nameplate", (244, 25)), ("advance", (12, 8))):
        # 每个组件都有独立透明画布。
        image = transparent_surface(size)
        # 箭头使用三角形，其余使用浅色矩形。
        if name == "advance":
            # 向下箭头提示可继续对话。
            pygame.draw.polygon(image, (83, 64, 41), ((0, 0), (11, 0), (6, 7)))
        # 主框与姓名牌都保留一像素边界。
        else:
            # 圆角矩形使组件外角保持透明。
            pygame.draw.rect(image, (235, 223, 192), image.get_rect(), border_radius=4)
            # 棕色边框与房间底色区分。
            pygame.draw.rect(image, (151, 125, 83), image.get_rect(), 1, border_radius=4)
        # 缓存当前对话组件。
        dialogue_ui[name] = image
    # 立绘复用基础角色图，正式美术包可单独替换，不影响游戏数据。
    portraits = {kind: actor_frame(kind, "down", 0) for kind in ("hero", "slime")}
    # 构建不含私人路径的完整资源容器。
    return ResourceBundle(
        # 完整房间背景已经准备好。
        background=background,
        # 行走缓存包含两个角色的四个方向。
        animations=animations,
        # 所有基础帧统一以脚底中央为锚点。
        anchors={kind: (32, 58) for kind in ("hero", "slime")},
        # 时钟与数字图形不包含视频装饰。
        ui=ui,
        # 对话组件只缓存图形。
        dialogue_ui=dialogue_ui,
        # 角色立绘由稳定 ID 查找。
        portraits=portraits,
        # 基础时钟放在画布上方中央。
        clock_position=(264, 12),
        # 字体缺失时显示英文备用对白。
        font_path=find_font(),
    )

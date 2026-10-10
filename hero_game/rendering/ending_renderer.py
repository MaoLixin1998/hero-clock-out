"""只绘制河岸日夜变化和离画角色，不叠加结局文字。"""

# 角色绘图通过现有公开回调组合，不复制精灵渲染逻辑。
from typing import Callable

# 图像和像素操作只在绘图层使用。
import pygame

# 底图尺寸沿用正式画布契约。
from hero_game.config import LOGICAL_SIZE
# 角色快照与状态均由纯模型提供。
from hero_game.model.actor import Actor
# 结局阶段与光照进度通过Game公开接口读取。
from hero_game.model.game import Game


# 默认场景完全程序绘制，白天与夜晚共享全部几何位置。
def create_base_background(night: bool) -> pygame.Surface:
    # 画布属于本次资源构造，不使用可变全局缓存。
    background = pygame.Surface(LOGICAL_SIZE)
    # 天空渐变保留完整画布上半部。
    for y in range(200):
        # 夜晚不保留橙色夕照，其他空间位置完全不变。
        color = (13 + y // 12, 24 + y // 10, 49 + y // 8) if night else (80 + y // 3, 67 + y // 4, 112 + y // 5)
        # 逐行画天空，不读取任何私人图像。
        pygame.draw.line(background, color, (0, y), (639, y))
    # 太阳只在夕阳端点出现，夜景端点没有太阳。
    if not night:
        # 日夜叠画会逐渐消退太阳光。
        pygame.draw.circle(background, (246, 184, 112), (446, 106), 31)
    # 两个端点复用相同城市轮廓。
    for x in range(150, 640, 54):
        # 远处高楼的尺寸不随光照改变。
        pygame.draw.rect(background, (36, 46, 68) if night else (73, 74, 99), (x, 138 - x % 43, 42, 66 + x % 43))
        # 夜晚在现有楼体内显示暖色窗光。
        if night:
            # 窗光属于同一建筑，不能产生新的通路。
            pygame.draw.rect(background, (188, 155, 92), (x + 9, 119 - x % 43, 4, 6))
    # 江面始终位于固定河岸后方。
    pygame.draw.rect(background, (29, 56, 79) if night else (100, 136, 155), (137, 130, 503, 58))
    # 水面反射亮度变化不移动江岸。
    for y in range(139, 188, 11):
        # 日落反光逐渐过渡到城市灯光反射。
        pygame.draw.line(background, (136, 133, 112) if night else (169, 165, 158), (370, y), (520, y), 2)
    # 步道留下完整行走空间。
    pygame.draw.rect(background, (48, 63, 79) if night else (96, 101, 104), (0, 199, 640, 161))
    # 栏杆保持在角色后方。
    pygame.draw.rect(background, (36, 48, 63) if night else (60, 72, 83), (137, 188, 503, 11))
    # 竖柱在两张底图里使用相同间隔。
    for x in range(149, 640, 46):
        # 夜晚柱体仍能分辨，不将整个背景压成纯黑。
        pygame.draw.rect(background, (60, 69, 78) if night else (88, 90, 90), (x, 180, 5, 21))
    # 左侧公司体块和唯一门洞都保留。
    pygame.draw.rect(background, (30, 43, 63) if night else (43, 53, 68), (0, 52, 136, 207))
    # 门口暖光保持可见，强调角色已经走到外面。
    pygame.draw.rect(background, (212, 185, 122), (78, 150, 40, 89))
    # 台阶与脚底起点使用稳定的位置关系。
    pygame.draw.rect(background, (84, 91, 99) if night else (128, 130, 130), (65, 239, 76, 12))
    # 地面纹理只作静态空间参照。
    pygame.draw.line(background, (66, 77, 90) if night else (120, 122, 121), (0, 263), (640, 263), 2)
    # 右侧板凳不进入角色行走的前景水平线。
    pygame.draw.rect(background, (87, 65, 54) if night else (122, 79, 55), (415, 221, 99, 11))
    # 椅背固定在原有位置。
    pygame.draw.rect(background, (94, 70, 55) if night else (140, 93, 63), (415, 199, 99, 17))
    # 两条椅腿保持相同尺寸。
    for x in (426, 501):
        # 深色椅腿仍与地面连接。
        pygame.draw.rect(background, (34, 44, 57), (x, 230, 5, 25))
    # 两棵树位于步道后缘，角色从前方走过。
    for x in (196, 587):
        # 日夜只改变树干明度，不改变树的位置。
        pygame.draw.rect(background, (75, 62, 54) if night else (106, 79, 56), (x - 4, 147, 8, 64))
        # 树冠在两个端点保持同一轮廓。
        pygame.draw.ellipse(background, (35, 58, 48) if night else (71, 100, 69), (x - 30, 111, 59, 64))
    # 完整端点归当前绘制器持有。
    return background


# 绘制器只查询结局状态，日夜资源在初始化时缓存。
class EndingRenderer:
    # 可选外部日夜图必须同尺寸，未提供时有独立基础画面。
    def __init__(self, background: pygame.Surface | None = None, night_background: pygame.Surface | None = None) -> None:
        # 两张显式画布都在使用前验证类型与尺寸。
        for image in (background, night_background):
            # 省略值代表使用基础资源，错误值不能隐式转换。
            if image is not None and (not isinstance(image, pygame.Surface) or image.get_size() != LOGICAL_SIZE):
                # 错误发生在初始化，不等待玩家完成游戏。
                raise ValueError("Ending background must be a 640 by 360 surface")
        # 夕阳缓存由当前绘制器独立拥有。
        self.background = create_base_background(False) if background is None else background.copy()
        # 有完整夜景时直接复制，不能修改调用者的资源。
        if night_background is not None:
            # 夜景几何与夕阳相同，混合仅改变光照。
            self.night_background = night_background.copy()
        # 默认产品使用没有太阳的程序夜景。
        elif background is None:
            # 此端点不依赖任何本机素材。
            self.night_background = create_base_background(True)
        # 旧外部资源包只有夕阳图时兼容原有几何。
        else:
            # 暗色派生图与资源原件隔离。
            self.night_background = background.copy()
            # 只压低明度，保留旧资源包可识别的空间轮廓。
            self.night_background.fill((80, 108, 152), special_flags=pygame.BLEND_RGB_MULT)
        # 混合层的透明度可变，不改写日夜端点缓存。
        self._night_overlay = self.night_background.copy()

    # 无文字、时钟或敌人的结局画面只包含环境渐变与已有角色。
    def draw(self, surface: pygame.Surface, model: Game, draw_actor: Callable[[Actor], None]) -> None:
        # 每帧从同一夕阳端点重新铺画，避免行走残影。
        surface.blit(self.background, (0, 0))
        # 合法光照进度由模型负责，绘制不会推进时间。
        progress = model.ending_night_progress
        # 平滑曲线使初末光照变化放缓，避免最后突然变黑。
        eased = progress * progress * (3.0 - 2.0 * progress)
        # 透明度只作用于当前绘制器持有的混合层。
        self._night_overlay.set_alpha(round(255 * eased))
        # 同位置叠画两张底图，保留河岸、门和板凳的完整布局。
        surface.blit(self._night_overlay, (0, 0))
        # 角色使用隔离快照，不会通过绘图改写模型。
        actor = model.ending_actor
        # 夜景空镜仍完整绘制，完全离画的角色不需要绘图。
        if actor is not None and actor.x < LOGICAL_SIZE[0] + 32:
            # 脚底阴影跟随位置，步态与画布边界由正式角色绘图处理。
            pygame.draw.ellipse(surface, (39, 49, 63), (actor.x - 21, actor.y - 4, 42, 9))
            # 直接复用现有向右行走帧，不生成新的角色造型。
            draw_actor(actor)

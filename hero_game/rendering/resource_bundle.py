"""保存已经加载的画面资源；不负责读取文件或决定游戏规则。"""

# 数据类只生成资源容器的初始化接口。
from dataclasses import dataclass
# 路径只记录可选的外部游戏声音位置。
from pathlib import Path
# Any 用于动画帧元数据的 JSON 结构。
from typing import Any

# pygame 类型用于标明缓存的是已解码画布。
import pygame


# 一次资源准备产生一个实例，由应用持有并交给绘制器只读使用。
# 图像保持共享缓存，绘制时不修改原图；派生缩放图由绘制器自行保存。
# 数据类生成字段初始化，资源加载与校验由独立工厂完成。
@dataclass
class ResourceBundle:
    # 背景使用完整逻辑画布尺寸。
    background: pygame.Surface
    # 每个角色和朝向对应帧列表与时长元数据。
    animations: dict[tuple[str, str], tuple[list[pygame.Surface], dict[str, Any]]]
    # 每个角色的脚底锚点由资源指定，不与运动坐标混淆。
    anchors: dict[str, tuple[int, int]]
    # 时钟组件缓存后按顺序叠画。
    ui: dict[str, pygame.Surface]
    # 对话框、姓名牌与翻页图标均为可复用透明图。
    dialogue_ui: dict[str, pygame.Surface]
    # 立绘按说话者 ID 查询，内容与对白数据分离。
    portraits: dict[str, pygame.Surface]
    # 时钟的逻辑坐标不随窗口缩放改变。
    clock_position: tuple[int, int]
    # 找不到中文字体时使用英文备用文字。
    font_path: str | None
    # 没有外部声音时由应用生成基础提示音。
    landing_sound: Path | None = None
    # 外部背景已有木门时复用其纹理；基础资源由动态层绘制木门。
    baked_exit_door: bool = False
    # 可选门外底图只替换结局显示，未提供时由结局绘制器生成基础画面。
    ending_background: pygame.Surface | None = None
    # 夜景与夕阳底图使用完全相同布局，仅供结局光照渐变。
    ending_night_background: pygame.Surface | None = None

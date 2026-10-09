"""显式加载外部游戏美术包；它不改变剧情、输入或模拟规则。"""

# JSON 清单只描述图像路径与动画时长。
import json
# 资源根目录与相对路径统一采用 Path。
from pathlib import Path
# Any 标明尚未校验的 JSON 对象。
from typing import Any

# pygame 负责实际解码图像。
import pygame

# 逻辑尺寸用于核对背景是否适合当前布局。
from hero_game.config import LOGICAL_SIZE
# 共享有限数值边界也处理超大整数，动画总周期不允许溢出。
from hero_game.model.numeric import finite_number
# 基础方向和系统字体查找可由两类资源共用。
from hero_game.rendering.generated_resources import DIRECTIONS, find_font
# 加载完成后返回同一资源接口，不让绘制器区分来源。
from hero_game.rendering.resource_bundle import ResourceBundle

# 对话组件尺寸属于绘制协议，缺件或尺寸不符不能悄悄遮挡正文。
DIALOGUE_COMPONENT_SIZES = {"panel": (476, 108), "nameplate": (244, 25), "advance": (12, 8)}


# 将清单路径限制在明确的外部美术目录内，拒绝绝对路径与符号链接越界。
def resource_path(root: Path, relative: str) -> Path:
    # 函数自身保证根路径已规范化，不依赖调用者是否记得处理系统路径别名。
    root = root.resolve()
    # 路径字段必须是非空字符串。
    if not isinstance(relative, str) or not relative:
        # 资源名无效时不尝试自动转换。
        raise ValueError("Resource path must be a nonempty string")
    # 清单沿用以 assets 开头的项目相对路径，也支持资源根相对路径。
    parts = Path(relative).parts
    # 不允许任何上级跳转或绝对路径。
    if not parts or Path(relative).is_absolute() or ".." in parts:
        # 防止配置访问个人文件。
        raise ValueError("Resource path must stay inside the asset directory")
    # 去除兼容的 assets 前缀后始终从传入的资源根解析。
    suffix = Path(*parts[1:]) if parts[0] == "assets" else Path(*parts)
    # resolve 会展开链接，因此随后核对实际位置。
    path = (root / suffix).resolve()
    # 解析后的文件必须仍在资源目录内部。
    if root not in path.parents or not path.is_file():
        # 缺失与越界均不能悄悄略过。
        raise ValueError(f"Resource is missing or outside asset directory: {relative}")
    # 返回已经限制范围的普通文件路径。
    return path


# 读取一份资源 JSON 对象，保留原始解析错误。
def read_object(path: Path) -> dict[str, Any]:
    # 文件由路径校验入口选出，内容仍须单独检查。
    value = json.loads(path.read_text(encoding="utf-8"))
    # 数组等结构不能作为资源清单。
    if not isinstance(value, dict):
        # 报告文件名而不输出清单正文。
        raise ValueError(f"Resource metadata must be an object: {path.name}")
    # 每次读取产生独立数据。
    return value


# 加载显式指定的美术根目录，返回可替换程序绘制资源的缓存。
def load_local_resources(asset_root: Path) -> ResourceBundle:
    # 根目录允许系统 /var 等路径别名，内部文件仍必须留在此根目录中。
    root = asset_root.resolve()
    # 入口清单同样经过范围与存在性检查。
    manifest = read_object(resource_path(root, "manifest.json"))
    # 三个对话组件是固定绘制接口，不能缺失、拼错或混入未知组件。
    dialogue_specification = manifest.get("dialogue")
    # 先验证结构与必需键，再读取任何对话图片。
    if not isinstance(dialogue_specification, dict) or set(dialogue_specification) != set(DIALOGUE_COMPONENT_SIZES):
        # 错误资源包在初始化阶段明确失败，不拖到玩家首次说话。
        raise ValueError("Dialogue UI must provide panel, nameplate and advance")
    # 背景解码后无需透明通道。
    background = pygame.image.load(resource_path(root, manifest["background"])).convert()
    # 当前界面使用固定逻辑尺寸，错误图片不能默默拉伸。
    if background.get_size() != LOGICAL_SIZE:
        # 提前报告尺寸不兼容。
        raise ValueError("Background must be 640 by 360")
    # 旧资源包不要求结局图片，省略字段时保留程序绘制的基础场景。
    ending_background = None
    # 显式声明的结局图片必须存在且符合尺寸，不能用回退掩盖错误配置。
    if "ending_background" in manifest:
        # 与办公室底图共用路径边界，拒绝越界文件和无效路径。
        ending_background = pygame.image.load(resource_path(root, manifest["ending_background"])).convert()
        # 结局沿用同一逻辑画布，不允许加载器静默拉伸。
        if ending_background.get_size() != LOGICAL_SIZE:
            # 在进入结局前报告错误，不等待游戏胜利才暴露缺件。
            raise ValueError("Ending background must be 640 by 360")
    # 夜景同样可选，旧美术包仍可由绘制器生成基础暗色端点。
    ending_night_background = None
    # 显式夜景字段有与白天底图相同的路径和尺寸契约。
    if "ending_night_background" in manifest:
        # 所有外部文件必须保持在用户显式指定的资源根内。
        ending_night_background = pygame.image.load(resource_path(root, manifest["ending_night_background"])).convert()
        # 两张底图必须逐像素对齐，加载器不能静默缩放。
        if ending_night_background.get_size() != LOGICAL_SIZE:
            # 在进入游戏前报告无效资源。
            raise ValueError("Ending night background must be 640 by 360")
    # 帧缓存与锚点都由本次加载独立创建。
    animations, anchors = {}, {}
    # 两个游戏角色均必须具备完整的四向资源。
    for kind in ("hero", "slime"):
        # 查找角色对应资源配置，缺失键明确失败。
        specification = manifest["actors"][kind]
        # 锚点要求两个真实整数。
        anchor = specification["anchor"]
        # 固定帧尺寸为64像素，锚点必须落在图片内部。
        if len(anchor) != 2 or any(type(value) is not int or not 0 <= value <= 64 for value in anchor):
            # 不将错误锚点传播到绘图偏移。
            raise ValueError("Actor anchor must contain two coordinates inside a 64px frame")
        # 保存不可变坐标对，供绘制器读取。
        anchors[kind] = tuple(anchor)
        # 逐个验证朝向，不因缺少一方向而混用其他图。
        for direction in DIRECTIONS:
            # 角色清单引用另一份动画元数据。
            metadata_path = resource_path(root, specification["animations"][direction])
            # 原始帧时长必须保留。
            metadata = read_object(metadata_path)
            # 帧列表不能缺失或为空。
            entries = metadata["frames"]
            # 无帧动画无法提供待机图。
            if not isinstance(entries, list) or not entries:
                # 阻止后续索引或取余失败。
                raise ValueError("Animation frames must be a nonempty list")
            # 待机索引必须指向现有帧，bool不当作整数。
            idle = metadata["idle_frame"]
            # 负索引会隐藏错误，因此显式拒绝。
            if type(idle) is not int or not 0 <= idle < len(entries):
                # 定位到动画接口而不输出素材内容。
                raise ValueError("Idle frame is outside animation")
            # 解码列表由资源对象持有。
            frames = []
            # 周期独立累计，单帧有限不能保证多帧之和仍有限。
            cycle_duration_ms = 0.0
            # 每帧分别核对时长和尺寸。
            for entry in entries:
                # 帧时长单位为毫秒；共享检查将极大整数溢出转换为ValueError。
                duration = finite_number(entry["duration_ms"], "frame duration_ms")
                # 零和负值不能形成有效动画帧。
                if duration <= 0:
                    # 取余周期必须为有限正数。
                    raise ValueError("Frame duration must be positive finite milliseconds")
                # 在解码本帧之前确认总周期仍有限，防止绘制取余得到无效进度。
                cycle_duration_ms = finite_number(cycle_duration_ms + duration, "animation cycle duration_ms")
                # 帧名必须是非空相对路径，不能用资产根内的绝对路径绕过规则。
                frame_name = entry["file"]
                # 在拼接前检查字段，避免Path自动丢弃前缀目录。
                if not isinstance(frame_name, str) or not Path(frame_name).parts or Path(frame_name).is_absolute() or ".." in Path(frame_name).parts:
                    # 错误帧路径不交给图像解码器。
                    raise ValueError("Frame name must be a nonempty relative path without parent traversal")
                # 帧文件相对于当前动画元数据目录定位。
                frame_relative = (metadata_path.parent / frame_name).relative_to(root)
                # 再次经过路径校验，防止帧路径上级跳转或链接越界。
                path = resource_path(root, frame_relative.as_posix())
                # 保留透明像素，避免角色带方形底色。
                frame = pygame.image.load(path).convert_alpha()
                # 现有渲染锚点与呼吸姿态使用64像素帧。
                if frame.get_size() != (64, 64):
                    # 不自动拉伸错误帧。
                    raise ValueError("Actor frame must be 64 by 64")
                # 将有效帧加入独立缓存。
                frames.append(frame)
            # 资源来源不同，提供给绘制器的接口保持一致。
            animations[kind, direction] = (frames, metadata)
    # 时钟组件按固定名称逐个加载。
    ui = {}
    # 时钟图形保持现有美术样式。
    for name in ("clock_housing", "shift_end_1730", "colon", *(f"digit_{digit}" for digit in range(10))):
        # 所有组件路径仍受到资源目录约束。
        ui[name] = pygame.image.load(resource_path(root, f"ui/{name}.png")).convert_alpha()
    # 对话组件引用清单中的对应图形，逐个验证固定布局尺寸。
    dialogue_ui = {}
    # 每个必需组件都通过同一套文件范围与图像尺寸检查。
    for name, expected_size in DIALOGUE_COMPONENT_SIZES.items():
        # 图像已解码到独立缓存，保留边缘透明像素。
        image = pygame.image.load(resource_path(root, dialogue_specification[name])).convert_alpha()
        # 不自动拉伸错误图片，避免正文和点击区域失配。
        if image.get_size() != expected_size:
            # 错误只标记组件ID和技术尺寸，不输出任何创作正文。
            raise ValueError(f"Dialogue UI {name} must have size {expected_size}")
        # 合法组件才放入给绘制器使用的缓存。
        dialogue_ui[name] = image
    # 角色立绘由稳定ID对应，不借用视频作者头像。
    portraits = {kind: pygame.image.load(resource_path(root, f"portraits/{kind}.png")).convert_alpha()
                 # 正式游戏仅有当前两个角色。
                 for kind in ("hero", "slime")}
    # 时钟位置必须是画布内的两个整数。
    position = manifest["clock_position"]
    # 组件应完整位于画布内。
    if len(position) != 2 or any(type(value) is not int for value in position):
        # 不将无效值交给pygame绘制。
        raise ValueError("Clock position must contain two integers")
    # 当前时钟宽112高54，超出画布时明确失败。
    if not (0 <= position[0] <= 528 and 0 <= position[1] <= 306):
        # 防止无意裁掉时钟。
        raise ValueError("Clock must fit inside the logical canvas")
    # 保持所有资源加载行为在显式工厂中。
    return ResourceBundle(
        # 已解码背景由应用持有。
        background=background,
        # 帧与元数据缓存由当前资源实例拥有。
        animations=animations,
        # 两个脚底锚点与帧大小已经校验。
        anchors=anchors,
        # 时钟图形不参与游戏规则。
        ui=ui,
        # 对话图形与台词配置独立。
        dialogue_ui=dialogue_ui,
        # 立绘只用于显示说话者。
        portraits=portraits,
        # 保存不变的时钟坐标对。
        clock_position=tuple(position),
        # 系统字体不复制到包中。
        font_path=find_font(),
        # 只有显式本机美术包加载才读取它的落地声音。
        landing_sound=resource_path(root, "audio/slime_land.wav"),
        # 当前完整场景美术的原门板由动态绘制器复用纹理。
        baked_exit_door=True,
        # 独立底图只供结局绘制，不参与模型、碰撞或追逐。
        ending_background=ending_background,
        # 夜景图仅参与显示，不改变游戏规则或计时状态。
        ending_night_background=ending_night_background,
    )

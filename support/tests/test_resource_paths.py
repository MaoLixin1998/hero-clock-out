"""检查外部美术路径只访问明确目录，不依赖项目的私人素材。"""

# JSON 只构造受控清单，不复制项目素材或台词。
import json
# 两个可选场景字段共用相同路径与尺寸契约。
from itertools import product
# 虚拟显示避免图像格式转换打开桌面窗口。
import os
# 临时目录让路径测试不触碰真实图片、录音或用户文件。
import tempfile
# 标准测试框架验证正常路径与越界拒绝。
import unittest
# 环境补丁只在当前图像解码测试期间生效。
from unittest.mock import patch
# Path 创建受控文件和符号链接。
from pathlib import Path

# Pillow 创建纯色技术占位PNG，不依赖实际游戏美术。
from PIL import Image
# pygame 真实解码这些PNG并执行透明格式转换。
import pygame

# 使用真实路径入口检查存在性与目录边界。
from hero_game.rendering.local_resources import load_local_resources, resource_path


# 保存指定尺寸的纯色占位PNG；图像和文件句柄在当前调用内完成释放。
def write_placeholder_png(path: Path, size: tuple[int, int]) -> None:
    # 只创建测试所需的父目录，不接触真实素材目录。
    path.parent.mkdir(parents=True, exist_ok=True)
    # 独立RGBA画布让解码测试涵盖透明格式转换。
    with Image.new("RGBA", size, (80, 100, 120, 255)) as image:
        # 写入真正PNG，而不是依赖模拟解码器返回预期尺寸。
        image.save(path)


# 每项只创建必要的技术占位文件，测试结束后自动清理。
class ResourcePathChecks(unittest.TestCase):
    # 可选结局资源兼容旧清单；显式提供时须真实解码，并拒绝缺失、越界或尺寸错误。
    def test_optional_ending_background_is_loaded_and_validated(self) -> None:
        # 每项使用独立资源包，不依赖任何私人场景图片。
        for field, case in product(("ending_background", "ending_night_background"), ("absent", "valid", "wrong_size", "missing", "escape")):
            # 子项名称明确区分兼容路径与失败边界。
            with self.subTest(field=field, case=case), tempfile.TemporaryDirectory() as temp:
                # 根目录规范化后仍由实际加载器检查相对路径。
                root = Path(temp).resolve()
                # 其余资源均完整，避免无关缺件掩盖结局图片错误。
                self.write_resource_pack(root)
                # 读取受控清单，只修改本项的可选字段。
                manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
                # 旧清单完全不声明该字段，不能要求它新增文件。
                if case != "absent":
                    # 正常与尺寸错误使用同一路径，缺失案例故意不写文件。
                    manifest[field] = "ending.png"
                    # 真实存在的PNG才能验证解码后的尺寸。
                    if case in ("valid", "wrong_size"):
                        # 固定画布或错误小图分别触发成功与尺寸失败。
                        write_placeholder_png(root / "ending.png", (640, 360) if case == "valid" else (12, 8))
                    # 上级跳转不能作为可选增强读取。
                    if case == "escape":
                        # 路径错误必须明确失败，不能自动退回基础图。
                        manifest[field] = "../ending.png"
                # 保存实际JSON，测试走真正的解析和图像加载路径。
                (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                # 解码转换只使用虚拟显示，不创建桌面窗口。
                with patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy"}):
                    # 生命周期由测试显式建立，不让资源加载器启动设备。
                    pygame.display.init()
                    # 正常和失败分支都清理当前显示。
                    try:
                        # 一像素显示足以提供图像转换格式。
                        pygame.display.set_mode((1, 1))
                        # 旧清单和合法新图均须完整加载。
                        if case in ("absent", "valid"):
                            # 返回实际缓存，不能使用模拟Surface绕过PNG读取。
                            resources = load_local_resources(root)
                            # 未声明时没有隐藏的图片依赖。
                            if case == "absent":
                                # 基础场景由绘制器承担。
                                self.assertIsNone(getattr(resources, field))
                            # 新图保持原始逻辑尺寸。
                            else:
                                # 合法资源已经被真正解码。
                                self.assertEqual(getattr(resources, field).get_size(), (640, 360))
                        # 所有显式错误都应失败，不能被可选默认掩盖。
                        else:
                            # 无效路径和尺寸统一在加载边界报告ValueError。
                            with self.assertRaises(ValueError):
                                # 执行实际加载流程。
                                load_local_resources(root)
                    # 测试不持有其他pygame模块，因此仅释放显示。
                    finally:
                        # 连续子项之间不残留旧窗口。
                        pygame.display.quit()

    # 创建完整的临时资源协议样例，可分别覆盖周期与对话组件尺寸边界。
    def write_resource_pack(
        # 当前测试实例只组织临时数据，不持有pygame生命周期。
        self,
        # 外部资源根目录由每项测试独立创建。
        root: Path,
        # 毫秒时长为不可变元组，避免默认列表在测试之间共享。
        durations_ms: tuple[float, ...] = (100.0,),
        # 正常面板尺寸固定，测试可显式注入错误尺寸。
        panel_size: tuple[int, int] = (476, 108),
    ) -> None:
        # 纯色背景符合固定逻辑画布，不包含创作画面。
        write_placeholder_png(root / "background.png", (640, 360))
        # 所有朝向可使用同一占位帧，本项只测资源协议与边界。
        write_placeholder_png(root / "frames/frame.png", (64, 64))
        # 每帧引用真实存在的PNG，时长由当前测试单独指定。
        metadata = {"idle_frame": 0, "frames": [{"file": "frame.png", "duration_ms": duration} for duration in durations_ms]}
        # 写入真正JSON，验证正式读取与解析路径。
        (root / "frames/animation.json").write_text(json.dumps(metadata), encoding="utf-8")
        # 独立描述预期对话协议，面板可用错误大小触发加载边界。
        component_sizes = {"panel": panel_size, "nameplate": (244, 25), "advance": (12, 8)}
        # 创建三张真实UI图，而不是让测试返回模拟Surface。
        for name, size in component_sizes.items():
            # 每个组件路径可被正式清单独立引用。
            write_placeholder_png(root / "ui" / f"dialogue_{name}.png", size)
        # 时钟组件提供完整的解码依赖，避免缺失文件掩盖待测错误。
        clock_sizes = {"clock_housing": (112, 54), "shift_end_1730": (112, 20), "colon": (5, 22)}
        # 十个数字有独立文件，但它们都只是同尺寸技术占位图。
        clock_sizes.update({f"digit_{digit}": (10, 22) for digit in range(10)})
        # 逐个写入时钟图，加载器能完成真实资源组装。
        for name, size in clock_sizes.items():
            # 路径和尺寸遵守正式接口，内容无需涉及任何剧情。
            write_placeholder_png(root / "ui" / f"{name}.png", size)
        # 正式模型的两个角色均需要立绘路径。
        for kind in ("hero", "slime"):
            # 占位立绘使用独立PNG，加载时不读取项目人物图。
            write_placeholder_png(root / "portraits" / f"{kind}.png", (64, 64))
        # 声音在本工厂仅检查路径，测试不声称验证音频解码或听感。
        (root / "audio").mkdir()
        # 技术占位文件满足资源路径存在性，声音播放器不参与当前测试。
        (root / "audio/slime_land.wav").write_bytes(b"placeholder")
        # 每个方向引用同一份受控元数据，避免生成重复图像。
        animations = {direction: "frames/animation.json" for direction in ("down", "left", "up", "right")}
        # 完整资源清单对应真实生成的目录与文件。
        manifest = {
            # 背景路径相对于明确的外部资源根。
            "background": "background.png",
            # 两种角色都遵循相同锚点和完整四向接口。
            "actors": {kind: {"anchor": [32, 58], "animations": animations} for kind in ("hero", "slime")},
            # 三种对话组件使用独立路径。
            "dialogue": {name: f"ui/dialogue_{name}.png" for name in component_sizes},
            # 时钟位置完整留在逻辑画布内。
            "clock_position": [264, 12],
        }
        # 序列化到本次临时目录，不写入正式资源或Git。
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # 允许资源根相对路径和历史assets前缀，结果指向同一个真实文件。
    def test_relative_file_and_legacy_assets_prefix_resolve_inside_root(self) -> None:
        # 创建完全受控的美术目录，不读取实际创作资产。
        with tempfile.TemporaryDirectory() as temp:
            # 解析系统临时路径别名，保持测试对macOS与Linux一致。
            root = Path(temp).resolve()
            # 准备一个普通文件，内容无须是图片，因为本项只测路径。
            (root / "frame.png").write_bytes(b"placeholder")
            # 不带assets前缀的资源根相对路径可正常访问。
            self.assertEqual(resource_path(root, "frame.png"), root / "frame.png")
            # 旧清单使用assets前缀时应得到同一文件。
            self.assertEqual(resource_path(root, "assets/frame.png"), root / "frame.png")

    # 拒绝空值、当前目录、上级跳转、绝对路径与缺失文件。
    def test_invalid_or_escaping_paths_fail_with_clear_value_error(self) -> None:
        # 受控根目录内外各有文件，不能依赖缺失文件假装阻止越界。
        with tempfile.TemporaryDirectory() as temp:
            # 父目录同时容纳资源根和外部占位文件。
            parent = Path(temp).resolve()
            # 明确的美术资源目录由加载调用者提供。
            root = parent / "assets"
            # 创建真实目录，后续路径检查必须以它为边界。
            root.mkdir()
            # 外部文件确实存在，测试上级跳转仍应被拒绝。
            outside = parent / "outside.png"
            # 文件内容只作存在性标记。
            outside.write_bytes(b"outside")
            # 根内也存在普通文件，以检查绝对路径政策与存在性无关。
            inside = root / "inside.png"
            # 使用技术占位内容，不制造或复制创作素材。
            inside.write_bytes(b"inside")
            # 每种路径都不满足明确的资源相对路径契约。
            for relative in ("", ".", "../outside.png", str(outside), str(inside), "missing.png"):
                # 标记路径，失败时可以快速分清结构、存在性或越界问题。
                with self.subTest(relative=relative):
                    # 错误必须是模型理解的明确边界错误，而不是索引崩溃。
                    with self.assertRaises(ValueError):
                        # 真实入口负责检查，测试不重复实现路径算法。
                        resource_path(root, relative)

    # 符号链接即使名字在资源根内，也不能指向根外的真实文件。
    def test_symlink_cannot_escape_the_asset_root(self) -> None:
        # 临时父目录提供一个确实存在的外部文件。
        with tempfile.TemporaryDirectory() as temp:
            # 解析根路径，避免系统临时目录别名影响比较。
            parent = Path(temp).resolve()
            # 声明本次允许访问的资源边界。
            root = parent / "assets"
            # 创建目录，不修改任何项目资源。
            root.mkdir()
            # 受控外部文件不是允许的资源。
            outside = parent / "outside.png"
            # 占位内容只用于证明目标存在。
            outside.write_bytes(b"outside")
            # 链接名看似在根内，但实际目标在根外。
            (root / "linked.png").symlink_to(outside)
            # resolve之后必须识别越界，不按表面路径放行。
            with self.assertRaises(ValueError):
                # 真实入口验证符号链接后的路径。
                resource_path(root, "linked.png")

    # 缺失或未知对话组件必须在资源加载前明确拒绝。
    def test_dialogue_ui_requires_exact_component_names(self) -> None:
        # 每个错误清单都拥有独立目录，不让上一例文件干扰结果。
        for specification in ({"panel": "panel.png"}, {"panel": "p.png", "nameplate": "n.png", "advance": "a.png", "extra": "e.png"}):
            # 本项只需清单，组件协议错误应早于图像读取。
            with tempfile.TemporaryDirectory() as temp:
                # 规范化系统临时路径别名。
                root = Path(temp).resolve()
                # 缺省背景字段故意未提供，确保错误来自更早的UI协议检查。
                (root / "manifest.json").write_text(json.dumps({"dialogue": specification}), encoding="utf-8")
                # 只接收明确组件错误，不能由缺背景等无关错误假通过。
                with self.assertRaisesRegex(ValueError, "Dialogue UI"):
                    # 实际加载入口负责协议检查。
                    load_local_resources(root)

    # 单帧有限但周期之和溢出的动画必须在取余绘制之前失败。
    def test_animation_cycle_overflow_is_rejected_during_actual_loading(self) -> None:
        # 全部图像都在临时目录真实生成，避免本机素材影响边界结论。
        with tempfile.TemporaryDirectory() as temp:
            # 当前资源根只属于这一项测试。
            root = Path(temp).resolve()
            # 两帧各自有限，但总毫秒时长会溢出。
            self.write_resource_pack(root, durations_ms=(1e308, 1e308))
            # 虚拟显示只在本项作用，退出后还原环境变量。
            with patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy"}):
                # 图片convert需要显示格式，初始化不会创建真实桌面窗口。
                pygame.display.init()
                # 错误资源路径也必须明确释放显示模块。
                try:
                    # 一像素虚拟画布足以建立RGBA转换格式。
                    pygame.display.set_mode((1, 1))
                    # 明确期望周期错误，不接受无关图像或文件异常。
                    with self.assertRaisesRegex(ValueError, "animation cycle"):
                        # 真实PNG与JSON解码路径应拒绝非有限总周期。
                        load_local_resources(root)
                # 无论加载是否按预期失败都清理当前显示生命周期。
                finally:
                    # 当前测试没有启动字体和声音，不清理不属于它的其他模块。
                    pygame.display.quit()

    # 正确组件尺寸可实际解码组装，错误面板不能被自动拉伸后放行。
    def test_dialogue_ui_dimensions_are_checked_with_real_png_files(self) -> None:
        # 同时验证合法尺寸能加载，以及错误尺寸确实由尺寸边界拒绝。
        for panel_size in ((476, 108), (1, 1)):
            # 每次尺寸检查使用独立的真实资源目录。
            with tempfile.TemporaryDirectory() as temp:
                # 规范化路径后交给正式加载入口。
                root = Path(temp).resolve()
                # 两个正常帧时长合计200毫秒，避免周期错误掩盖尺寸检查。
                self.write_resource_pack(root, durations_ms=(75.0, 125.0), panel_size=panel_size)
                # 使用短暂的虚拟显示环境执行真正PNG解码。
                with patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy"}):
                    # 明确创建当前测试所需的显示格式。
                    pygame.display.init()
                    # 成功与失败都走同一个释放分支。
                    try:
                        # 一像素窗口不会改变被解码资源的尺寸。
                        pygame.display.set_mode((1, 1))
                        # 正常尺寸应完成完整资源加载。
                        if panel_size == (476, 108):
                            # 得到正式资源容器，未使用模拟返回值。
                            resources = load_local_resources(root)
                            # 解码后的面板大小和技术协议一致。
                            self.assertEqual(resources.dialogue_ui["panel"].get_size(), (476, 108))
                            # 元数据保持实际帧时长，未被默默统一成默认值。
                            self.assertEqual([frame["duration_ms"] for frame in resources.animations["hero", "down"][1]["frames"]], [75.0, 125.0])
                        # 错误图片必须由明确尺寸检查拒绝。
                        else:
                            # 错误不能由缺文件或解码失败代替。
                            with self.assertRaisesRegex(ValueError, "Dialogue UI panel"):
                                # 同一真实工厂处理错误的面板PNG。
                                load_local_resources(root)
                    # 释放当前测试的虚拟显示。
                    finally:
                        # 反复运行尺寸案例也不会保留旧窗口。
                        pygame.display.quit()

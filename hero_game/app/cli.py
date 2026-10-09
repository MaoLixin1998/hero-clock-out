"""正式游戏入口，不加载视频制作脚本或本机剧情覆盖。"""

# 参数通过标准解析器校验。
import argparse
# SDL驱动只在显式启动时设置。
import os
# 外部游戏美术通过明确路径提供。
from pathlib import Path
# 将真实失败原因与退出状态交给终端。
import sys

# 导入pygame不创建窗口。
import pygame

# 应用协调已准备好的依赖。
from hero_game.app.application import Application
# 声音设备在明确start阶段启动。
from hero_game.app.audio import LandingAudio
# 正式输入策略由独立控制器实现。
from hero_game.app.input_controller import InputController
# 正式配置随包分发。
from hero_game.config import LOGICAL_SIZE, load_game_presentation
# 应用工厂读取正式数据并显式注入纯模型，核心不反向依赖文件适配器。
from hero_game.app.game_factory import create_game
# 无外部素材时使用完整基础画面。
from hero_game.rendering.generated_resources import create_generated_resources
# 外部美术只替换显示资源。
from hero_game.rendering.local_resources import load_local_resources
# 绘制器只读取模型与资源。
from hero_game.rendering.renderer import Renderer


# 解析非负帧数，零表示持续运行。
def nonnegative_integer(value: str) -> int:
    # 非整数由argparse报告参数错误。
    number = int(value)
    # 负数不能代表有效限制。
    if number < 0:
        # 不将负数误解释为持续运行。
        raise argparse.ArgumentTypeError("帧数必须为非负整数")
    # 合法零值原样保留。
    return number


# 组装正式游戏，设备在所有成功与失败路径都释放。
def run_game(arguments: argparse.Namespace) -> int:
    # 只在显式无显示模式下覆盖SDL显示驱动。
    if arguments.headless:
        # 赋值必须早于显示初始化。
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    # 窗口创建后发生的任何错误都走统一清理。
    try:
        # 显式初始化显示模块。
        pygame.display.init()
        # 字体生命周期由同一入口管理。
        pygame.font.init()
        # 窗口像素由逻辑尺寸乘缩放倍数得到。
        window = pygame.display.set_mode(tuple(size * arguments.scale for size in LOGICAL_SIZE))
        # 游戏界面文字从包内正式数据读取。
        presentation = load_game_presentation()
        # 标题仅用于显示，不参与状态判断。
        pygame.display.set_caption(presentation["windowTitle"])
        # 纯代码包不依赖本机图片，外部美术必须明确提供。
        resources = create_generated_resources() if arguments.assets is None else load_local_resources(arguments.assets)
        # 应用层读取正式规则与游戏对白，构造无文件依赖的模型。
        model = create_game()
        # 资源与显示文字显式注入。
        renderer = Renderer(model, resources=resources, presentation=presentation)
        # 正式输入默认失焦暂停、失败后重开。
        input_controller = InputController(model, renderer, arguments.scale)
        # 无显示验收不依赖扬声器设备。
        audio = LandingAudio(arguments.silent or arguments.headless, resources.landing_sound)
        # 显式准备音频。
        audio.start()
        # 协调层接收已经准备好的依赖。
        application = Application(model, renderer, window, input_controller, audio,
                                  # 帧数限制与固定步长仅用于启动验收。
                                  frame_limit=arguments.frames, headless=arguments.headless)
        # 从此处开始响应输入与显示帧。
        application.run()
        # 零状态表示完整运行流程成功退出。
        return 0
    # 所有错误路径都释放窗口、字体和声音。
    finally:
        # 重复调用pygame.quit也安全。
        pygame.quit()


# 解析正式游戏参数，普通导入不会启动窗口或读配置。
def main(argv: list[str] | None = None, default_assets: Path | None = None) -> int:
    # 入口只描述游戏，不包含视频拍摄安排。
    parser = argparse.ArgumentParser(description="运行二维追逐小游戏")
    # 逻辑像素保持不变，仅放大显示。
    parser.add_argument("--scale", type=int, choices=(1, 2, 3), default=2)
    # 可选游戏美术根目录不包含视频作者头像。
    parser.add_argument("--assets", type=Path, default=default_assets, help="可选游戏美术根目录")
    # 兼容原来的静音参数。
    parser.add_argument("--silent", "--mute", action="store_true", help="关闭游戏音效")
    # 虚拟驱动用于可重复启动验证。
    parser.add_argument("--headless", action="store_true", help="使用虚拟显示并静音")
    # 零值允许正常交互运行。
    parser.add_argument("--frames", type=nonnegative_integer, default=0, help="完成N帧后退出，0为持续运行")
    # 未知选项明确拒绝。
    arguments = parser.parse_args(argv)
    # 无显示持续循环没有交互出口，必须给出终止帧数。
    if arguments.headless and arguments.frames == 0:
        # 避免验收命令意外永久运行。
        parser.error("--headless需要同时提供大于0的--frames")
    # 应用边界只转换已知的资源与设备失败。
    try:
        # 不访问本机视频扩展。
        return run_game(arguments)
    # 未知编程错误不静默吞掉。
    except (OSError, ValueError, KeyError, TypeError, pygame.error) as error:
        # 保留真实错误原因。
        print(f"游戏启动失败：{error}", file=sys.stderr)
        # 打包验收可识别失败。
        return 1

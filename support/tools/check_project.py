"""统一工作区检查、只读索引检查和可选干净源码包/wheel启动验收。"""

# 解析明确的检查模式。
import argparse
# 给受控子进程设置无窗口和无音频环境。
import os
# 通过参数列表执行测试、安装和游戏启动。
import subprocess
# 使用当前运行解释器，并向终端返回真实失败状态。
import sys
# 独立构建、解包和安装都在自动清理临时目录中进行。
import tempfile
# 项目和快照路径统一使用Path。
from pathlib import Path
# 只解开由本工具白名单生成的源码ZIP。
from zipfile import ZipFile

# 直接脚本方式与python -m使用相同项目导入路径。
if __package__ in {None, ""}:
    # 只设置当前检查进程，不改变系统Python或其他仓库。
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Python规范检查只解析文本或索引blob。
from support.tools import check_code_conventions
# Git范围检查保持工作区与索引的明确区分。
from support.tools import check_git_scope
# 打包始终使用正式白名单快照。
from support.tools.export_game import build_wheel, export_game


# 运行受控技术命令，非零或超时都会保留真实失败原因。
def run_check(command: list[str], directory: Path, environment: dict[str, str] | None = None) -> None:
    # timeout避免GUI误启动或死循环使检查无限等待。
    result = subprocess.run(command, cwd=directory, env=environment, check=False, timeout=120)
    # 子命令未成功即停止统一检查，不能继续打印全部通过。
    if result.returncode != 0:
        # 保留真实返回码和命令入口，不输出私人环境变量。
        raise RuntimeError(f"检查命令失败，返回码{result.returncode}：{command[:3]!r}")


# 从干净正式快照验证源码运行和wheel安装运行，不访问旧本机素材。
def check_package(repository: Path, build_python: str) -> None:
    # 不在项目源码内安装包或创建临时依赖。
    with tempfile.TemporaryDirectory(prefix="hero-package-check-") as temporary:
        # 所有验收产物限制在受控临时根目录。
        folder = Path(temporary)
        # 生成正式源码包，白名单外文件不会复制。
        source_zip, _ = export_game(folder / "source.zip", root=repository)
        # 运行源与安装wheel的环境使用不同目录。
        source_folder = folder / "source"
        # 源码目录从空目录开始。
        source_folder.mkdir()
        # 只解开本工具刚生成并验证CRC的正式ZIP。
        with ZipFile(source_zip) as archive:
            # 内部路径已受selected_entries约束，没有父目录跳转。
            archive.extractall(source_folder)
        # 保留当前解释器依赖环境，显式关闭显示和真实音频设备。
        environment = os.environ.copy()
        # SDL空驱动使程序真正运行绘制流程但不创建窗口。
        environment["SDL_VIDEODRIVER"] = "dummy"
        # 空音频驱动避免自动检查播放声音。
        environment["SDL_AUDIODRIVER"] = "dummy"
        # 清除调用者注入的源码路径，避免干净快照偷偷借用原包。
        environment.pop("PYTHONPATH", None)
        # 限定三帧启动，验证默认配置、资源回退和退出清理。
        run_check([sys.executable, "main.py", "--headless", "--frames", "3", "--silent"], source_folder, environment)
        # wheel也只从同一正式白名单快照构建。
        wheel = build_wheel(folder / "wheel", root=repository, python_executable=build_python)
        # 将wheel离线安装到全新目录，不改项目虚拟环境。
        installed = folder / "installed"
        # --no-index和--no-deps保证验收不会下载或升级现有依赖。
        run_check([sys.executable, "-m", "pip", "install", "--no-cache-dir", "--no-index", "--no-deps", "--target", str(installed), str(wheel)], folder, environment)
        # 运行安装副本时只额外加入安装目录，旧项目源码不在搜索路径。
        installed_environment = environment.copy()
        # console脚本从installed/bin运行，需要显式标明target模块位置。
        installed_environment["PYTHONPATH"] = str(installed)
        # 实际运行生成的console入口，验证pyproject入口名与打包路径。
        run_check([sys.executable, str(installed / "bin/hero-clock-out"), "--headless", "--frames", "3", "--silent"], folder, installed_environment)
        # 模块入口也必须来自已安装副本，防止漏打包__main__.py。
        run_check([sys.executable, "-m", "hero_game", "--headless", "--frames", "3", "--silent"], folder, installed_environment)
    # 临时目录已清理后才报告完整验收通过。
    print("打包验收通过：干净源码ZIP启动、wheel离线安装、已安装console与模块入口均运行3帧并退出。")


# 工作区执行测试；索引模式只解析blob，绝不执行索引中的代码。
def main(argv: list[str] | None = None) -> int:
    # 提供统一技术检查入口，不安装hook或修改全局Git设置。
    parser = argparse.ArgumentParser(description=__doc__)
    # 默认根目录按当前脚本确定，测试可传临时目录。
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    # 提交前只读索引模式同时关闭工作区测试。
    parser.add_argument("--staged", action="store_true")
    # 快速人工检查可以跳过测试，但报告不称测试已运行。
    parser.add_argument("--skip-tests", action="store_true")
    # 打包启动验收必须明确选择，不每次格式检查重复构建。
    parser.add_argument("--check-package", action="store_true")
    # 可指定本机已装setuptools>=70的构建解释器，不自动安装。
    parser.add_argument("--build-python", default=sys.executable)
    # 未知参数由标准库拒绝。
    arguments = parser.parse_args(argv)
    # 索引规范检查不执行索引文件，不能混为同一验证范围。
    if arguments.staged and arguments.check_package:
        # 给出明确模式错误，而不是偷偷改成工作区打包。
        parser.error("--staged只读检查索引；请另行以工作区模式运行--check-package。")
    # 统一根目录边界。
    repository = arguments.root.resolve()
    # 两种检查器接收相同根目录和显式索引标志。
    checker_arguments = ["--root", str(repository), *(["--staged"] if arguments.staged else [])]
    # 规范失败时不继续执行测试或构建。
    if check_code_conventions.main(checker_arguments) != 0:
        # 保留规范检查器已经输出的具体问题。
        return 1
    # 索引路径和正式文件编码检查也必须通过。
    if check_git_scope.main(checker_arguments) != 0:
        # 不因语法正常而忽略内容边界失败。
        return 1
    # 有限副作用仅发生在明确的工作区测试和临时打包验收中。
    try:
        # 索引模式永远不运行工作区或索引测试。
        if not arguments.staged and not arguments.skip_tests:
            # 使用当前解释器发现工作区测试，结果明确属于工作区。
            run_check([sys.executable, "-m", "unittest", "discover", "-s", "support/tests", "-v"], repository)
        # 打包测试另需用户选择统一入口的该选项。
        if arguments.check_package:
            # 干净源码与安装副本共享同一组已安装依赖。
            check_package(repository, arguments.build_python)
    # 任何子进程失败、超时或构建异常都转为统一非零状态。
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        # 显示真实检查失败，不宣称全部完成。
        print(f"项目检查未通过：{error}", file=sys.stderr)
        # 返回外层命令可识别的失败状态。
        return 1
    # 明确区分只读索引与工作区，不把结果说成远程CI通过。
    print(f"项目检查通过：{'Git索引只读规范与范围' if arguments.staged else '工作区规范与范围'}；测试{'未执行' if arguments.staged or arguments.skip_tests else '已执行'}。")
    # 所选检查均成功。
    return 0


# 直接运行检查器才执行统一流程。
if __name__ == "__main__":
    # 将成功或失败状态传给终端。
    sys.exit(main())

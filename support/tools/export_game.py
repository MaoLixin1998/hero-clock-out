"""从正式白名单构建源码ZIP或wheel，失败时保留已有可用产物。"""

# 解析导出格式、路径和索引快照选项。
import argparse
# 原子替换成功完成的临时产物。
import os
# 显式调用构建解释器，不通过shell拼接路径。
import subprocess
# 默认使用调用工具的Python解释器，并返回真实退出状态。
import sys
# 临时快照和产物在失败时自动清理。
import tempfile
# 统一项目根目录和输出路径。
from pathlib import Path
# 源码包与wheel均使用标准ZIP容器。
from zipfile import ZIP_DEFLATED, ZipFile

# 支持python support/tools/export_game.py；仅调整当前进程的模块查找入口。
if __package__ in {None, ""}:
    # 使用实际脚本目录定位同一项目，避免依赖终端工作目录。
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 发布与Git检查复用同一允许范围和blob读取方式。
from support.tools.check_git_scope import entry_problems, index_entries, working_entries

# 默认根目录来自工具位置，不扫描其他仓库。
ROOT = Path(__file__).resolve().parents[2]
# 构建必需正式文件不能通过空白快照误报成功。
REQUIRED_FILES = frozenset({"main.py", "dialogue.py", "pyproject.toml", "requirements.txt", "TECHNICAL.md", "AGENTS.md", "hero_game/__init__.py", "hero_game/app/cli.py", "hero_game/data/game.json", "hero_game/data/dialogue.json", "hero_game/data/presentation.json"})
# 固定构建代码只调用已安装setuptools，不插入外部文字或调用游戏入口。
WHEEL_BUILD_COMMAND = "from setuptools.build_meta import build_wheel; import sys; build_wheel(sys.argv[1])"


# 选出完整正式快照并校验，不将本机艺术资源或视频目录复制进去。
def selected_entries(root: Path, staged: bool = False) -> list[tuple[str, bytes, str]]:
    # 解析系统根路径后只检查项目内部链接。
    repository = Path(root).resolve()
    # 明确区分工作区文件和Git索引原始blob。
    entries = index_entries(repository) if staged else working_entries(repository)
    # UTF-8、JSON和路径检查不执行任何快照代码。
    problems = entry_problems(entries)
    # 快照必须包含可安装游戏的正式入口和包内配置。
    missing = REQUIRED_FILES - {path for path, _, _ in entries}
    # 缺失文件和越界文件都阻止构建，已有产物不会被打开。
    if problems or missing:
        # 只显示技术路径和失败原因，不展开私人正文。
        raise ValueError("正式快照不完整或不合法：" + "; ".join([*problems, *[f"缺少{path}" for path in sorted(missing)]]))
    # 完整快照可用于源码ZIP或wheel构建。
    return entries


# 返回白名单内已存在的相对路径，供技术审阅和筛选测试使用。
def public_files(root: Path = ROOT) -> list[Path]:
    # 这里只选择路径；构建入口另行要求必需文件齐全。
    return [Path(path) for path, _, _ in working_entries(Path(root).resolve())]


# 把正式快照写入受控临时目录，供安装包构建与独立运行检查使用。
def write_snapshot(destination: Path, entries: list[tuple[str, bytes, str]]) -> None:
    # 快照目录必须为空，避免混入先前本机内容。
    if destination.exists() and any(destination.iterdir()):
        # 禁止在非空目录内叠加构建。
        raise ValueError("正式快照目标目录必须为空。")
    # 创建必要的快照根目录。
    destination.mkdir(parents=True, exist_ok=True)
    # 路径已由同一策略验证，不允许自行传入越界条目。
    problems = entry_problems(entries)
    # 直接调用此帮助函数时也保留边界校验。
    if problems:
        # 不写出任何不合法快照内容。
        raise ValueError("; ".join(problems))
    # 依次写入真实UTF-8字节，不引用本机资源。
    for relative, content, _ in entries:
        # 每个快照文件均以项目相对路径定位。
        destination_path = destination / relative
        # 建立包目录和纯技术文档目录。
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        # 原始字节不经换行或编码重新解释。
        destination_path.write_bytes(content)


# 原子构建源码运行包；返回最终路径与实际文件数量。
def export_game(destination: Path | None = None, root: Path = ROOT, staged: bool = False) -> tuple[Path, int]:
    # 先校验全部内容，再创建临时产物。
    entries = selected_entries(root, staged)
    # 默认源码包明确使用source命名，避免误称自带解释器的应用。
    output_path = Path(destination) if destination is not None else Path(root) / "support/tools/output/hero-clock-out-source.zip"
    # 输出本身不能是链接或目录，避免意外覆盖其他对象。
    if output_path.is_symlink() or output_path.is_dir():
        # 构建失败保持链接和原目标不动。
        raise ValueError("源码包输出必须是普通文件路径。")
    # 将目标统一为绝对路径，方便终端报告。
    output_path = output_path.resolve()
    # 输出目录允许创建，但已有ZIP在成功替换前保持完整。
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # 临时文件放在同一文件系统，确保最后替换可以保持原子性。
    with tempfile.TemporaryDirectory(prefix=".source-build-", dir=output_path.parent) as temporary:
        # ZIP只写临时文件，不直接打开旧正式包。
        pending_path = Path(temporary) / output_path.name
        # 以稳定顺序写入正式文件，不递归整个工作目录。
        with ZipFile(pending_path, "w", compression=ZIP_DEFLATED) as archive:
            # 每份文件来自明确快照，工作区之后改动不影响这一份包。
            for relative, content, _ in sorted(entries):
                # ZIP内部路径使用POSIX分隔符。
                archive.writestr(relative, content)
        # 重新打开检查CRC，损坏产物不替换旧包。
        with ZipFile(pending_path) as archive:
            # testzip返回首个损坏成员，None表示容器完整。
            damaged_member = archive.testzip()
            # 真实容器错误必须使构建失败。
            if damaged_member is not None:
                # 只显示损坏的正式路径。
                raise RuntimeError(f"源码包CRC检查失败：{damaged_member}")
        # 只有完整写入并验证后才替换正式输出。
        os.replace(pending_path, output_path)
    # 返回可供后续独立启动检查的真实产物位置。
    return output_path, len(entries)


# 在干净正式快照中构建wheel，要求指定解释器已安装setuptools>=70。
def build_wheel(destination: Path | None = None, root: Path = ROOT, staged: bool = False, python_executable: str = sys.executable) -> Path:
    # 快照验证先于构建工具执行，缺资源不会靠本机目录补齐。
    entries = selected_entries(root, staged)
    # wheel输出目录与源码目录分离，避免构建文件进入Git。
    output_directory = Path(destination) if destination is not None else Path(root) / "support/tools/output"
    # wheel输出目录不能通过末层链接转向其他位置。
    if output_directory.is_symlink() or (output_directory.exists() and not output_directory.is_dir()):
        # 不改变现有文件或链接。
        raise ValueError("wheel输出必须是实际目录。")
    # 成功wheel最后移到同一个本地输出目录。
    output_directory = output_directory.resolve()
    # 确保同一文件系统内可以原子替换。
    output_directory.mkdir(parents=True, exist_ok=True)
    # 构建过程只在临时快照运行，不写原项目源码。
    with tempfile.TemporaryDirectory(prefix=".wheel-build-", dir=output_directory) as temporary:
        # 明确区分纯源码快照与构建输出。
        temporary_root = Path(temporary)
        # 正式快照从空目录开始。
        source_directory = temporary_root / "source"
        # 构建输出也在临时区。
        wheel_directory = temporary_root / "wheel"
        # 不带support/production、本机规范或任何旧稿与媒体。
        write_snapshot(source_directory, entries)
        # 显式创建wheel输出目录。
        wheel_directory.mkdir()
        # 不启用联网和构建隔离安装，直接使用已存在的setuptools。
        result = subprocess.run([python_executable, "-c", WHEEL_BUILD_COMMAND, str(wheel_directory)], cwd=source_directory, capture_output=True, text=True, check=False)
        # 缺少构建依赖或后端失败不能冒称成功。
        if result.returncode != 0:
            # 保留构建诊断，但不会读取私人目录。
            raise RuntimeError(f"wheel构建失败（需已安装setuptools>=70）：{result.stderr.strip()}")
        # 正常构建应恰好产出一份wheel。
        wheels = list(wheel_directory.glob("*.whl"))
        # 多份或没有输出都不是可确定的结果。
        if len(wheels) != 1:
            # 不任意挑选不完整或陌生产物。
            raise RuntimeError("wheel构建未产生唯一有效产物。")
        # 检查wheel容器和包内正式配置是否齐全。
        with ZipFile(wheels[0]) as archive:
            # 正式配置必须随wheel，不从源工作区读取。
            required_data = {f"hero_game/data/{name}.json" for name in ("game", "dialogue", "presentation")}
            # CRC与数据缺失都会阻止替换旧包。
            if archive.testzip() is not None or not required_data.issubset(archive.namelist()):
                # 安装包缺失正式配置无法独立运行。
                raise RuntimeError("wheel容器损坏或缺少正式游戏配置。")
        # 最终文件名由安装元数据生成，不手工伪造版本名。
        output_path = output_directory / wheels[0].name
        # 已有同名链接或目录不能作为产物被替换。
        if output_path.is_symlink() or output_path.is_dir():
            # 构建结果保留在临时目录直到退出，不修改异常目标。
            raise ValueError("已有wheel目标必须是普通文件。")
        # 成功后原子替换同名旧wheel，失败时旧产物一直保留。
        os.replace(wheels[0], output_path)
    # 返回真实wheel文件供离线安装检查。
    return output_path


# 对外命令只生成本地产物，不提交、推送或上传文件。
def main(argv: list[str] | None = None) -> int:
    # 帮助文字明确导出模式和构建依赖。
    parser = argparse.ArgumentParser(description=__doc__)
    # 指定源码ZIP路径；wheel模式将其作为输出目录。
    parser.add_argument("--destination", type=Path)
    # 默认工作区正式快照，提交前可选择索引版本。
    parser.add_argument("--staged", action="store_true")
    # wheel使用预安装setuptools，不下载PyInstaller或其他工具。
    parser.add_argument("--wheel", action="store_true")
    # 支持本机已有构建解释器与运行解释器不同的情况。
    parser.add_argument("--build-python", default=sys.executable)
    # 未知参数由标准库拒绝。
    arguments = parser.parse_args(argv)
    # 应用边界把明确构建失败转为非零退出状态。
    try:
        # 按用户选定格式执行唯一构建流程。
        if arguments.wheel:
            # wheel构建只读取正式快照。
            output = build_wheel(arguments.destination, staged=arguments.staged, python_executable=arguments.build_python)
        # 默认导出不依赖额外构建包的源码ZIP。
        else:
            # 返回值中的数量供其他调用方使用。
            output, _ = export_game(arguments.destination, staged=arguments.staged)
    # 文件权限、配置错误和构建后端错误都保留失败事实。
    except (OSError, ValueError, RuntimeError) as error:
        # 只在工具边界显示友好错误，内部保留异常原因。
        print(f"导出失败：{error}", file=sys.stderr)
        # 非零状态可用于统一检查入口。
        return 1
    # 明确本次产物来自工作区还是索引。
    print(f"已从{'Git索引' if arguments.staged else '工作区'}正式快照导出：{output}")
    # 不宣称安装或运行验收，后续检查独立执行。
    return 0


# 直接执行时才生成本地构建产物。
if __name__ == "__main__":
    # 将构建状态返回调用方。
    sys.exit(main())

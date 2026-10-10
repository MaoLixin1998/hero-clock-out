"""核对正式代码范围与实际索引内容，不导入或执行索引中的源码。"""

# 解析工作区、索引和可选历史检查模式。
import argparse
# 严格解析正式配置，拒绝损坏或非UTF-8数据。
import json
# 正则只约束已审范围的文件名，不推断正文语义。
import re
# 输出真实失败状态。
import sys
# 统一项目相对路径和文件边界。
from pathlib import Path, PurePosixPath

# 支持直接脚本执行，不改系统Python配置。
if __package__ in {None, ""}:
    # 当前进程加入工具所属项目根目录。
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 复用只读Git调用，避免不同工具形成不同的索引读取方式。
from support.tools.check_code_conventions import run_git

# 根文件逐项允许，README与AGENTS只保存技术入口，本机混合版本留在排除目录。
ROOT_FILES = frozenset({".gitignore", ".gitattributes", "README.md", "TECHNICAL.md", "AGENTS.md", "requirements.txt", "pyproject.toml", "main.py", "dialogue.py"})
# 技术工具逐项审阅，本机素材生成脚本保持排除。
TOOL_FILES = frozenset({"__init__.py", "build_audio.py", "build_dialogue_ui.py", "split_gif.py", "export_game.py", "check_code_conventions.py", "check_git_scope.py", "check_project.py"})
# 只有这三份正式配置属于可发布游戏内容，视频覆盖配置放在本机目录。
DATA_FILES = frozenset({"game.json", "dialogue.json", "presentation.json"})
# 经正文审阅的通用规范、项目补充和纯技术文档逐份登记，不递归放行辅助目录。
DOCUMENT_FILES = frozenset({"support/standards/general-coding-standard.md", "support/standards/python-pygame.md", "support/technical/architecture.md", "support/technical/packaging.md"})
# Python模块名采用英文标识符，阻止异常路径、隐藏目录和媒体混入。
MODULE_PART_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")


# 判断仓库相对路径是否属于已经人工审阅的正式技术范围。
def is_allowed_path(path: str) -> bool:
    # POSIX路径与Git一致，反斜杠不作为跨平台逃逸入口。
    relative = PurePosixPath(path)
    # 绝对路径、父层跳转和视频覆盖配置永远不能进入正式包。
    if not relative.parts or relative.as_posix() != path or relative.is_absolute() or ".." in relative.parts or "\\" in path or ".local." in path:
        # 提前拒绝明确不合法的路径。
        return False
    # 精确登记的根文件和技术文档允许进入Git。
    if path in ROOT_FILES or path in DOCUMENT_FILES:
        # 正文是否含混合创作段落仍须人工审阅。
        return True
    # 正式数据只允许包内三份JSON，避免根config出现第二来源。
    if len(relative.parts) == 3 and relative.parts[:2] == ("hero_game", "data"):
        # __init__.py同时使data在wheel中可作为资源包访问。
        return relative.name in DATA_FILES or relative.name == "__init__.py"
    # 工具严格按已经列出的文件名允许。
    if len(relative.parts) == 3 and relative.parts[:2] == ("support", "tools"):
        # 禁止借.py后缀夹带本机素材脚本。
        return relative.name in TOOL_FILES
    # 测试目录只放独立测试模块及可选包入口。
    if len(relative.parts) == 3 and relative.parts[:2] == ("support", "tests"):
        # 测试正文同样需要检查，不把任意目录递归放行。
        return relative.name == "__init__.py" or bool(re.fullmatch(r"test_[a-z0-9_]+\.py", relative.name))
    # 正式运行代码允许按职责增加包，但仅允许普通Python模块。
    if relative.parts[0] == "hero_game" and relative.suffix == ".py":
        # 每层目录必须采用模块命名，末尾允许Python约定的包入口。
        return all(MODULE_PART_PATTERN.fullmatch(part) for part in relative.parts[1:-1]) and (relative.name in {"__init__.py", "__main__.py"} or bool(MODULE_PART_PATTERN.fullmatch(relative.stem)))
    # 本机制作、混合规则、构建产物和未登记路径默认拒绝。
    return False


# 读取Git索引的完整条目并保留真实blob，未合并或链接立即失败。
def index_entries(repository: Path) -> list[tuple[str, bytes, str]]:
    # NUL分隔保留文件名中的空格、Tab和换行。
    raw_entries = run_git(repository, ["ls-files", "--stage", "-z"])
    # 只在全部条目合法后返回完整结果。
    entries = []
    # 每个条目包含文件模式、对象ID、合并阶段和路径。
    for entry in raw_entries.split(b"\0"):
        # 最末尾分隔符没有实际内容。
        if not entry:
            # 跳过空分隔项。
            continue
        # 元数据和路径只按第一个Tab拆开。
        metadata, raw_path = entry.split(b"\t", 1)
        # ASCII元数据不允许容错替换。
        mode, object_id, stage = metadata.decode("ascii").split(" ")
        # 路径严格按UTF-8解码，异常字节不能伪装普通英文文件。
        path = raw_path.decode("utf-8")
        # 未合并索引不能作为完整可发布版本。
        if stage != "0":
            # 不读取冲突文件正文。
            raise RuntimeError(f"索引存在未合并路径：{path!r}")
        # 只允许普通文件，不把符号链接或子模块作为源码。
        if mode not in {"100644", "100755"}:
            # 链接目标文本也不能作为普通blob放行。
            raise RuntimeError(f"索引条目不是普通文件：{path!r}")
        # 通过对象ID读取实际索引，不采用工作区同名文件。
        entries.append((path, run_git(repository, ["cat-file", "blob", object_id]), mode))
    # 返回路径、原始字节和原始模式。
    return entries


# 选择工作区内允许发布的真实文件，本机创作目录不读取正文。
def working_entries(repository: Path) -> list[tuple[str, bytes, str]]:
    # 根文件和文档都按精确清单选择。
    candidates = [repository / path for path in ROOT_FILES | DOCUMENT_FILES]
    # 正式包、已知工具和独立测试按上面的统一策略筛选。
    for folder in ("hero_game", "support/tools", "support/tests"):
        # 枚举文件名时不读取未知文件内容。
        # 仅主体包递归；辅助测试和工具只枚举根文件，不探测本机场景或产物。
        paths = (repository / folder).rglob("*") if folder == "hero_game" else (repository / folder).glob("*")
        # 文件名筛选先于读取，support/production从未进入遍历范围。
        candidates.extend(path for path in paths if is_allowed_path(path.relative_to(repository).as_posix()))
    # 收集所有真实普通文件。
    entries = []
    # 排序去重使源码包和检查结果可复现。
    for path in sorted(set(candidates)):
        # 选中的文件或任何项目内父目录不能是链接。
        relative = path.relative_to(repository)
        # 本机根目录外的系统链接不属于项目内容边界。
        if any((repository / Path(*relative.parts[:length])).is_symlink() for length in range(1, len(relative.parts) + 1)):
            # 不跟随链接读取任何外部正文。
            raise RuntimeError(f"正式文件不能经过符号链接：{relative.as_posix()!r}")
        # 尚未创建的可选技术文档可由打包完整性规则另行判断。
        if not path.is_file():
            # 不将目录或不存在的路径写入结果。
            continue
        # 字节读取不导入、编译或执行代码。
        entries.append((relative.as_posix(), path.read_bytes(), "100644"))
    # 返回与索引模式相同结构。
    return entries


# 检查路径、编码、配置语法和本机覆盖标记；创作语义保留人工审阅。
def entry_problems(entries: list[tuple[str, bytes, str]]) -> list[str]:
    # 一次收集全部问题，避免修一处才看到下一处。
    problems = []
    # 每份正式文件均为UTF-8文本，程序绘制资源无需二进制素材。
    for path, content, mode in entries:
        # 路径策略永远先于正文解析。
        if not is_allowed_path(path):
            # 禁止路径只报名字，不显示私人正文。
            problems.append(f"路径不在正式技术与游戏配置范围：{path!r}")
            # 不读取或展示禁止文件的具体内容。
            continue
        # 非普通文件不能仅凭允许的名字通过。
        if mode not in {"100644", "100755"}:
            # 与索引读取检查保持一致。
            problems.append(f"正式文件不是普通文件：{path!r}")
        # 严格检查文本编码。
        try:
            # 保留零长度包入口合法性。
            text = content.decode("utf-8")
            # 非空文本统一末尾换行。
            if text and not text.endswith("\n"):
                # 该规则也覆盖JSON和技术文档。
                problems.append(f"文本末尾缺少换行：{path!r}")
            # 正式JSON必须能够解析，不执行任意表达式。
            if path.endswith(".json"):
                # JSON语法错误会在下面统一转为失败。
                json.loads(text)
        # 编码或JSON损坏都不能当作成功完成检查。
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            # 只输出异常类型和位置，不展开文件内容。
            problems.append(f"正式文本编码或JSON格式无效：{path!r} ({type(error).__name__})")
    # 稳定排序可用于测试和提交前比对。
    return sorted(set(problems))


# 命令行明确区分工作区和索引；可选历史检查只读取提交树路径。
def main(argv: list[str] | None = None) -> int:
    # 检查器不会安装hook或修改Git全局设置。
    parser = argparse.ArgumentParser(description=__doc__)
    # 从本工具定位项目，也允许受控临时测试根目录。
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    # 提交前应选择真实索引blob，避免工作区修好但索引仍旧。
    parser.add_argument("--staged", action="store_true")
    # 推送前可附加检查分支可达提交，不删除或重写历史。
    parser.add_argument("--history", action="store_true")
    # 非法参数由标准库报错。
    arguments = parser.parse_args(argv)
    # 所有只读操作限制在同一个明确根目录。
    repository = arguments.root.resolve()
    # 任何Git或文件读取错误都会返回真实失败。
    try:
        # 无论哪种模式，都拒绝索引中的越界路径和冲突。
        indexed = index_entries(repository)
        # 索引路径不能因工作区选择排除而隐藏。
        problems = [f"索引路径越界：{path!r}" for path, _, _ in indexed if not is_allowed_path(path)]
        # 只有选定模式的正文被用于内容检查。
        selected = indexed if arguments.staged else working_entries(repository)
        # 对实际blob或实际工作区文本执行同一纯检查。
        problems.extend(entry_problems(selected))
        # 历史检查仅针对真正的可达commit，Codex内部tree引用不是分支提交。
        commits = run_git(repository, ["rev-list", "--all"]).decode("ascii").splitlines() if arguments.history else []
        # 不同提交可能重复相同违规路径，最终统一去重。
        for commit in commits:
            # ls-tree以NUL返回完整路径。
            paths = run_git(repository, ["ls-tree", "-r", "--name-only", "-z", commit])
            # 路径逐项核对，历史不会自动重写。
            for raw_path in paths.split(b"\0"):
                # 输出末尾的空项不代表真实文件。
                if raw_path and not is_allowed_path(raw_path.decode("utf-8")):
                    # 记录足以定位的提交前缀，不读取私人正文。
                    problems.append(f"历史{commit[:12]}路径越界：{raw_path.decode('utf-8')!r}")
    # 损坏Git、非法路径和文件权限错误均不能被吞掉。
    except (OSError, RuntimeError, ValueError, UnicodeError) as error:
        # 明确检查未完成，不称通过。
        print(f"Git范围检查未完成：{error}", file=sys.stderr)
        # 非零状态允许统一入口阻止后续操作。
        return 1
    # 展示全部确定的问题，不输出正文。
    for problem in sorted(set(problems)):
        # 中文错误信息可直接用于本机操作。
        print(problem, file=sys.stderr)
    # 汇总失败或检查范围。
    if problems:
        # 存在问题即为失败。
        return 1
    # 不把可自动判断项通过说成创作正文已自动验收。
    print(f"Git范围检查通过：{'Git索引' if arguments.staged else '工作区'}共{len(selected)}份正式文本；正文用途仍需人工审阅。")
    # 成功返回给终端。
    return 0


# 通过模块执行检查，导入时不调用Git。
if __name__ == "__main__":
    # 将检查返回码传给外层命令。
    sys.exit(main())

#!/usr/bin/env python3
"""只读检查当前项目Python代码的可自动判断规范，不替代语义与架构审查。"""

# 解析工作区与Git索引两种明确的检查模式。
import argparse
# 只解析语法树，不导入或执行被检查的代码。
import ast
# 为Python分词器提供内存中的文本输入。
import io
# 检查中文说明和普通Python标识符的外观形式。
import re
# 通过独立参数调用只读Git命令。
import subprocess
# 将失败状态交给提交钩子或终端。
import sys
# 区分真正的注释、字符串和缩进，避免按文本误判。
import tokenize
# 从脚本位置确定项目，测试也可以传入受控临时目录。
from pathlib import Path


# 只检查程序、回归测试和技术脚本，不读取素材或需求文档。
SOURCE_DIRECTORIES = ("hero_game", "support/tests", "support/tools")
# 根目录兼容入口也属于正式Python代码。
ROOT_SOURCE_FILES = ("main.py", "dialogue.py")
# 本机旧素材脚本包含创作记录，既不上传也不参与技术检查。
EXCLUDED_SOURCE_FILES = frozenset({"support/tools/build_assets.py"})
# 说明至少包含一个常用汉字；文字是否准确仍需人工审查。
CHINESE_TEXT_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
# 普通方法支持单下划线内部前缀，不把任意驼峰名称当作框架例外。
FUNCTION_NAME_PATTERN = re.compile(r"_?[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")
# 类名使用大驼峰形式；名称是否表达实际职责由审查判断。
CLASS_NAME_PATTERN = re.compile(r"[A-Z][A-Za-z0-9]*\Z")
# Python新版本将插值字符串文字分开分词，兼容旧版本只提供STRING的情况。
STRING_CONTENT_TOKEN_TYPES = frozenset({tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", -1)})
# 仅放行Python明确的常用协议方法，不放行自行发明的双下划线名称。
PYTHON_PROTOCOL_METHODS = frozenset(
    {
        # 构造、析构与数据类初始化协议。
        "__init__", "__new__", "__del__", "__post_init__",
        # 对象展示、比较与哈希协议。
        "__str__", "__repr__", "__format__", "__eq__", "__ne__", "__lt__", "__le__",
        # 大小比较和哈希同样沿用Python名称。
        "__gt__", "__ge__", "__hash__", "__bool__",
        # 迭代、容器、调用与上下文管理协议。
        "__iter__", "__next__", "__len__", "__getitem__", "__setitem__", "__contains__",
        # 同步和异步上下文协议。
        "__call__", "__enter__", "__exit__", "__aenter__", "__aexit__", "__aiter__", "__anext__",
        # 属性管理协议。
        "__getattr__", "__getattribute__", "__setattr__", "__delattr__",
    }
)
# unittest生命周期必须保留库规定的名称，且只对测试类的直接方法生效。
UNITTEST_METHODS = frozenset({"setUp", "tearDown", "setUpClass", "tearDownClass", "asyncSetUp", "asyncTearDown"})


# 读取连续且同缩进的上方注释，确认其中确有中文说明。
def has_chinese_comment_above(line_number: int, indentation: int, comments: dict) -> bool:
    # 从对应语句紧邻的上一行开始，空行会中断说明关系。
    previous_line = line_number - 1
    # 多行说明可以包含英文接口名，只要整块说明中有中文。
    while previous_line in comments:
        # 注释所在列必须与语句缩进相同。
        comment = comments[previous_line]
        # 不把父级或子级的说明借给当前语句。
        if comment.start[1] != indentation:
            # 缩进不同时说明块已经结束。
            return False
        # 至少一个汉字说明当前块不是纯英文或占位符。
        if CHINESE_TEXT_PATTERN.search(comment.string):
            # 已满足自动检查能够确认的中文位置要求。
            return True
        # 继续读取同一说明块的更早一行。
        previous_line -= 1
    # 紧邻位置没有同缩进中文说明。
    return False


# 提取基类表达式末尾名称，仅用于限定已登记的框架命名例外。
def base_name(expression: ast.expr) -> str:
    # 直接导入的基类使用普通名称节点。
    if isinstance(expression, ast.Name):
        # 返回明确的基类标识符。
        return expression.id
    # 通过库别名引用的基类保存在属性节点。
    if isinstance(expression, ast.Attribute):
        # 这里只判断语法形式，不声称已经验证运行时继承关系。
        return expression.attr
    # 动态构造的基类不自动享有命名豁免。
    return ""


# 判断直接类方法是否属于明确登记的语言或框架名称例外。
def is_framework_method(node: ast.AST, parent: ast.AST | None) -> bool:
    # 自由函数和嵌套函数不能借用类方法例外。
    if not isinstance(parent, ast.ClassDef):
        # 交给普通Python函数命名规则检查。
        return False
    # Python协议方法只允许在类中使用。
    if node.name in PYTHON_PROTOCOL_METHODS:
        # 已知协议名称可以沿用双下划线形式。
        return True
    # 收集该类直接声明的基类名称，不推断未知继承链。
    bases = {base_name(base) for base in parent.bases}
    # unittest生命周期名称仅在明确的测试类中放行。
    if bases & {"TestCase", "IsolatedAsyncioTestCase"} and node.name in UNITTEST_METHODS:
        # 不能改名的测试入口遵守标准库协议。
        return True
    # pygame不要求额外的类方法命名豁免。
    return False


# 检查单份源码字节，返回行号、规则编号与说明；永远不执行源码。
def check_source(raw_source: bytes) -> list[tuple[int, str, str]]:
    # 每份文件独立收集问题，便于一次定位多处格式错误。
    violations = []
    # 严格按UTF-8解码，兼容Python允许的UTF-8字节顺序标记。
    try:
        # 解码失败时不能用替换字符继续伪装检查成功。
        source = raw_source.decode("utf-8-sig")
    # 非UTF-8文件需要先统一编码再检查语法。
    except UnicodeDecodeError:
        # 没有可靠文本行号时定位到文件首行。
        return [(1, "PY001", "源码必须使用UTF-8编码。")]
    # 非空源码必须以换行结束，空包入口允许为空文件。
    if source and not source.endswith("\n"):
        # 给出最后一行的位置，便于直接修复。
        violations.append((len(source.splitlines()), "PY002", "文件末尾缺少换行。"))
    # 先解析语法，语法非法时不继续依赖不完整语法树。
    try:
        # 编译但不执行，补充AST解析不会拒绝的顶层return或循环外break等上下文错误。
        compile(source, "<checked-source>", "exec")
        # 解析只生成AST，不导入模块、运行装饰器或求值表达式。
        tree = ast.parse(source)
        # 分词能区分字符串中的井号与实际注释。
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    # 语法与分词失败都应阻止提交，不能静默跳过。
    except (SyntaxError, tokenize.TokenError, IndentationError) as error:
        # 语法错误通常带行号，分词错误则使用其位置元组。
        line_number = getattr(error, "lineno", None) or (error.args[1][0] if isinstance(error, tokenize.TokenError) else 1)
        # 保留Python自身的错误原因，但不展示整份源码。
        violations.append((line_number, "PY004", f"Python语法无法解析：{error.args[0]}"))
        # 无法可靠定位的后续规则不再重复报错。
        return violations
    # 用真实注释token建立索引，不把字符串中的中文井号当作说明。
    comments = {token.start[0]: token for token in tokens if token.type == tokenize.COMMENT}
    # 记录跨行字符串内部行，避免把示例文本中的Tab当作程序缩进。
    string_interior_lines = set()
    # 每个字符串都只影响它实际跨越的物理行。
    for token in tokens:
        # 单行字符串没有内部起始行需要排除。
        if token.type in STRING_CONTENT_TOKEN_TYPES:
            # 字符串首行前缀仍属于真实程序缩进。
            string_interior_lines.update(range(token.start[0] + 1, token.end[0] + 1))
    # 按物理行检查缩进，保留真实行号。
    for line_number, line in enumerate(source.splitlines(), start=1):
        # 只提取代码或注释前面的空白，不检查字符串内容的Tab。
        prefix = line[:len(line) - len(line.lstrip(" \t"))]
        # 多行字符串内部内容不属于Python块缩进。
        if "\t" in prefix and line_number not in string_interior_lines:
            # 混合空格和Tab同样违反约定。
            violations.append((line_number, "PY003", "缩进不能使用Tab，请使用空格。"))
    # 每个真实注释分别检查是否占据独立的一行。
    for line_number, comment in comments.items():
        # 注释前面已有非空白文本时，说明写在了语句尾部。
        if comment.line[:comment.start[1]].strip():
            # 该规则同样适用于多行调用参数后面的注释。
            violations.append((line_number, "PY005", "注释须独立写在对应代码上方，不能写在句尾。"))
    # 直接父节点决定方法例外，防止把类内部嵌套函数当作系统回调。
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    # 真实首句文档字符串用于文档工具，不要求在定义体内再重复其已有说明。
    docstring_owners = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    # 仅豁免Python实际识别的docstring，普通位置的字符串表达式仍需说明。
    docstrings = {owner.body[0] for owner in ast.walk(tree) if isinstance(owner, docstring_owners) and ast.get_docstring(owner, clean=False) is not None}
    # 类计数包含嵌套类，不能通过嵌套绕过单类单文件约定。
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    # 第二个及后续类给出自己的定义行号。
    for node in sorted(classes, key=lambda item: item.lineno)[1:]:
        # 测试类和异常类同样遵循一个文件一个类。
        violations.append((node.lineno, "PY008", "一个Python文件只允许定义一个类，嵌套类也计入。"))
    # 各种逻辑语句都通过AST检查，字符串内容不会被递归当作代码。
    for node in ast.walk(tree):
        # 真实文档字符串和非语句节点不参与逐句说明检查，定义本身仍需上方说明。
        if not isinstance(node, ast.stmt) or node in docstrings:
            # 多行参数和分支标题的说明仍交由人工检查。
            continue
        # 带装饰器的定义将职责说明放在整组装饰器之前。
        decorated = isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.decorator_list
        # 其他语句使用自身开始行。
        start_line = node.decorator_list[0].lineno if decorated else node.lineno
        # 每句有逻辑的代码上方都要有同缩进中文说明。
        if not has_chinese_comment_above(start_line, node.col_offset, comments):
            # 定义与普通逻辑分别给出规则号，便于定位规范章节。
            rule_id = "PY006" if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) else "PY007"
            # 自动检查确认位置与中文存在性，不能保证说明准确。
            violations.append((start_line, rule_id, "定义或逻辑语句上方缺少紧邻、同缩进的中文说明。"))
        # 逐个检查装饰器本身的用途说明。
        if decorated:
            # 后续装饰器不能借用第一个装饰器上方的注释。
            for decorator in node.decorator_list:
                # 装饰器表达式的AST列包含@后的偏移，统一用定义缩进。
                if not has_chinese_comment_above(decorator.lineno, node.col_offset, comments):
                    # 与整体定义缺注释的报告去重。
                    violations.append((decorator.lineno, "PY011", "每个装饰器上方须有同缩进中文用途说明。"))
        # 类名只检查形式，不据此判断职责是否合理。
        if isinstance(node, ast.ClassDef) and not CLASS_NAME_PATTERN.fullmatch(node.name):
            # 大驼峰名称不允许下划线或小写开头。
            violations.append((node.lineno, "PY009", "类名须使用英文大驼峰形式。"))
        # 普通函数与方法遵循小写下划线形式。
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 只有明确的语言或框架协议可以使用其他形式。
            if not FUNCTION_NAME_PATTERN.fullmatch(node.name) and not is_framework_method(node, parents.get(node)):
                # 不把任意库回调或所有驼峰函数整体豁免。
                violations.append((node.lineno, "PY010", "普通函数或方法名须使用英文小写下划线形式。"))
        # 通配导入隐藏依赖，不能因有中文说明而放行。
        if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
            # 原始导入行即可直接定位问题。
            violations.append((node.lineno, "PY012", "禁止使用通配导入。"))
    # 排序并去重，让同一源码的输出稳定。
    return sorted(set(violations))


# 通过参数列表运行只读Git命令，失败时明确中止索引检查。
def run_git(repository: Path, arguments: list[str]) -> bytes:
    # Git缺失和进程启动错误同样不能视为检查成功。
    try:
        # 禁止替代对象影响待检查blob，不使用shell或外部文本拼接命令。
        result = subprocess.run(["git", "--no-replace-objects", "-C", str(repository), *arguments], capture_output=True, check=False)
    # 将系统错误转为检查器统一处理的失败。
    except OSError as error:
        # 保留原因供调用方诊断。
        raise RuntimeError(f"无法启动Git：{error}") from error
    # Git命令失败不是空索引或通过检查。
    if result.returncode != 0:
        # 错误信息按可显示方式解码，不输出源码正文。
        detail = result.stderr.decode("utf-8", errors="backslashreplace").strip()
        # 返回码和错误内容都用于定位索引检查失败。
        raise RuntimeError(f"Git返回{result.returncode}：{detail!r}")
    # blob保留原始字节，编码由源码检查器判断。
    return result.stdout


# 根据仓库相对路径选择主体包、正式回归与构建工具，不读取本机资料。
def is_source_path(path: str) -> bool:
    # Git路径使用正斜线，与support辅助组织目录的层级保持一致。
    parts = path.split("/")
    # 兼容根入口仍属于正式源码。
    if path in ROOT_SOURCE_FILES:
        # 入口不会因辅助目录迁移而漏检。
        return True
    # 正式回归只读取support/tests根目录的独立test_*.py。
    if parts[:2] == ["support", "tests"]:
        # local_video及其他子目录完全排除，不读取其正文。
        return len(parts) == 3 and bool(re.fullmatch(r"test_[a-z0-9_]+\.py", parts[2]))
    # 主体运行源码仍按包递归，工具单独限制为support/tools位置。
    is_code_directory = parts[0] == "hero_game" or (len(parts) == 3 and parts[:2] == ["support", "tools"])
    # 本机素材脚本和非Python文件都不参与正式源码检查。
    return is_code_directory and path.endswith(".py") and path not in EXCLUDED_SOURCE_FILES


# 从Git索引读取实际blob，工作区未暂存内容不会影响此模式的结果。
def staged_sources(repository: Path) -> list[tuple[str, bytes]]:
    # 根目录必须明确位于Git仓库，空仓库有索引也可检查。
    root_output = run_git(repository, ["rev-parse", "--show-toplevel"])
    # 只移除Git追加的换行，不吞掉目录名中的合法空白。
    repository_root = Path(root_output.decode("utf-8", errors="surrogateescape").removesuffix("\n"))
    # NUL分隔可以正确处理空格、Tab和换行文件名。
    entries = run_git(repository_root, ["ls-files", "--stage", "-z"])
    # 先确认全部索引条目合法，再读取blob。
    selected_entries = []
    # 每个索引条目包含模式、对象ID、阶段和路径。
    for entry in entries.split(b"\0"):
        # Git输出的最后一个分隔符后没有实际条目。
        if not entry:
            # 跳过分隔符形成的空项。
            continue
        # 格式错误不能被误认为没有待检查文件。
        try:
            # 只按第一个Tab拆分，文件名中的Tab仍保留。
            metadata, raw_path = entry.split(b"\t", 1)
            # 索引元数据由Git使用ASCII输出。
            mode, object_id, stage = metadata.decode("ascii").split(" ")
            # 路径使用文件系统兼容解码，不按换行拆分。
            path = raw_path.decode("utf-8", errors="surrogateescape")
        # 损坏或不符合预期的Git输出必须中止。
        except (ValueError, UnicodeError) as error:
            # 不泄露异常条目的正文内容。
            raise RuntimeError("GIT001：无法解析Git索引条目。") from error
        # 存在任意未合并路径时不能声称索引规范已经通过。
        if stage != "0":
            # 路径使用repr转义，换行不能伪造另一条输出。
            raise RuntimeError(f"GIT002：索引仍有未合并条目：{path!r}")
        # 非Python及范围外文件由Git内容边界检查器处理。
        if not is_source_path(path):
            # 不读取素材、技术文档或其他类型blob。
            continue
        # 符号链接和子模块不是可直接检查的Python源码文件。
        if mode not in {"100644", "100755"}:
            # 不能把链接目标文本当作Python源码放行。
            raise RuntimeError(f"GIT003：Python索引条目必须为普通文件：{path!r}")
        # 记录索引自己的对象ID，不读取工作区文件。
        selected_entries.append((path, object_id))
    # 每份blob只通过Git对象库读取，删除或修改工作区不影响结果。
    return [(path, run_git(repository_root, ["cat-file", "blob", object_id])) for path, object_id in selected_entries]


# 从工作区读取正式代码范围，默认检查不需要Git或任何第三方依赖。
def working_sources(repository: Path) -> list[tuple[str, bytes]]:
    # 解析macOS系统临时目录链接，项目内部链接仍由后续边界检查拒绝。
    repository = Path(repository).resolve()
    # 不存在的根目录往往是调用错误，不能以零文件通过。
    if not repository.is_dir():
        # 明确提示检查目标错误。
        raise RuntimeError("检查根目录不存在或不是目录。")
    # 先收集后返回，读取失败时不会报告部分检查成功。
    sources = []
    # 兼容入口和包源码使用同一判定，不读取本机视频目录。
    for name in ROOT_SOURCE_FILES:
        # 兼容入口应存在，缺失即为不完整工作区。
        path = repository / name
        # 入口不允许使用符号链接绕过检查边界。
        if path.is_symlink():
            # 拒绝不受控制的链接入口。
            raise RuntimeError(f"IO001：正式入口不能是链接：{name!r}")
        # 读取真实入口字节，不导入或执行入口。
        sources.append((name, path.read_bytes()))
    # 各目录统一筛选；support/tests/local_video仅为本机拍摄扩展，不读取或检查。
    for directory in SOURCE_DIRECTORIES:
        # 项目不必提前建立当前尚无用途的目录。
        # 主体包按职责递归，辅助工具和正式测试只检查各自目录根文件。
        paths = (repository / directory).rglob("*.py") if directory == "hero_game" else (repository / directory).glob("*.py")
        # 工具output和本机拍摄子目录不会被递归遍历。
        for path in sorted(paths):
            # 严格排除本机创作脚本和解释器缓存。
            if not is_source_path(path.relative_to(repository).as_posix()) or "__pycache__" in path.parts:
                # 不把本机创作代码纳入技术规范检查。
                continue
            # 链接不应把只读检查带到项目之外。
            if path.is_symlink() or repository not in path.resolve().parents:
                # 路径转义输出，避免异常文件名影响报告。
                raise RuntimeError(f"IO001：Python源码不能通过链接指向检查范围外：{str(path)!r}")
            # 保存仓库相对路径，输出可直接定位文件。
            sources.append((path.relative_to(repository).as_posix(), path.read_bytes()))
    # 返回原始字节供统一编码与AST检查。
    return sources


# 将只读检查用于命令行、提交钩子或持续集成。
def main(argv: list[str] | None = None) -> int:
    # 明确说明自动检查不覆盖注释准确性和架构语义。
    parser = argparse.ArgumentParser(description="只读检查Python注释位置、基础格式、命名、单类文件与通配导入；语义规则仍需审查。")
    # 默认从本脚本定位当前项目，受控测试可以指定临时根目录。
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2], help="检查根目录，默认使用脚本所在项目")
    # 提交钩子必须选择索引blob，不能只检查未暂存的工作区。
    parser.add_argument("--staged", action="store_true", help="读取Git索引中的Python blob，不读取工作区源码")
    # 未知参数由argparse直接拒绝。
    arguments = parser.parse_args(argv)
    # 路径统一规范化，供范围边界判断。
    repository = arguments.root.resolve()
    # 读取或Git失败时必须返回非零，不把未完成当作通过。
    try:
        # 两种模式共用同一源码规范判定。
        sources = staged_sources(repository) if arguments.staged else working_sources(repository)
        # 为每条问题保留路径、行号和规则编号。
        problems = [(path, line, rule, message) for path, source in sources for line, rule, message in check_source(source)]
    # 文件权限、Git失败和路径编码问题都应阻止放行。
    except (OSError, RuntimeError, UnicodeError) as error:
        # 不在错误报告中展开完整源码。
        print(f"代码规范检查未完成：{error}", file=sys.stderr)
        # 失败状态可被Git钩子和CI识别。
        return 1
    # 完整展示定位信息，便于一次修复同一批问题。
    for path, line, rule, message in problems:
        # 文件名转义后仍可区分带空格或换行的合法路径。
        print(f"{path!r}:{line}: {rule} {message}", file=sys.stderr)
    # 检测到明确违反项时拒绝继续提交。
    if problems:
        # 汇总数量不代替前面的实际问题列表。
        print(f"代码规范检查未通过：{len(problems)}项，检查了{len(sources)}份Python文件。", file=sys.stderr)
        # 任意一项失败都返回非零。
        return 1
    # 结果明确区分索引与工作区，避免把两种状态混为一谈。
    scope = "Git索引" if arguments.staged else "工作区"
    # 自动通过只表示当前可检查项通过。
    print(f"代码规范自动检查通过：{scope}共{len(sources)}份Python文件；注释含义与架构仍需人工审查。")
    # 零状态允许调用方继续自己的流程。
    return 0


# 直接运行时执行检查，导入检查器不会调用Git或读取项目源码。
if __name__ == "__main__":
    # 将明确的成功或失败状态传给终端及钩子。
    sys.exit(main())

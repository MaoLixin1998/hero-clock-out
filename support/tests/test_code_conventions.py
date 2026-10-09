"""验证规范检查器只解析文本，以及索引模式不会误读工作区。"""

# 在临时目录建立受控Git索引，不修改正式仓库。
import tempfile
# 使用标准库测试框架。
import unittest
# 构造受控源码路径。
from pathlib import Path

# 导入纯文本检查和只读索引读取接口。
from support.tools.check_code_conventions import check_source, is_source_path, run_git, staged_sources, working_sources


# 覆盖语法、注释、命名、单类和真实索引读取边界。
class CodeConventionChecks(unittest.TestCase):
    # 合法中文上方注释和标准命名应通过。
    def test_valid_source_is_accepted(self) -> None:
        # 同时覆盖类、方法、返回和调用说明。
        source = "# 保存一个只读状态对象。\nclass SampleState:\n    # 返回当前状态值。\n    def current_value(self):\n        # 返回稳定整数。\n        return 1\n"
        # 纯技术合法源码没有自动规则错误。
        self.assertEqual(check_source(source.encode("utf-8")), [])

    # 检查器不能通过执行被检查源码来判断语法。
    def test_source_is_never_executed(self) -> None:
        # 此语句若执行会抛异常，但语法与注释均合法。
        source = "# 示例只用于语法检查，实际执行会失败。\nraise RuntimeError('do not execute')\n"
        # 检查器只编译与解析，因此不会触发RuntimeError。
        self.assertEqual(check_source(source.encode("utf-8")), [])

    # 单文件多个类必须被拒绝，包括测试类。
    def test_multiple_classes_are_rejected(self) -> None:
        # 两个均有合法说明的类仍违反单类文件约束。
        source = "# 第一个状态。\nclass FirstState:\n    # 空类保留协议。\n    pass\n# 第二个状态。\nclass SecondState:\n    # 空类保留协议。\n    pass\n"
        # 检查明确规则号，不依赖具体中文错误文案。
        self.assertIn("PY008", {rule for _, rule, _ in check_source(source.encode("utf-8"))})

    # 定义说明与每个装饰器用途说明均需要独立存在。
    def test_decorator_requires_its_own_comment(self) -> None:
        # 第二个装饰器没有紧邻说明，不能借用前一条注释。
        source = "# 缓存查询，第一层装饰器保存元信息。\n@first\n@second\ndef read_value():\n    # 返回稳定值。\n    return 1\n"
        # 明确报装饰器用途说明缺失。
        self.assertIn("PY011", {rule for _, rule, _ in check_source(source.encode("utf-8"))})

    # 行尾说明不符合项目约定。
    def test_inline_comment_is_rejected(self) -> None:
        # 前方有合法说明也不能放行行尾注释。
        source = "# 设置计数。\ncount = 1  # 错误位置\n"
        # 分词检查确认真正注释，而非字符串中的井号。
        self.assertIn("PY005", {rule for _, rule, _ in check_source(source.encode("utf-8"))})

    # 格式、编码和上下文语法错误必须独立报告。
    def test_encoding_and_context_syntax_are_rejected(self) -> None:
        # 任意非UTF-8字节不能静默替换。
        self.assertEqual(check_source(b"\xff")[0][1], "PY001")
        # 顶层return可形成AST，但不可编译执行，因此必须报语法失败。
        self.assertIn("PY004", {rule for _, rule, _ in check_source("# 顶层返回非法。\nreturn 1\n".encode("utf-8"))})

    # Python函数不能借用其他项目AppKit命名例外。
    def test_unregistered_framework_name_is_rejected(self) -> None:
        # 普通函数采用驼峰，不属于任何Python协议。
        source = "# 查询状态。\ndef readValue():\n    # 返回稳定值。\n    return 1\n"
        # 项目不继承vibe-pet的Cocoa选择器例外。
        self.assertIn("PY010", {rule for _, rule, _ in check_source(source.encode("utf-8"))})

    # 本机拍摄脚本同时从工作区和索引规范检查排除，正式根测试仍检查。
    def test_local_video_scripts_are_excluded_from_both_modes(self) -> None:
        # 受控根目录没有真实拍摄代码或创作正文。
        with tempfile.TemporaryDirectory() as temporary:
            # 使用独立临时项目验证目录选择。
            root = Path(temporary)
            # 工作区检查要求两个兼容入口存在。
            for name in ("main.py", "dialogue.py"):
                # 空Python文件合法，不引入多余测试行为。
                (root / name).write_bytes(b"")
            # 创建默认unittest不会递归的无包拍摄目录。
            local = root / "support/tests/local_video"
            # 只构造目录结构，不修改正式工作区。
            local.mkdir(parents=True)
            # 故意使用非法编码，证明检查器不会读取此正文。
            (local / "shot.py").write_bytes(b"\xff")
            # 正式根测试使用有效UTF-8。
            (root / "support/tests/test_example.py").write_bytes(b"")
            # 工作区只包含两个入口和正式根测试。
            self.assertEqual({path for path, _ in working_sources(root)}, {"main.py", "dialogue.py", "support/tests/test_example.py"})
            # 初始化临时索引，不需要创建commit。
            run_git(root, ["init", "-q"])
            # 故意登记本机路径验证规范筛选，不代表Git范围允许它。
            run_git(root, ["add", "support/tests"])
            # 索引规范同样只读取正式根测试blob。
            self.assertEqual(staged_sources(root), [("support/tests/test_example.py", b"")])
            # 纯路径判断明确排除拍摄文件。
            self.assertFalse(is_source_path("support/tests/local_video/shot.py"))

    # 索引检查必须读取已暂存blob，不受工作区后来改动影响。
    def test_staged_mode_reads_real_blob(self) -> None:
        # 临时仓库不需要用户身份或创建commit。
        with tempfile.TemporaryDirectory() as temporary:
            # Git只作用于受控目录。
            root = Path(temporary)
            # 初始化空仓库，避免依赖正式项目HEAD。
            run_git(root, ["init", "-q"])
            # 放入合法技术入口并暂存。
            source = root / "main.py"
            # 已暂存版本有完整中文说明。
            indexed = "# 显示固定状态。\nprint('indexed')\n".encode("utf-8")
            # 用真实字节写入工作区。
            source.write_bytes(indexed)
            # 暂存只发生在临时仓库。
            run_git(root, ["add", "main.py"])
            # 后来工作区故意改成非法Python，索引检查不应读它。
            source.write_text("this is invalid python !\n", encoding="utf-8")
            # 索引读取接口按对象ID返回旧合法字节。
            self.assertEqual(staged_sources(root), [("main.py", indexed)])


# 直接执行本文件时启动受控测试。
if __name__ == "__main__":
    # 测试框架负责报告失败和退出状态。
    unittest.main()

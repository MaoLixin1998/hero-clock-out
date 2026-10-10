"""验证正式路径策略、文本校验和链接拒绝，不读取真实私人文档。"""

# 受控目录在测试结束后自动删除。
import tempfile
# 使用标准库断言。
import unittest
# 构造文件、目录和符号链接路径。
from pathlib import Path

# 导入纯路径与文本检查函数。
from support.tools.check_git_scope import entry_problems, is_allowed_path, working_entries


# 核对游戏配置可发布、视频本机覆盖不可发布及文件边界。
class GitScopeChecks(unittest.TestCase):
    # 正式游戏包内配置与纯技术文档均在允许范围。
    def test_formal_game_and_technical_paths_are_allowed(self) -> None:
        # 逐个覆盖根入口、职责模块、正式配置和项目专用补充。
        for path in ("main.py", "README.md", "AGENTS.md", "hero_game/__main__.py", "hero_game/model/game.py", "hero_game/data/dialogue.json", "support/standards/general-coding-standard.md", "support/standards/python-pygame.md", "support/technical/packaging.md", "support/tools/check_project.py"):
            # 正式路径应由同一策略放行。
            self.assertTrue(is_allowed_path(path), path)

    # 视频制作内容不能凭文件类型混入正式包。
    def test_local_video_and_unknown_paths_are_rejected(self) -> None:
        # 样例均为受控字符串，不涉及真实台词或素材。
        for path in ("", "AGENTS.override.md", "support/production/notes/README.md", "support/tests/local_video/shot.py", "config/dialogue.json", "support/production/runtime/dialogue.json", "hero_game/data/dialogue.local.json", "assets/hero.png", "support/tools/build_assets.py", "support/tools/unknown.py", "hero_game/../private.py", "/main.py", "hero_game\\private.py", "docs/script.md", "support/standards/local-collaboration.md"):
            # 默认拒绝范围之外的路径。
            self.assertFalse(is_allowed_path(path), path)

    # JSON损坏与非UTF-8正文必须阻止放行。
    def test_invalid_json_and_encoding_are_rejected(self) -> None:
        # 正式JSON错误仅报告位置和类别，不泄漏正文。
        problems = entry_problems([("hero_game/data/game.json", b"{\n", "100644"), ("main.py", b"\xff", "100644")])
        # 两个独立错误都必须被看到。
        self.assertEqual(len(problems), 2)

    # 工作区选出的正式入口不能指向任意外部文件。
    def test_working_entry_symlink_is_rejected(self) -> None:
        # 链接和目标都只在测试临时目录。
        with tempfile.TemporaryDirectory() as temporary:
            # 受控项目根目录。
            root = Path(temporary)
            # 模拟本机私有文件但不使用真实资料。
            target = root / "private.txt"
            # 私有标记不被检查器读取。
            target.write_text("private\n", encoding="utf-8")
            # 允许名字main.py实际是链接，必须拒绝。
            (root / "main.py").symlink_to(target)
            # 不把链接目标正文作为正式源码。
            with self.assertRaises(RuntimeError):
                # 工作区枚举在读取链接内容前失败。
                working_entries(root)


# 直接执行时才运行测试。
if __name__ == "__main__":
    # 返回标准测试状态。
    unittest.main()

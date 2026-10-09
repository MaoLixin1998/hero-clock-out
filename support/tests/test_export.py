"""验证正式发行清单隔离本机制作内容并保护已有产物。"""

# 临时项目隔离发行测试，不改动用户的真实素材与压缩包。
import tempfile
# 标准框架记录路径筛选和失败行为。
import unittest
# 路径对象统一项目内相对位置。
from pathlib import Path
# ZIP解码确认导出容器实际包含的文件。
from zipfile import ZipFile

# 正式导出只从允许范围选择文件，发布不会遍历私有目录。
from support.tools.export_game import export_game, public_files


# 检查真实打包入口，不用Git忽略规则代替包内容边界验证。
class ExportChecks(unittest.TestCase):
    # 技术模块和正式游戏数据可入包，私有素材与未知脚本均排除。
    def test_unknown_and_private_files_are_excluded(self) -> None:
        # 构造受控项目，避免从本机正式素材中读取任何内容。
        with tempfile.TemporaryDirectory() as temporary:
            # 相对路径都属于这一份临时根目录。
            root = Path(temporary)
            # 这些文件属于已登记技术入口或正式数据位置。
            allowed_paths = (
                # 轻量启动入口属于正式程序。
                "main.py",
                # 纯技术协作入口可随源码分发。
                "AGENTS.md",
                # 包模块按纯技术职责组织。
                "hero_game/model/game.py",
                # 三份默认数据均随正式游戏分发。
                "hero_game/data/game.json",
                # 共用对白以正式游戏数据为主。
                "hero_game/data/dialogue.json",
                # 界面文字独立于运行算法。
                "hero_game/data/presentation.json",
                # 已审阅的构建工具可以随源码包交付。
                "support/tools/export_game.py",
                # 项目专用补充可以分发，但不是通用规范正文副本。
                "support/standards/python-pygame.md",
            )
            # 每个路径使用普通文本，不读取外部真实文件。
            for relative in allowed_paths:
                # 为包内嵌套目录建立必要父层。
                target = root / relative
                # 临时目录结构按真实发行结构组织。
                target.parent.mkdir(parents=True, exist_ok=True)
                # 所有JSON使用合法空对象；源码只用无副作用注释。
                target.write_text("{}\n" if target.suffix == ".json" else "# 受控技术样例。\n", encoding="utf-8")
            # 私有路径包括旧配置、视频资料、素材和未登记脚本。
            excluded_paths = (
                # 个人资源关联入口不属于技术代码。
                "LIFE_PLAN_LINK.md",
                # 原README混合创作内容，不能默认打包。
                "README.md",
                # 根配置不能成为另一套默认规则来源。
                "config/game.json",
                # 本机视频台词保持隔离。
                "config/dialogue.json",
                # 任意视频覆盖均不可进入正式游戏数据。
                "hero_game/data/presentation.local.json",
                # 旧文稿目录只保留本机。
                "docs/private.md",
                # 视频扩展可整体移除。
                "support/production/runtime/video_scene.py",
                # 本机美术不因文件后缀而获准分发。
                "assets/background.png",
                # 配乐和音效也不能随代码目录递归带出。
                "assets/slime_land.wav",
                # 个人素材构建工具仍不属于已审阅清单。
                "support/tools/build_assets.py",
                # 陌生工具要先审阅，不能只凭.py放行。
                "support/tools/unknown.py",
                # 本机通用开发规范不因Markdown后缀或技术目录而获准分发。
                "support/standards/general-coding-standard.md",
            )
            # 写入明确私有标记，检查器只需筛路径而不解释正文。
            for relative in excluded_paths:
                # 私有样例也仅存在于当前临时目录。
                target = root / relative
                # 建立私有目录，不影响正式清单。
                target.parent.mkdir(parents=True, exist_ok=True)
                # 即使后缀是假媒体，边界也应按路径拒绝。
                target.write_bytes(b"private")
            # 实际筛选器返回项目相对文件路径。
            selected = {path.as_posix() for path in public_files(root)}
            # 确认完整保留正式技术和游戏数据。
            self.assertEqual(selected, set(allowed_paths))
            # 排除发行不会删除本机规范文件或改写其正文。
            self.assertEqual((root / "support/standards/general-coding-standard.md").read_bytes(), b"private")

    # 构建失败不能覆盖已经存在的可用压缩包。
    def test_missing_required_files_preserve_existing_artifact(self) -> None:
        # 临时项目故意不提供完整正式源码。
        with tempfile.TemporaryDirectory() as temporary:
            # 根目录和已有产物共处临时区，便于检查实际字节。
            root = Path(temporary)
            # 已有产物使用可识别的固定字节。
            output_path = root / "game-source.zip"
            # 模拟先前已经交付的文件。
            output_path.write_bytes(b"previous-valid-artifact")
            # 缺少构建必需入口时应明确失败。
            with self.assertRaises(ValueError):
                # 显式传入目标，不让工具使用真实dist目录。
                export_game(destination=output_path, root=root)
            # 旧产物必须完整保留，不能被失败构建清空。
            self.assertEqual(output_path.read_bytes(), b"previous-valid-artifact")

    # 合法技术路径上的符号链接不能绕过边界读取外部文件。
    def test_allowed_symlink_is_rejected_without_following(self) -> None:
        # 将外部文件和项目根分开，模拟链接越出允许根目录。
        with tempfile.TemporaryDirectory() as temporary:
            # 临时区同时保存项目和外部标记。
            temporary_root = Path(temporary)
            # 建立不包含链接目标的独立项目根。
            root = temporary_root / "project"
            # 正式筛选入口只允许读这个目录。
            root.mkdir()
            # 外部标记不属于项目。
            external_path = temporary_root / "external.txt"
            # 内容不应通过main.py链接进入发行包。
            external_path.write_text("private\n", encoding="utf-8")
            # 使用技术入口名创建越界链接。
            (root / "main.py").symlink_to(external_path)
            # 筛选必须在读取链接正文前阻止本次导出。
            with self.assertRaises(RuntimeError):
                # 调用实际发行路径筛选函数。
                public_files(root)

    # 导出容器本身也必须只含正式文件，不能只验证筛选函数返回值。
    def test_source_archive_contains_only_the_controlled_formal_snapshot(self) -> None:
        # 本例只验证打包字节，不宣称这些无执行代码的样例可以运行。
        with tempfile.TemporaryDirectory() as temporary:
            # 临时项目完全不挂载本机游戏素材或制作资料。
            root = Path(temporary) / "project"
            # 明确给出独立的最小正式结构，构建工具另行检查必需项。
            expected_paths = {
                # 启动脚本与历史导入兼容层属于技术入口。
                "main.py", "dialogue.py",
                # 依赖声明和纯技术文档属于源码交付说明。
                "pyproject.toml", "requirements.txt", "TECHNICAL.md", "AGENTS.md",
                # 包入口与命令组装入口必须完整。
                "hero_game/__init__.py", "hero_game/app/cli.py",
                # 正式运行数据只有这三份默认文件。
                "hero_game/data/game.json", "hero_game/data/dialogue.json",
                # 界面文字不从本机覆盖文件补齐。
                "hero_game/data/presentation.json",
                # 只有项目专用补充进入正式技术交付。
                "support/standards/python-pygame.md",
            }
            # 为每份文件写入可校验且无副作用的技术样例。
            for relative in expected_paths:
                # 文件相对位置保持真实正式包结构。
                target = root / relative
                # 必要的包层级由当前临时项目持有。
                target.parent.mkdir(parents=True, exist_ok=True)
                # JSON使用合法对象，其他文本保持UTF-8末尾换行。
                target.write_text("{}\n" if target.suffix == ".json" else "# 受控技术样例。\n", encoding="utf-8")
            # 添加明确不应打包的本机目录。
            private_path = root / "support/production/private.txt"
            # 私有目录与正式源码可以在同一工作区共存。
            private_path.parent.mkdir()
            # 隔离测试标记不包含真实个人资料。
            private_path.write_text("private\n", encoding="utf-8")
            # 在同一技术目录放本机规范，实测ZIP不收集它。
            local_standard = root / "support/standards/general-coding-standard.md"
            # 只使用受控标记，不复制真实通用规则正文。
            local_standard.write_bytes(b"local-only general rules\n")
            # 目标放在项目外，避免本次产物参与自己的清单筛选。
            output_path = root.parent / "game-source.zip"
            # 通过真实构建入口写出临时ZIP。
            archive_path, entry_count = export_game(destination=output_path, root=root)
            # 返回的位置必须是实际请求的文件。
            self.assertEqual(archive_path, output_path.resolve())
            # 文件数量须对应正式快照全部成员。
            self.assertEqual(entry_count, len(expected_paths))
            # 解码真实容器，不能仅凭ZIP文件存在就算通过。
            with ZipFile(archive_path) as archive:
                # 容器成员应精确等于正式源码快照。
                self.assertEqual(set(archive.namelist()), expected_paths)
                # 本机通用规范必须从实际容器成员中排除。
                self.assertNotIn("support/standards/general-coding-standard.md", archive.namelist())
                # CRC必须完整，压缩过程没有损坏任何文件。
                self.assertIsNone(archive.testzip())
                # 正式数据实际保存了源字节，不只是一个占位成员名。
                self.assertEqual(archive.read("hero_game/data/game.json"), b"{}\n")
            # 构建后本机规范仍保留原字节，不借排除规则删除原稿。
            self.assertEqual(local_standard.read_bytes(), b"local-only general rules\n")

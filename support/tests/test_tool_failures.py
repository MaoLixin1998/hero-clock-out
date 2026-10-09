"""验证素材工具的失败路径保留旧输出，测试数据全部临时生成。"""

# 每项测试均使用自动清理的独立目录。
import tempfile
# 使用标准库测试框架。
import unittest
# 模拟真实文件编码失败，不依赖磁盘权限或真实素材。
from unittest.mock import patch
# 构造受控输入和输出路径。
from pathlib import Path

# Pillow只生成测试用几何图片。
from PIL import Image

# 声音合成工具采用同盘临时输出。
from support.tools.build_audio import build_landing_sound
# PNG保存接口单独负责失败保护。
from support.tools.build_dialogue_ui import save_png
# GIF整体解码后才替换旧目录。
from support.tools.split_gif import split_gif


# 覆盖GIF参数与解码失败，以及WAV/PNG编码中断保护。
class ToolFailureChecks(unittest.TestCase):
    # 损坏GIF不能删除旧帧目录或旧清单。
    def test_invalid_gif_keeps_existing_output(self) -> None:
        # 输入和旧输出均为受控样例。
        with tempfile.TemporaryDirectory() as temporary:
            # 临时项目根目录。
            root = Path(temporary)
            # 设置旧帧目录。
            output = root / "frames"
            # 建立旧目录。
            output.mkdir()
            # 旧标记用字节比较，证明不是重新生成的同名文件。
            marker = output / "old.txt"
            # 写入旧内容。
            marker.write_bytes(b"old frame data")
            # 输入后缀虽为GIF，内容实际损坏。
            source = root / "broken.gif"
            # 不使用任何真实用户图片。
            source.write_bytes(b"not a gif")
            # 解码失败必须抛错误。
            with self.assertRaises(OSError):
                # 正式旧目录在解码前不被移动。
                split_gif(source, output)
            # 旧字节保留完整。
            self.assertEqual(marker.read_bytes(), b"old frame data")
            # 未完成的临时目录会自动清理。
            self.assertEqual({path.name for path in root.iterdir()}, {"frames", "broken.gif"})

    # 布尔值不能作为毫秒整数配置被接受。
    def test_boolean_fallback_is_rejected(self) -> None:
        # 参数校验发生在打开输入和创建目录之前。
        with self.assertRaises(ValueError):
            # 无需构造真实GIF即可验证类型边界。
            split_gif(Path("unused.gif"), Path("unused-output"), True)

    # WAV写入错误不能覆盖旧音效。
    def test_audio_write_failure_keeps_old_file(self) -> None:
        # 只在临时目录内生成样例输出。
        with tempfile.TemporaryDirectory() as temporary:
            # 现有音效使用固定字节标记。
            output = Path(temporary) / "sound.wav"
            # 写入旧字节。
            output.write_bytes(b"old audio")
            # 模拟编码阶段文件系统失败。
            with patch("support.tools.build_audio.wave.open", side_effect=OSError("controlled failure")):
                # 错误必须保留给调用方。
                with self.assertRaises(OSError):
                    # 合成样本后，输出仍只写入临时路径。
                    build_landing_sound(output)
            # 正式旧文件不被打开或清空。
            self.assertEqual(output.read_bytes(), b"old audio")

    # PNG编码异常不能把旧图片截断成零字节。
    def test_png_write_failure_keeps_old_file(self) -> None:
        # 目录和图片对象均自动清理。
        with tempfile.TemporaryDirectory() as temporary, Image.new("RGBA", (2, 2)) as image:
            # 正式输出路径。
            output = Path(temporary) / "panel.png"
            # 写入旧图片标记。
            output.write_bytes(b"old image")
            # Pillow编码调用失败在replace之前。
            with patch.object(Image.Image, "save", side_effect=OSError("controlled failure")):
                # 错误应传给调用者，而非打印成功。
                with self.assertRaises(OSError):
                    # 原子保存接口保护旧正式文件。
                    save_png(image, output)
            # 旧文件字节不变。
            self.assertEqual(output.read_bytes(), b"old image")


# 直接执行时启动受控失败路径测试。
if __name__ == "__main__":
    # 返回标准unittest结果。
    unittest.main()

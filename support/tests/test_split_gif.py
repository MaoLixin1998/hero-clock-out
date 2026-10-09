"""验证受控GIF的透明帧处置和不同帧时长。"""

# 临时目录隔离自造GIF，不改动任何个人素材。
import tempfile
# 标准测试框架报告帧处置与时长是否保留。
import unittest
# 路径对象组织临时源文件与拆帧目录。
from pathlib import Path

# Pillow生成受控透明调色板GIF并读取工具产物。
from PIL import Image

# 调用实际技术拆帧工具，验证编码后的真实像素。
from support.tools.split_gif import split_gif


# GIF回归只使用临时自造图像，不需要本机动画素材。
class GifSplitChecks(unittest.TestCase):
    # 制造透明双帧 GIF，确认拆帧无拖影且保留不同播放时长。
    def test_gif_disposal_and_durations_survive_decode(self) -> None:
        # 在自动清理的临时目录中制造样例 GIF，不改动正式角色动画。
        with tempfile.TemporaryDirectory() as temp:
            # 把临时目录字符串转成 Path，后面可以直接拼接测试文件路径。
            folder = Path(temp)
            # 设置透明、红、绿三个调色槽，其余补零至 256 色格式。
            palette = [0, 0, 0, 255, 0, 0, 0, 255, 0] + [0] * 759
            # 创建两张索引色帧，初始全部使用透明编号 0。
            first_frame, second_frame = Image.new("P", (10, 10), 0), Image.new("P", (10, 10), 0)
            # 为两张帧分别设置相同调色板，颜色编号才能保持同一含义。
            for image in (first_frame, second_frame):
                # 安装调色板，后面的编号 1 和 2 分别代表红色与绿色。
                image.putpalette(palette)
            # 只在第一帧的 (2,2) 点画红色，作为应在下一帧消失的旧内容。
            first_frame.putpixel((2, 2), 1)
            # 只在第二帧的 (7,7) 点画绿色，作为下一帧的新内容。
            second_frame.putpixel((7, 7), 2)
            # 保存双帧 GIF，使用透明背景与 disposal=2，并赋予不同帧时长。
            first_frame.save(folder / "sample.gif", save_all=True, append_images=[second_frame],
                   # 第 0 色透明，每帧清除旧图，设置 70/130 毫秒节拍，并关闭自动调色板优化。
                   transparency=0, disposal=2, duration=[70, 130], loop=0, optimize=False)
            # 调用真实拆帧工具，将刚刚制造的 GIF 还原成完整 PNG。
            result = split_gif(folder / "sample.gif", folder / "frames")
            # 确认两帧时长仍是 70 和 130 毫秒，没有被统一节拍覆盖。
            self.assertEqual([frame["duration_ms"] for frame in result["frames"]], [70, 130])
            # 打开第二张解码帧，检查上一帧透明处置有没有正确执行。
            with Image.open(folder / "frames/frame_001.png") as image:
                # 确认旧红点位置已经透明，没有把上一帧错误叠加留下拖影。
                self.assertEqual(image.getpixel((2, 2))[3], 0)
                # 确认新的绿点保留完整颜色与不透明度，证明没有漏掉当前帧。
                self.assertEqual(image.getpixel((7, 7)), (0, 255, 0, 255))

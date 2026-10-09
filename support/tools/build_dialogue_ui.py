"""将规则几何对话组件输出为本地PNG，运行版也可直接使用程序绘制。"""

# 在异常路径也关闭所有临时图像资源。
from contextlib import ExitStack
# 用临时输出保证单张PNG写入失败时不破坏旧文件。
import tempfile
# 导入路径对象，按本脚本位置寻找项目与素材输出目录。
from pathlib import Path

# 导入 Pillow 的图像和绘图对象，用规则几何形状生成可复用框素材。
from PIL import Image, ImageDraw

# 从脚本所在support/tools向上定位项目根，避免依赖终端当前目录。
ROOT = Path(__file__).resolve().parents[2]


# 将PNG写入同盘临时目录；失败时保留此前输出，成功后替换单个文件。
def save_png(image: Image.Image, destination: Path) -> None:
    # 临时目录离开上下文后自动清理，不遗留未完成PNG。
    with tempfile.TemporaryDirectory(prefix=".ui-build-", dir=destination.parent) as temporary:
        # 格式由后缀确定，路径不来自外部代码表达式。
        pending = Path(temporary) / "image.png"
        # Pillow完成编码前不会打开旧正式文件。
        image.save(pending)
        # 编码成功才替换正式图片。
        pending.replace(destination)


# 生成三张可复用透明 PNG：主纸框、姓名牌和下一句箭头。
def build_dialogue_ui(destination: Path | None = None) -> tuple[Path, Path, Path]:
    # 组件默认保存到本机工具产物目录，不成为正式运行的隐藏依赖。
    folder = Path(destination) if destination is not None else ROOT / "support/tools/output/dialogue_ui"
    # 创建组件目录及上层目录，已经存在时允许重复生成。
    folder.mkdir(parents=True, exist_ok=True)
    # 统一持有三张图片，任何保存失败也按逆序关闭。
    with ExitStack() as resources:
        # 透明底能让四个切角露出场景。浅色底配深色边框提高文字对比。
        panel = resources.enter_context(Image.new("RGBA", (476, 108)))
        # 创建台词框画布的绘图对象，后面绘制都会作用在这张图上。
        draw = ImageDraw.Draw(panel)
        # 按顺时针列出台词框的八个角点，四角各切去小块形成像素纸框。
        shape = [(6, 0), (470, 0), (476, 6), (476, 102),
                 # 继续列出纸框底边与左边的角点，回到左上切角形成封闭轮廓。
                 (470, 108), (6, 108), (0, 102), (0, 6)]
        # 填充羊皮纸色、画 3 像素深色边框，切角之外保留透明背景。
        draw.polygon(shape, fill="#E9DDBD", outline="#66563F", width=3)
        # 在外框内再画 1 像素细线，让边缘有纸质面板的层次。
        draw.rectangle((8, 8, 467, 99), outline="#B5A17B", width=1)
        # 四角装饰以整数像素绘制，不做模糊，放大后仍有清晰的像素边。
        for x, y in ((14, 14), (455, 14), (14, 87), (455, 87)):
            # 在当前角点附近画 6 像素方形装饰，四个角使用相同造型。
            draw.rectangle((x, y, x + 6, y + 6), outline="#C4B18B")
        # 保存不带任何文字的主台词框，运行时可以叠不同角色台词。
        save_png(panel, folder / "panel.png")

        # 创建 244×25 透明姓名牌画布，左右尖角之外保持透明。
        nameplate = resources.enter_context(Image.new("RGBA", (244, 25)))
        # 把绘图对象切换到姓名牌，避免继续画到刚才的主框上。
        draw = ImageDraw.Draw(nameplate)
        # 画带左右尖角的六边形牌子，用深底浅边保证浅色姓名可读。
        draw.polygon([(10, 0), (234, 0), (244, 12), (234, 24), (10, 24), (0, 12)],
                     # 姓名牌使用深棕底和 2 像素浅边，运行时浅色文字能清晰显示在上面。
                     fill="#655B4C", outline="#C2AE88", width=2)
        # 保存空姓名牌，角色名由游戏按当前说话者动态绘制。
        save_png(nameplate, folder / "nameplate.png")

        # 创建 12×8 透明小图，作为下一句的向下指示箭头。
        advance = resources.enter_context(Image.new("RGBA", (12, 8)))
        # 用三个顶点画深棕色向下三角形，不依赖任何字体图标。
        ImageDraw.Draw(advance).polygon([(0, 0), (11, 0), (6, 7)], fill="#75633F")
        # 保存独立箭头，游戏可以按需放在台词框右下角。
        save_png(advance, folder / "advance.png")
        # 返回实际输出路径，便于调用方验证和定位。
        return folder / "panel.png", folder / "nameplate.png", folder / "advance.png"


# 只有直接执行脚本时生成图片，导入函数不会自动写素材文件。
if __name__ == "__main__":
    # 调用生成函数，按顺序保存主框、姓名牌和箭头。
    build_dialogue_ui()
    # 输出完成消息，方便命令行确认组件已生成。
    print("Built panel, nameplate and advance indicator.")

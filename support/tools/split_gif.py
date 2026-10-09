"""将GIF解码为完整透明PNG和毫秒帧清单，失败时保留旧输出目录。"""

# 解析输入GIF、输出目录与无效时长的回退值。
import argparse
# 写入只含结构数据的帧清单。
import json
# 检查浮点时长的有限性。
import math
# 成功替换后清理旧帧目录。
import shutil
# 应用边界返回明确失败状态。
import sys
# 自动清理未发布的解码文件。
import tempfile
# 给旧目录创建不冲突的安全备份名。
import uuid
# 统一文件和目录路径。
from pathlib import Path

# Pillow按GIF透明处置规则解码完整帧。
from PIL import Image


# 在空目录解码GIF，返回可JSON序列化的完整帧清单。
def decode_frames(source: Path, destination: Path, fallback_ms: int) -> dict[str, object]:
    # 单个GIF的帧记录由此函数独立持有。
    frames = []
    # 输入文件在完成或失败后都会关闭。
    with Image.open(source) as gif:
        # 真正的解码格式必须是GIF，不只相信后缀。
        if gif.format != "GIF":
            # 报告输入格式错误，不修改正式输出。
            raise ValueError(f"Expected a GIF, got {gif.format}")
        # GIF画布尺寸由首帧确定，局部更新不改变整体画布。
        size = list(gif.size)
        # 缺失循环信息保留为None，不冒充原文件声明了循环。
        loop = gif.info.get("loop")
        # 按原始顺序解码，Pillow负责合成与disposal处理。
        for index in range(gif.n_frames):
            # seek使当前帧呈现为完整画布。
            gif.seek(index)
            # 无时长字段单独标记为回退，不混淆合法0与正常播放值。
            raw_duration = gif.info.get("duration")
            # 拒绝布尔值、非数、无穷和小于1毫秒的时长。
            duration_valid = type(raw_duration) in {int, float} and math.isfinite(raw_duration) and raw_duration >= 1
            # 毫秒清单按整数保存；合法数值向最近毫秒取整。
            duration_ms = round(raw_duration) if duration_valid else fallback_ms
            # 固定宽度编号保证文件名排序与播放顺序一致。
            name = f"frame_{index:03}.png"
            # 转换图像也有独立生命周期，写入后释放像素资源。
            with gif.convert("RGBA") as frame:
                # 只写入受控临时目录，失败不影响旧帧。
                frame.save(destination / name)
            # 回退状态和最终毫秒值分别记录。
            frames.append({"file": name, "duration_ms": duration_ms, "duration_fallback": not duration_valid})
    # 来源只记录输入文件名，不泄漏绝对用户路径。
    data = {"source": source.name, "size": size, "gif_loop": loop, "runtime_loop": True, "frames": frames}
    # 明确UTF-8和末尾换行，便于跨系统读取。
    (destination / "animation.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 返回与落盘JSON相同的数据。
    return data


# 完整解码后替换目录；输入或写入失败保留已有帧，返回新清单。
def split_gif(source: Path, destination: Path, fallback_ms: int = 100) -> dict[str, object]:
    # 回退值必须是正整数毫秒，不能接受True作为1毫秒。
    if type(fallback_ms) is not int or fallback_ms <= 0:
        # 在创建输出目录前拒绝无效参数。
        raise ValueError("fallback_ms must be a positive integer")
    # 统一调用方传入的路径对象。
    source = Path(source)
    # 不解析目标末层链接，先明确拒绝再确定路径。
    destination = Path(destination)
    # 正式目标不能是链接或普通文件，避免覆盖意外对象。
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        # 保持原文件和链接完全不动。
        raise ValueError("destination must be a real directory path")
    # 上层目录允许按用户指定路径创建。
    destination.parent.mkdir(parents=True, exist_ok=True)
    # 备份放在临时目录之外，恢复失败时仍保留原始文件。
    backup = destination.with_name(f".{destination.name}.previous-{uuid.uuid4().hex}")
    # 解码文件与目标保持同盘，目录重命名无需逐文件复制。
    with tempfile.TemporaryDirectory(prefix=".gif-build-", dir=destination.parent) as temporary:
        # 临时目录自身就是待替换的完整帧目录。
        pending = Path(temporary) / "frames"
        # 明确建立空目录，旧帧不会混入新清单。
        pending.mkdir()
        # 所有输入格式和图像错误都在替换前发生。
        data = decode_frames(source, pending, fallback_ms)
        # 只有存在旧目录才创建临时备份。
        if destination.exists():
            # 重命名旧目录保留其全部字节，尚未删除。
            destination.rename(backup)
        # 替换失败时应恢复旧输出。
        try:
            # 新目录完整写入后一次性替换正式路径。
            pending.rename(destination)
        # 只处理文件系统错误，不吞掉程序错误。
        except OSError:
            # 旧目录存在时尽力恢复，恢复失败备份仍留在项目旁。
            if backup.exists():
                # 这一调用若失败会保留backup并向调用方报告真实异常。
                backup.rename(destination)
            # 继续抛出最初替换错误，不能冒充成功。
            raise
    # 正式新目录已发布，旧备份可以安全清理。
    if backup.exists():
        # 删除的仅是本次工具自己创建的旧输出备份。
        shutil.rmtree(backup)
    # 返回正式新目录对应清单。
    return data


# 解析命令并在边界报告错误，导入时不处理任何图片。
def main(argv: list[str] | None = None) -> int:
    # 参数帮助来自模块技术说明。
    parser = argparse.ArgumentParser(description=__doc__)
    # 第一个位置参数为GIF源文件。
    parser.add_argument("source", type=Path)
    # 第二个位置参数为完整帧输出目录。
    parser.add_argument("destination", type=Path)
    # 明确单位为毫秒，默认每帧100毫秒。
    parser.add_argument("--fallback-ms", type=int, default=100)
    # 参数错误由标准库给出非零结果。
    arguments = parser.parse_args(argv)
    # 输入损坏或写入失败在工具边界展示。
    try:
        # 主函数只负责组装，图像处理由独立函数完成。
        result = split_gif(arguments.source, arguments.destination, arguments.fallback_ms)
    # Pillow图像格式错误属于OSError或ValueError，均不伪装成功。
    except (OSError, ValueError) as error:
        # 失败时保留旧输出并显示原因。
        print(f"GIF拆帧失败：{error}", file=sys.stderr)
        # 返回可用于批处理的失败状态。
        return 1
    # 只报告实际成功的数量和目标。
    print(f"Exported {len(result['frames'])} complete frames to {arguments.destination}")
    # 正常完成返回零。
    return 0


# 仅直接运行时执行拆帧。
if __name__ == "__main__":
    # 把工具返回码传给终端。
    sys.exit(main())

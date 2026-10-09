"""合成单声道短冲击音效；输出仅保留本机，不属于发布必需资源。"""

# 数学函数用来合成逐渐降低的音高和衰减的弹簧振动。
import math
# 固定种子的随机噪声形成落地瞬间的短促冲击，每次构建结果相同。
import random
# struct 把小数声音转换为 WAV 所需的 16 位整数样本。
import struct
# 临时输出避免写入中断时破坏旧声音文件。
import tempfile
# wave 是 Python 自带的 WAV 写入工具，不增加运行依赖。
import wave
# Path 根据脚本位置确定输出路径，不依赖当前工作目录。
from pathlib import Path

# 按脚本位置定位项目根，生成产物集中在工具output目录。
ROOT = Path(__file__).resolve().parents[2]


# 合成0.48秒、48kHz单声道16位PCM；写入失败保留旧文件，返回最终路径。
def build_landing_sound(destination: Path | None = None) -> Path:
    # 默认写入本机工具产物目录；调用方可显式指定其他输出位置。
    destination = Path(destination) if destination is not None else ROOT / "support/tools/output/audio/slime_land.wav"
    # 首次运行时创建音效目录，已经存在则不重复创建。
    destination.parent.mkdir(parents=True, exist_ok=True)
    # 每秒 48000 个声音采样点，符合常见录屏音频规格。
    rate = 48000
    # 单个冲击音只持续0.48秒，便于按动作触发。
    duration = 0.48
    # 本地随机数发生器保证可重建，同时不影响其他代码的随机数。
    noise = random.Random(1729)
    # bytearray 按顺序收集全部 16 位采样字节。
    samples = bytearray()
    # phase 保存振动走过的角度，连续累加避免音高变化时出现断点。
    phase = 0.0
    # 按时间顺序计算每个采样点的振幅。
    for index in range(round(rate * duration)):
        # 将采样编号换成秒数，公式中的衰减都以秒为单位。
        time_seconds = index / rate
        # 音高从约 230Hz 下滑到低音，并带小幅弹簧式摆动。
        frequency = 62 + 168 * math.exp(-15 * time_seconds) + 18 * math.sin(52 * time_seconds) * math.exp(-8 * time_seconds)
        # 每个采样前进“频率 × 一圈角度 / 每秒采样数”，保持波形连续。
        phase += math.tau * frequency / rate
        # 低音主体随时间衰减，形成 duang 的弹性尾音。
        spring = math.sin(phase) * math.exp(-9 * time_seconds)
        # 最初的低频重击快速衰减，让落地点听起来有重量。
        thump = math.sin(math.tau * 72 * time_seconds) * math.exp(-35 * time_seconds)
        # 很短的噪声只存在于起音，模拟软团落地的撞击。
        impact = noise.uniform(-1, 1) * math.exp(-100 * time_seconds)
        # 2 毫秒渐入、40 毫秒渐出，减少波形突然截断产生的点击声。
        fade = min(1.0, time_seconds / 0.002, (duration - time_seconds) / 0.04)
        # 混合三种成分并保留音量余量，最大振幅不会超过整数范围。
        value = (0.48 * spring + 0.22 * thump + 0.1 * impact) * fade
        # 把 -1 到 1 的小数转换为有符号整数，并按 WAV 的小端顺序写入。
        samples.extend(struct.pack("<h", round(value * 32767)))
    # 在目标文件旁创建临时文件，同盘替换不会破坏旧音效。
    with tempfile.TemporaryDirectory(prefix=".audio-build-", dir=destination.parent) as temporary:
        # 临时文件名只在受控目录内使用。
        pending = Path(temporary) / "sound.wav"
        # 写入标准PCM格式，with保证正常或异常时关闭文件头。
        with wave.open(str(pending), "wb") as output:
            # 声音使用单声道，录屏软件可混入立体声轨道。
            output.setnchannels(1)
            # 每个采样占 2 字节，也就是 16 位整数音频。
            output.setsampwidth(2)
            # 写入每秒采样数，播放器据此恢复正确音高与长度。
            output.setframerate(rate)
            # 保存已经合成的全部样本，关闭文件时自动完成 WAV 文件头。
            output.writeframes(samples)
        # 文件关闭完成后原子替换旧输出。
        pending.replace(destination)
    # 返回真实输出位置，方便检查和其他素材工具引用。
    return destination


# 直接运行工具才生成音效；自动检查导入它时不改游戏素材。
if __name__ == "__main__":
    # 显示生成文件的位置，便于在游戏或剪辑软件中找到它。
    print(build_landing_sound())

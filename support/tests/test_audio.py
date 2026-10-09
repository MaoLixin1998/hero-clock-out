"""检查可重建音效的PCM格式、时长和削波余量。"""

# array 将16位PCM字节解码为真实音频振幅。
from array import array
# 临时目录让音效检查不覆盖游戏正在使用的文件。
import tempfile
# 标准测试框架提供明确的检查结果。
import unittest
# wave 读取真实WAV文件头和PCM内容。
import wave
# Path 组织临时音频路径。
from pathlib import Path

# 直接调用实际合成工具，而非检查另外一份声音公式。
from support.tools.build_audio import build_landing_sound


# 声音工具回归生成临时文件，不读取或播放个人录音。
class AudioChecks(unittest.TestCase):
    # 合成相同声音两次，核对文件格式、非零音量和峰值余量。
    def test_landing_sound_is_reproducible_pcm_without_clipping(self) -> None:
        # 在自动删除的临时目录生成检查用声音。
        with tempfile.TemporaryDirectory() as temp:
            # 两个路径独立，第二次构建不能直接复用第一份文件。
            first_path, second_path = Path(temp) / "first.wav", Path(temp) / "second.wav"
            # 生成第一份实际声音。
            build_landing_sound(first_path)
            # 用相同工具再次生成声音，验证固定种子和公式可重建。
            build_landing_sound(second_path)
            # 文件内容应完全一致，不只是两份时长相同。
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            # 解码真实WAV头和样本，不能仅凭文件后缀判断可用。
            with wave.open(str(first_path), "rb") as source:
                # 采样率、单声道、16位是交付素材的实际规格。
                self.assertEqual((source.getframerate(), source.getnchannels(), source.getsampwidth()), (48000, 1, 2))
                # 0.48秒应该包含23040个采样点。
                self.assertEqual(source.getnframes(), 23040)
                # 读取全部采样并转换为有符号16位整数。
                samples = array("h", source.readframes(source.getnframes()))
            # 实际峰值证明声音并非空文件或静音。
            peak = max(abs(value) for value in samples)
            # 音量需要可听且保留削波余量。
            self.assertTrue(1000 < peak < 32767)

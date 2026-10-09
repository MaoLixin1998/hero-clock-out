"""缓存落地声音，按事件编号去重；不参与模拟规则。"""

# 生成基础提示音的周期波形。
import math
# 有符号16位PCM采样与mixer格式一致。
from array import array
# 外部游戏声音通过明确路径传入。
from pathlib import Path
# 设备失败时保留可理解的原因。
import sys

# 声音设备在显式start阶段初始化。
import pygame


# 应用拥有播放器，退出时由应用边界关闭pygame设备。
class LandingAudio:
    # 构造只保存输出策略和可选路径。
    def __init__(self, is_silent: bool, source: Path | None = None) -> None:
        # 显式静音不接触声音设备。
        self.is_silent = is_silent
        # 外部声音路径已经由资源入口校验。
        self.source = source
        # 初始化前没有声音对象。
        self.sound: pygame.mixer.Sound | None = None
        # 编号零表示尚未消费落地事件。
        self.played_serial = 0

    # 显式准备设备，缺设备时报告并继续无声游戏。
    def start(self) -> None:
        # 静音策略优先于设备初始化。
        if self.is_silent:
            # 不生成采样或加载文件。
            return
        # 只在音频边界转换pygame设备错误。
        try:
            # 统一为44100Hz单声道有符号16位PCM。
            pygame.mixer.init(frequency=44100, size=-16, channels=1, allowedchanges=0)
            # 外部包提供声音时保留其真实内容。
            if self.source is not None:
                # 坏资源明确进入错误报告，不伪装成功。
                self.sound = pygame.mixer.Sound(str(self.source))
            # 干净安装包自带公式生成的提示音。
            else:
                # 7056个采样等于0.16秒，音高与响度逐渐降低。
                samples = array("h", (round(6500 * math.sin(2 * math.pi * (160 - 80 * index / 7056) * index / 44100)
                                            # 尾部衰减到零，避免突然截断。
                                            * (1 - index / 7056) ** 2) for index in range(7056)))
                # 原始PCM与当前设备格式匹配。
                self.sound = pygame.mixer.Sound(buffer=samples.tobytes())
            # 保留幅度余量。
            self.sound.set_volume(0.65)
        # 无设备不影响游戏可操作性，但不能隐瞒原因。
        except pygame.error as error:
            # 后续消费事件但不重复尝试启动设备。
            self.sound = None
            # 仅报告音频失败，不声称已听音验收。
            print(f"声音不可用，继续无声运行：{error}", file=sys.stderr)

    # 每个新落地编号只发声一次。
    def update(self, landing_serial: int) -> None:
        # 相同编号没有新事件。
        if landing_serial == self.played_serial:
            # 保持原状态。
            return
        # 只有设备成功准备后才播放。
        if self.sound is not None:
            # 异步播放不阻塞绘图。
            self.sound.play()
        # 静音也消费事件，避免重放旧落地。
        self.played_serial = landing_serial

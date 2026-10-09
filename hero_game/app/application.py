"""协调输入、模型、绘图与声音，窗口生命周期由外层入口管理。"""

# 框架提供帧率控制和窗口刷新。
import pygame

# 声音仅消费游戏事件。
from hero_game.app.audio import LandingAudio
# 输入控制器拥有按键集合。
from hero_game.app.input_controller import InputController
# 模型不反向依赖应用。
from hero_game.model.game import Game
# 绘制器不推进时间。
from hero_game.rendering.renderer import Renderer


# 一个实例协调一个窗口的依赖，构造不启动循环。
class Application:
    # 零帧限制表示交互运行，无显示模式使用固定步长。
    def __init__(self, model: Game, renderer: Renderer, window: pygame.Surface,
                 # 控制器和声音均由外层明确创建。
                 input_controller: InputController, audio: LandingAudio,
                 # 验收参数不影响游戏剧情数据。
                 frame_limit: int = 0, headless: bool = False) -> None:
        # 模型由当前应用协调。
        self.model = model
        # 绘制器引用同一模型。
        self.renderer = renderer
        # 外层持有窗口的创建和释放责任。
        self.window = window
        # 输入状态由控制器所有。
        self.input_controller = input_controller
        # 声音对象只观察事件。
        self.audio = audio
        # 零表示不自动退出。
        self.frame_limit = frame_limit
        # 无显示验收不等待墙上时间。
        self.headless = headless

    # 显式运行并返回已完成显示的帧数。
    def run(self) -> int:
        # 当前运行持有自己的帧率时钟。
        clock = pygame.time.Clock()
        # 只统计实际完成的帧。
        frame_count = 0
        # 达到限制或收到退出事件时结束。
        while self.frame_limit == 0 or frame_count < self.frame_limit:
            # 虚拟检查使用稳定步长，交互窗口限制到60FPS。
            dt = 1 / 60 if self.headless else min(clock.tick(60) / 1000, 0.05)
            # 处理输入并获取切换当帧的冻结请求。
            is_running, freeze_frame = self.input_controller.handle_events(pygame.event.get())
            # 退出后不再推进世界。
            if not is_running:
                # 返回真实已完成帧数。
                return frame_count
            # 查询归一化前的输入方向。
            dx, dy = self.input_controller.direction()
            # 状态切换当帧不补走或跳字。
            self.model.update(0 if freeze_frame else dt, dx, dy)
            # 登场和对话不继承旧移动键。
            self.input_controller.clear_blocked_input()
            # 消费新落地事件。
            self.audio.update(self.model.landing_serial)
            # 最近邻缩放保留像素边缘。
            self.window.blit(pygame.transform.scale(self.renderer.draw(), self.window.get_size()), (0, 0))
            # 将本帧送到窗口。
            pygame.display.flip()
            # 显示成功后才增加计数。
            frame_count += 1
        # 指定的帧数已实际完成。
        return frame_count

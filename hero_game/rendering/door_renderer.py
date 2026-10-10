"""动态门板与通道绘制，门框位置由正式规则提供。"""

# pygame只用于内存像素绘制，不参与通关条件判断。
import pygame


# 缓存门板纹理，绘制不会修改共享房间底图。
class DoorRenderer:
    # 背景中的原门可复用纹理，基础资源则生成独立木门。
    def __init__(self, background: pygame.Surface, bounds: tuple[float, float, float, float], baked: bool) -> None:
        # 四边转换为绘图矩形，不改变模型的逻辑入口。
        self.rect = pygame.Rect(round(bounds[0]), round(bounds[1]), round(bounds[2] - bounds[0]), round(bounds[3] - bounds[1]))
        # 外部原门纹理取副本，开门压缩不会污染背景缓存。
        self.texture = background.subsurface(self.rect).copy() if baked else pygame.Surface(self.rect.size)
        # 基础画面没有烘焙木门，先生成可发行的程序纹理。
        if not baked:
            # 深棕木门与开放后的暖光通道区分。
            self.texture.fill((104, 73, 48))
            # 木纹条保留可见的门板身份。
            for x in range(3, self.rect.width, 6):
                # 木纹只写入当前门板，不写入共享背景。
                pygame.draw.line(self.texture, (126, 89, 58), (x, 2), (x, self.rect.height - 3))
            # 金色门把手靠近右侧。
            pygame.draw.circle(self.texture, (225, 187, 98), (self.rect.width - 6, self.rect.height // 2), 2)

    # 按到点后的秒数把门板收向左侧，返回门洞右边界供角色遮挡。
    def draw(self, surface: pygame.Surface, open_seconds: float, is_open: bool) -> None:
        # 门框在动态层绘制，基础背景同样具备清晰出口。
        pygame.draw.rect(surface, (28, 31, 35), self.rect.inflate(6, 6))
        # 关闭时覆盖完整门板，不出现假通道。
        if not is_open:
            # 同一份缓存纹理用于闭合与转开的门。
            surface.blit(self.texture, self.rect)
            # 闭门绘制完成。
            return
        # 暖光通道对应门外安全区。
        pygame.draw.rect(surface, (202, 180, 125), self.rect)
        # 内侧暗边形成可辨认的深度。
        pygame.draw.rect(surface, (116, 102, 74), (self.rect.left, self.rect.top, 5, self.rect.height))
        # 0.8秒完成开门，进度封顶后不再改变门板宽度。
        progress = max(0.0, min(1.0, open_seconds / 0.8))
        # 余下细边代表门板收在左侧，门洞不会被完全擦掉。
        width = max(4, round(self.rect.width * (1 - progress)))
        # 最近邻缩放保留既有像素木纹。
        panel = pygame.transform.scale(self.texture, (width, self.rect.height))
        # 左门轴固定，动态门板不会漂移。
        surface.blit(panel, self.rect.topleft)

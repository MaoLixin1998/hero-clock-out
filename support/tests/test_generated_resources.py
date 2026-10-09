"""验证程序基础资源完整且各资源实例没有共享可变缓存。"""

# 标准框架检查实际生成图像与缓存所有权。
import unittest

# pygame提供画布字节和字体初始化，不开启显示窗口。
import pygame

# 正式逻辑画布大小由同一运行配置定义。
from hero_game.config import LOGICAL_SIZE
# 默认资源工厂仅生成基础图形，不读取assets或production。
from hero_game.rendering.generated_resources import create_generated_resources


# 资源回归不依赖任何本机艺术素材、中文字体文件或声音设备。
class GeneratedResourceChecks(unittest.TestCase):
    # 生成文字图形前按真实框架契约初始化字体模块。
    def setUp(self) -> None:
        # 资源工厂不应在导入时初始化pygame，由应用边界负责准备。
        pygame.font.init()

    # 检查结束释放字体状态，避免影响其他测试。
    def tearDown(self) -> None:
        # 没有创建显示窗口或声音设备，只清理本例持有的字体模块。
        pygame.font.quit()

    # 默认资源必须足够绘制两角色、全部朝向、对话和时钟。
    def test_generated_bundle_is_complete_without_private_files(self) -> None:
        # 使用实际工厂构造完整基础资源，不传入任何路径。
        resources = create_generated_resources()
        # 背景完整覆盖正式逻辑画布。
        self.assertEqual(resources.background.get_size(), LOGICAL_SIZE)
        # 两种角色的四向组合都必须存在，不允许缺帧后才启动失败。
        expected_directions = {
            # 每个组合按稳定角色ID与方向ID索引。
            (kind, direction)
            # 两种角色覆盖正常游戏和追击场景。
            for kind in ("hero", "slime")
            # 朝向与模型实际四向状态一致。
            for direction in ("down", "left", "up", "right")
        }
        # 动画缓存不能漏掉某个正式方向。
        self.assertEqual(set(resources.animations), expected_directions)
        # 每套动画都有可播放帧与合法时长。
        for frames, metadata in resources.animations.values():
            # 实际图像帧数要与用于选择帧的元数据对应。
            self.assertEqual(len(frames), len(metadata["frames"]))
            # 空帧列表无法绘制，因此至少提供一帧。
            self.assertGreater(len(frames), 0)
            # 默认基础帧尺寸统一，以同一锚点计算身体位置。
            self.assertTrue(all(frame.get_size() == (64, 64) for frame in frames))
            # 非零正时长避免动画周期除零。
            self.assertTrue(all(item["duration_ms"] > 0 for item in metadata["frames"]))
        # 对话立绘必须覆盖正式说话者。
        self.assertEqual(set(resources.portraits), {"hero", "slime"})
        # 面板、姓名牌与翻页箭头是绘制对话的必要组件。
        self.assertTrue({"panel", "nameplate", "advance"}.issubset(resources.dialogue_ui))
        # 缺少个人声音仍有完整默认路径，不产生隐式文件依赖。
        self.assertIsNone(resources.landing_sound)

    # 修改一份资源实例不能污染另一次创建的基础缓存。
    def test_resource_instances_do_not_share_mutable_images_or_metadata(self) -> None:
        # 第一个应用持有第一份资源实例。
        first = create_generated_resources()
        # 第二份资源不能直接复用第一份可变画布或子列表。
        second = create_generated_resources()
        # 保存第二份背景实际字节，避免仅比较对象地址。
        second_background = pygame.image.tobytes(second.background, "RGB")
        # 明确修改第一份背景。
        first.background.fill((255, 0, 255))
        # 第二份背景字节必须保持原样。
        self.assertEqual(pygame.image.tobytes(second.background, "RGB"), second_background)
        # 修改第一份动画的嵌套元数据，覆盖容易被浅拷贝遗漏的所有权问题。
        first.animations["hero", "down"][1]["frames"][0]["duration_ms"] = 999
        # 第二份资源保留自己的正常帧时长。
        self.assertNotEqual(second.animations["hero", "down"][1]["frames"][0]["duration_ms"], 999)

"""验证已注入依赖的纯游戏模型不通过文件IO补齐或更新状态。"""

# 路径类型用于封锁真实文件读取入口，不以假配置替代模型。
from pathlib import Path
# 标准测试框架报告模型构造与真实移动结果。
import unittest
# 受控替身在测试作用域内让任何文件读取立即失败。
from unittest.mock import patch

# 配置适配器在封锁文件IO之前准备独立正式数据。
from hero_game.config import load_game_dialogue, load_game_rules
# 直接构造纯模型，避免应用工厂代替受测对象完成验证。
from hero_game.model.game import Game


# 纯模型接收已准备的数据后，构造、移动、重开和对白只应使用内存状态。
class ModelIoBoundaryChecks(unittest.TestCase):
    # 阻断常见Python文件入口后，正式模型仍能构造并真实移动。
    def test_injected_model_constructs_and_moves_without_file_reads(self) -> None:
        # 默认规则只在外部准备阶段读取，之后归模型独立持有。
        rules = load_game_rules()
        # 正式对白同样在应用边界准备，不由模型偷偷加载。
        dialogue_data = load_game_dialogue()
        # 预期出生点来自调用方独立数据，不能从受测对象反推结果。
        expected_spawn = tuple(rules["heroSpawn"])
        # 以真实秒数和配置速度计算应产生的横向位移。
        expected_distance = rules["heroSpeed"] * 0.025
        # 同时封锁Path与内置文件入口，任何隐藏配置读取都使测试直接失败。
        with (
            # 捕获直接使用Path.read_text读取默认JSON的旧实现。
            patch.object(Path, "read_text", side_effect=AssertionError("纯模型不能读取配置文件")) as read_text,
            # 捕获Path.open及read_bytes等绕过read_text的路径读取。
            patch.object(Path, "open", side_effect=AssertionError("纯模型不能打开路径文件")) as open_path,
            # 捕获直接调用内置open读取磁盘的替代实现。
            patch("builtins.open", side_effect=AssertionError("纯模型不能调用文件IO")) as open_file,
        ):
            # 显式注入全部规则和对白，跳过开场只为独立观察真实位移。
            model = Game(rules=rules, dialogue_data=dialogue_data, play_intro=False)
            # 无窗口、资源或应用循环也能执行真实运动更新。
            model.update(0.025, 1, 0)
            # 横坐标按真实速度推进，证明模型并非只是在错误路径上无操作返回。
            self.assertAlmostEqual(model.hero.x, expected_spawn[0] + expected_distance)
            # 水平输入不会改变纵坐标。
            self.assertEqual(model.hero.y, expected_spawn[1])
            # 有效游戏时间也在内存中正常推进。
            self.assertAlmostEqual(model.elapsed, 0.025)
            # 重开复用已注入数据，不能重新从配置文件读取。
            model.reset(play_intro=False)
            # 重开回到传入的出生点，证明重置操作真实完成。
            self.assertEqual((model.hero.x, model.hero.y), expected_spawn)
            # 正式对白通过稳定场景ID启动，不去磁盘寻找对应台词。
            model.dialogue.start("intro")
            # 推进逐字时间也无需文件读取。
            model.update(0.05)
            # 已注入的第一句实际成为当前正文。
            self.assertEqual(model.dialogue.text(), dialogue_data["intro"][0]["text"])
            # 旧默认配置读取入口在整个模型生命周期中没有被使用。
            read_text.assert_not_called()
            # 路径文件接口也没有被模型绕用。
            open_path.assert_not_called()
            # 内置文件接口同样保持未调用。
            open_file.assert_not_called()

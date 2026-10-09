"""验证对话播放器的错误输入、空场景与查询快照所有权。"""

# 标准测试框架检查明确异常和调用前后的播放状态。
import unittest

# 正式游戏数据由包内配置入口独立读取。
from hero_game.config import load_game_dialogue
# 对话播放器不读取素材或启动任何pygame模块。
from hero_game.model.dialogue import Dialogue


# 播放器回归关注稳定接口，不在测试里复制具体游戏对白。
class DialoguePlayerChecks(unittest.TestCase):
    # 外部原稿与查询快照的修改都不得改变正在播放的正文。
    def test_input_and_query_snapshots_do_not_change_playback(self) -> None:
        # 预期文字取独立解析的数据，不从播放器自己反推。
        expected_text = load_game_dialogue()["intro"][0]["text"]
        # 调用方持有自己的配置对象。
        provided_data = load_game_dialogue()
        # 播放器接收输入时取得独立嵌套副本。
        dialogue = Dialogue(provided_data)
        # 启动真实游戏场景，不提前补全显示时间。
        dialogue.start("intro")
        # 修改调用方保存的输入，检查是否泄漏引用。
        provided_data["intro"][0]["text"] = "changed input"
        # 完整配置查询也应是独立快照。
        data_snapshot = dialogue.data
        # 修改快照不能回写内部原稿。
        data_snapshot["intro"][0]["text"] = "changed snapshot"
        # 当前段落列表也不能泄漏可变正文。
        lines_snapshot = dialogue.lines
        # 修改返回列表中的嵌套台词，覆盖浅层复制不足的风险。
        lines_snapshot[0]["text"] = "changed list"
        # 当前句查询提供另一份独立快照。
        current_snapshot = dialogue.current
        # 活动场景必须存在当前句，否则后续修改没有检查意义。
        self.assertIsNotNone(current_snapshot)
        # 显式收窄类型，异常应由断言报告而不是后续索引错误。
        if current_snapshot is not None:
            # 当前句快照同样不能改写真正播放正文。
            current_snapshot["text"] = "changed current"
        # 四种外部写入都不能改变实际文字。
        self.assertEqual(dialogue.text(), expected_text)

    # 选择不存在或元数据场景时，原段落和播放秒数必须完整保留。
    def test_unknown_scene_preserves_current_playback(self) -> None:
        # 独立播放器不依赖游戏更新循环。
        dialogue = Dialogue(load_game_dialogue())
        # 启动正式场景并推进一段逐字时间。
        dialogue.start("intro")
        # 0.1秒足够建立非初始播放状态。
        dialogue.update(0.1)
        # 完整保存当前查询状态作为异常后的对照。
        before = (dialogue.current, dialogue.index, dialogue.seconds)
        # 不存在场景和顶层元数据都不是可播放ID。
        for invalid_scene in ("missing_scene", "speakers", "charactersPerSecond"):
            # 错误应清楚抛出，不静默清空原场景。
            with self.assertRaises(ValueError):
                # 使用播放器公开场景选择入口。
                dialogue.start(invalid_scene)
            # 错误选择不能使已播放文字倒退或切到其他句。
            self.assertEqual((dialogue.current, dialogue.index, dialogue.seconds), before)

    # 正式允许空场景，重复查询和确认应保持一致的结束状态。
    def test_empty_scene_and_empty_text_are_valid(self) -> None:
        # 每例取得独立正式数据。
        data = load_game_dialogue()
        # 空列表明确表达没有这段对白，与缺失场景不同。
        data["intro"] = []
        # 空正文同样是合法字段，不采用其他文案覆盖它。
        data["caught"][0]["text"] = ""
        # 初始化真实播放器，验证空值在边界被保留。
        dialogue = Dialogue(data)
        # 启动空场景应立即处于合法结束状态。
        dialogue.start("intro")
        # 空场景不持有活动句。
        self.assertFalse(dialogue.active)
        # 无当前句与配置错误采用不同返回表达。
        self.assertIsNone(dialogue.current)
        # 结束后重复确认不能越界。
        dialogue.advance()
        # 重复跳过同样安全。
        dialogue.skip()
        # 查询统一返回空字符串。
        self.assertEqual(dialogue.visible_text(), "")
        # 启动有合法空正文的正式场景。
        dialogue.start("caught")
        # 空正文必须保持为空，不回退到英文或其他默认句。
        self.assertEqual(dialogue.text(), "")
        # 空句已完整，首次确认就应进入下一句。
        dialogue.advance()
        # 句索引实际推进，证明空正文没有卡住对话。
        self.assertEqual(dialogue.index, 1)

    # 未登记角色和非法打字速率必须在播放前拒绝。
    def test_invalid_speaker_and_typewriter_rate_are_rejected(self) -> None:
        # 先单独检查未登记角色ID。
        data = load_game_dialogue()
        # 用无对应姓名与立绘的ID替换第一句角色。
        data["intro"][0]["speaker"] = "unknown_speaker"
        # 初始化失败不会拖到绘制时才报告缺立绘。
        with self.assertRaises(ValueError):
            # 调用真实配置验证所在的播放器构造。
            Dialogue(data)
        # 零速、布尔值和非有限速率都不能产生有效逐字时间。
        for invalid_rate in (0, -1, True, float("nan"), float("inf")):
            # 每个速率案例从完整正式数据开始。
            data = load_game_dialogue()
            # 只替换当前待验证字段。
            data["charactersPerSecond"] = invalid_rate
            # 错误不允许被默认28字符每秒掩盖。
            with self.assertRaises(ValueError):
                # 在创建播放器时立即失败。
                Dialogue(data)

    # 非有限更新时长不能改变已有打字进度。
    def test_nonfinite_update_is_atomic(self) -> None:
        # 初始化独立播放器并启动真实场景。
        dialogue = Dialogue(load_game_dialogue())
        # 默认场景提供可推进的句子。
        dialogue.start("intro")
        # 非零进度使失败后清零等错误也能被发现。
        dialogue.update(0.1)
        # 保存已有显示秒数作为预期。
        expected_seconds = dialogue.seconds
        # 所有非法时间都应明确失败。
        for invalid in (float("nan"), float("inf"), True):
            # 不允许把错误时间当作零或极大时长。
            with self.assertRaises(ValueError):
                # 直接更新真实播放器。
                dialogue.update(invalid)
            # 异常不得部分改变播放状态。
            self.assertEqual(dialogue.seconds, expected_seconds)

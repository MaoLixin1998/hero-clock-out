"""验证正式游戏对白与世界状态保持一致。"""

# 标准测试框架检查确认、打字、跳过与冻结行为。
import unittest

# 预期场景来自正式游戏数据，测试正文不复制实际对白。
from hero_game.config import load_game_dialogue
# 应用工厂提供默认正式数据，模型持有独立对话与追击状态。
from hero_game.app.game_factory import create_game


# 台词测试从正式数据读取预期值，不依赖制作文稿。
class DialogueChecks(unittest.TestCase):
    # 检查确认键先补全当前句，第二次才换句并重新打字。
    def test_confirm_reveals_then_advances(self) -> None:
        # 跳过演出，仅检查确认键是否正确控制逐字台词。
        dialogue = create_game(play_intro=False).dialogue
        # 单独启动固定台词，当前检查只关注对话播放器的确认行为。
        dialogue.start("intro")
        # 开场刚启动时应还没有字出现，确认逐字计时从零开始。
        self.assertEqual(dialogue.visible_text(), "")
        # 第一次确认只补全本句；第二次才换角色，避免把没看完的句子跳掉。
        dialogue.advance()
        # 确认第一次确认操作显示整句，玩家不必一直等待打字效果。
        self.assertEqual(dialogue.visible_text(), dialogue.text())
        # 确认说话者仍是史莱姆，第一次确认没有把当前句直接跳掉。
        self.assertEqual(dialogue.current["speaker"], "slime")
        # 再确认一次，这时当前句已完整，应该进入下一句。
        dialogue.advance()
        # 确认下一句换成勇者，台词顺序与角色立绘切换一致。
        self.assertEqual(dialogue.current["speaker"], "hero")
        # 新的一句显示时间归零，应该重新从空文字逐字出现。
        self.assertEqual(dialogue.visible_text(), "")

    # 检查开场只有文字推进，跳过后恢复角色移动。
    def test_intro_freezes_world_but_reveals_text(self) -> None:
        # 跳过演出并启动对话，检查台词期间世界是否冻结。
        model = create_game(play_intro=False)
        # 本组专门检查台词冻结；走路与跳出的完整顺序由开场检查覆盖。
        model.dialogue.start("intro")
        # 复制双方全部角色字段、有效时间、缓冲和转向倒计时，保存对照快照。
        before = (vars(model.hero).copy(), vars(model.slime).copy(),
                  # 把游戏有效时间、开场缓冲和转向倒计时也放入快照，不能只检查角色坐标。
                  model.elapsed, model.start_delay, model.retarget_in)
        # 重复四十次更新，提供足够的时间让文字出现。
        for _ in range(40):
            # 每次传入右下移动输入，刻意检查对话期间玩家输入是否被忽略。
            model.update(0.05, 1, 1)
        # 确认整个世界快照保持一致；对话没有消耗逃跑的起步缓冲。
        self.assertEqual(before, (vars(model.hero), vars(model.slime),
                                  # 同步比较所有计时字段，确认对话没消耗敌人等待或转向反应时间。
                                  model.elapsed, model.start_delay, model.retarget_in))
        # 确认当前整句已显示，世界冻结不等于打字停止；读取配置中的台词，避免正常改文案导致误报。
        self.assertEqual(model.dialogue.visible_text(), model.dialogue.text())
        # 结束开场对话，游戏应允许开始正常追逐。
        model.dialogue.skip()
        # 向右更新一小步，确认跳过台词后真正恢复角色移动。
        model.update(0.05, 1, 0)
        # 确认勇者横坐标增加，没有被旧对话状态永久冻结。
        self.assertGreater(model.hero.x, before[0]["x"])

    # 检查失败台词跳过后仍失败，只有明确重开才能重新逃跑。
    def test_capture_dialogue_skip_does_not_revive_player(self) -> None:
        # 创建不播开场的游戏，用实际追击制造被抓场景。
        model = create_game(play_intro=False)
        # 推进一百次更新，保证敌人有机会走到原地勇者身边。
        for _ in range(100):
            # 不提供移动方向，勇者停在原地，史莱姆自然追上。
            model.update(0.05)
        # 确认已经失败，不直接伪造结果来替代实际追击。
        self.assertTrue(model.caught)
        # 失败对话第一句应由史莱姆说，姓名与立绘跟随这个编号。
        self.assertEqual(model.dialogue.current["speaker"], "slime")
        # 独立读取包内正式游戏数据，检查失败场景加载与切换。
        dialogue_config = load_game_dialogue()
        # 取失败场景第一句作为预期值，检查被抓后切换到了正确的场景。
        expected_text = dialogue_config["caught"][0]["text"]
        # 确认配置提供非空文字，避免空内容让场景加载检查失去意义。
        self.assertTrue(expected_text.strip())
        # 比较运行时实际文字与独立读取的配置，验证加载与场景切换。
        self.assertEqual(model.dialogue.text(), expected_text)
        # 记录被抓时勇者、敌人横坐标和有效游戏时间，供跳过后比较。
        before = (model.hero.x, model.slime.x, model.elapsed)
        # 跳过整段失败台词；这个动作只能结束文字，不能解除失败。
        model.dialogue.skip()
        # 尝试向右更新，检查失败冻结是否仍然生效。
        model.update(0.05, 1, 0)
        # 确认坐标与时间保持原值，跳过台词没有让角色复活。
        self.assertEqual(before, (model.hero.x, model.slime.x, model.elapsed))
        # 明确重开一局，只有这个操作才应该清除失败。
        model.reset()
        # 确认 caught 变回 False，新的追逐可以正常进行。
        self.assertFalse(model.caught)
        # 确认重试不重复开场台词，直接开始勇者逃跑。
        self.assertFalse(model.dialogue.active)

    # 检查后台暂停连台词打字时间也冻结。
    def test_focus_pause_also_stops_typewriter(self) -> None:
        # 直接进入开场台词，当前还没有经过任何打字时间。
        model = create_game(play_intro=False)
        # 本组专门检查台词冻结；走路与跳出的完整顺序由开场检查覆盖。
        model.dialogue.start("intro")
        # 设置暂停，模拟窗口切到后台后的状态。
        model.paused = True
        # 尝试推进一帧，暂停应该连台词打字也冻结。
        model.update(0.05)
        # 确认打字秒数仍为零，后台时间没有偷偷消耗文字播放进度。
        self.assertEqual(model.dialogue.seconds, 0)

"""验证真实过门后的结局、输入隔离、暂停与重开。"""

# 标准测试只推进模拟时间，不需要真实等待或外部素材。
import unittest

# 正式工厂保留真实出口与默认对白的组装边界。
from hero_game.app.game_factory import create_game
# 每个案例读取独立正式规则，缩短等待而不伪造成功字段。
from hero_game.config import load_game_rules
# 返回类型说明测试得到的仍是正式游戏模型。
from hero_game.model.game import Game


# 玩家真实到达门槛后，完整结局必须与失败、重玩保持一致。
class EndingChecks(unittest.TestCase):
    # 恰好七秒的门外回放必须完成，不能只靠多推进一帧绕过浮点尾差。
    def test_exact_seven_second_outside_duration_finishes_at_all_frame_rates(self) -> None:
        # 三种常用帧率累计同一物理时长。
        for frames_per_second in (30, 60, 120):
            # 每轮从真实成功事件开始。
            model = self.escaped_model()
            # 正常更新完成1.4秒跨门，初态不写私有时间。
            for _ in range(28):
                # 单次0.05秒满足Game的公开时间边界。
                model.update(0.05)
            # 此刻进入门外的起始帧。
            self.assertEqual(model.ending_phase, "outside")
            # 恰好推进七秒，不多补帧。
            for _ in range(7 * frames_per_second):
                # 时间以秒计，与显示帧数解耦。
                model.update(1 / frames_per_second)
            # 结束状态与光照端点都必须精确成立。
            self.assertEqual((model.ending_phase, model.ending_night_progress), ("complete", 1.0))

    # 受控出生点与保护期仅排除无关追击，通关仍由正常位移触发。
    def escaped_model(self) -> Game:
        # 正式门前出生，闭门时不会提前成功。
        rules = {**load_game_rules(), "heroSpawn": [516, 305], "gameSecondsPerMinute": 0.1,
                 # 保护期覆盖两帧开门条件，敌人没有被删除。
                 "startDelaySeconds": 2}
        # 跳过首次开场，直接验证正常追逐到出口的流程。
        model = create_game(rules=rules, play_intro=False)
        # 第一帧走到闭门区域，时间条件尚未成立。
        model.update(0.05, 1, 0)
        # 玩家在门前等待到点，真实规则产生成功。
        model.update(0.05)
        # 每个后续案例都要求真实触发前提。
        self.assertTrue(model.escaped)
        # 返回同一个模型，不用替身覆盖任何状态。
        return model

    # 门前触发成功后仍须有可见位移，不能立刻跳到安全区或恢复追逐。
    def test_crossing_moves_snapshot_while_chase_and_input_stay_frozen(self) -> None:
        # 通过真实规则开始跨门。
        model = self.escaped_model()
        # 成功初态保留门前位置，尚未切到门外。
        self.assertEqual(model.ending_phase, "crossing")
        # 冻结追逐快照，后续反向输入也不能继续运行敌人。
        chase_snapshot = (vars(model.hero).copy(), vars(model.slime).copy(), model.elapsed)
        # 半秒持续反向输入，过门应仍朝出口推进。
        for _ in range(10):
            # 普通Game.update负责阶段分流，不直接调用结局组件。
            model.update(0.05, -1, -1)
        # 独立角色确实向原门移动，而不是身体坐标固定的迈腿。
        self.assertGreater(model.ending_actor.x, model.hero.x)
        # 没有跨完时仍在办公室，不能靠文字宣布已到门外。
        self.assertEqual(model.ending_phase, "crossing")
        # 胜负和钟仍冻结在触发瞬间。
        self.assertEqual(chase_snapshot, (vars(model.hero), vars(model.slime), model.elapsed))
        # 外部修改查询快照不能穿透到结局内部。
        snapshot = model.ending_actor
        # 此处故意修改返回对象以检测封装边界。
        snapshot.x = 0
        # 下一次查询仍保留真实过门位置。
        self.assertGreater(model.ending_actor.x, model.hero.x)

    # 暂停冻结结局而重玩完全清除旧状态，不会在新局突然切回门外。
    def test_pause_and_reset_isolate_ending_lifecycle(self) -> None:
        # 同一正式模型进入成功序列。
        model = self.escaped_model()
        # 先推进到跨门中途，避免只检验零初态。
        model.update(0.05)
        # 保存独立结局的秒数与位置。
        before = (model.ending_elapsed, vars(model.ending_actor).copy())
        # 模型公开暂停用于受控生命周期验证。
        model.paused = True
        # 暂停中的更新不能继续跨门。
        model.update(0.05)
        # 秒数与角色均保持原值。
        self.assertEqual(before, (model.ending_elapsed, vars(model.ending_actor)))
        # 正式重开接口创建一局新的完整状态。
        model.reset()
        # 新局没有旧结局角色。
        self.assertIsNone(model.ending_actor)
        # 阶段也回到未开始，不能恢复旧动画。
        self.assertEqual(model.ending_phase, "inactive")
        # 新局仍需等待17:30并亲自走到出口。
        self.assertFalse(model.escaped or model.door_open)

    # 不同帧率均从门口向右离画，光照完成且终态不重新出现角色。
    def test_complete_outside_ending_at_supported_frame_rates(self) -> None:
        # 分别检查常用三种更新节奏。
        for frames_per_second in (30, 60, 120):
            # 每个子案例记录独立帧率。
            with self.subTest(fps=frames_per_second):
                # 每轮从真实成功事件开始。
                model = self.escaped_model()
                # 十秒足够跨门、门外行走与夜景，核心状态不能依赖显示帧数。
                for _ in range(10 * frames_per_second):
                    # 跟普通游戏一样按秒推进。
                    model.update(1 / frames_per_second)
                # 结尾稳定留下夜景空镜。
                self.assertEqual(model.ending_phase, "complete")
                # 角色向右完全离画后才停止步态。
                self.assertEqual((model.ending_actor.direction, model.ending_actor.moving), ("right", False))
                # 64像素身体左边缘也越过画布右界，不能残留半个角色。
                self.assertEqual((model.ending_actor.x, model.ending_actor.y), (680, 240))
                # 最后必须完整到达夜景，不能停在半透明夕阳。
                self.assertEqual(model.ending_night_progress, 1.0)
                # 成功不会在过场中重新被抓。
                self.assertFalse(model.caught)

    # 门外的起点在左门附近，连续位移与日夜进度不能跳变或被反向输入打断。
    def test_outside_walks_from_door_to_right_and_finishes_night_after_exit(self) -> None:
        # 仍通过真实门槛和时间判定进入结局。
        model = self.escaped_model()
        # 保存冻结的追逐时间和敌人位置。
        chase_state = (model.elapsed, vars(model.slime).copy())
        # 在完整跨门后多推进一帧，观察门外起步。
        for _ in range(29):
            # 玩家反向输入不能改变结局方向。
            model.update(0.05, -1, 0)
        # 第一个门外采样应在左侧门口，不能直接出现在中央。
        self.assertLess(model.ending_actor.x, 100)
        # 行走帧和向右朝向均已开始。
        self.assertEqual((model.ending_actor.direction, model.ending_actor.moving), ("right", True))
        # 保存连续查询值，以验证运动和光照的单调性。
        previous = (model.ending_actor.x, model.ending_night_progress)
        # 六秒半观察到完整离画，但尚未达到七秒夜景终点。
        for _ in range(130):
            # 正式更新负责进度，不直接修改角色或时间。
            model.update(0.05, -1, 0)
            # 角色不能向门退回或瞬移到较左位置。
            self.assertGreaterEqual(model.ending_actor.x, previous[0])
            # 光照不能在任一帧重新变亮。
            self.assertGreaterEqual(model.ending_night_progress, previous[1])
            # 更新下一帧比较所用的只读查询。
            previous = (model.ending_actor.x, model.ending_night_progress)
        # 角色已完全离画，夜景仍有尾段变化。
        self.assertEqual(model.ending_actor.x, 680)
        # 不用角色离画事件提前结束光照。
        self.assertLess(model.ending_night_progress, 1)
        # 史莱姆与办公室计时在整个门外过程保持冻结。
        self.assertEqual(chase_state, (model.elapsed, vars(model.slime)))

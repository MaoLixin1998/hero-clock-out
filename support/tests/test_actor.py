"""验证单角色运动接口的时间、方向与边界错误处理。"""

# 标准测试框架确认错误调用不会部分修改角色。
import unittest

# 独立运动对象不依赖窗口、游戏阶段或资源路径。
from hero_game.model.actor import Actor


# 检查低层运动边界，保证上层输入错误不会污染位置与动画状态。
class ActorChecks(unittest.TestCase):
    # 零速和零时长都应保持坐标，同时不能播放实际行走动画。
    def test_zero_speed_and_zero_duration_do_not_move(self) -> None:
        # 逐个验证两个合法零值入口。
        for duration_seconds, speed_pixels_per_second in ((0, 160), (0.05, 0)):
            # 每例创建独立角色，避免上一案例残留状态。
            actor = Actor("hero", 250, 230)
            # 向右提供真实方向，但零值不应产生任何位移。
            actor.move(1, 0, duration_seconds, speed_pixels_per_second, (80, 172, 548, 328))
            # 角色身体位置必须与创建时一致。
            self.assertEqual((actor.x, actor.y), (250, 230))
            # 没有实际位移就保持待机。
            self.assertFalse(actor.moving)
            # 行走动画累计时间保持为零。
            self.assertEqual(actor.phase, 0)

    # 无效时间、速度、方向和边界必须先失败，再保证原状态完整保留。
    def test_invalid_movement_is_atomic(self) -> None:
        # 参数依次为横向、纵向、秒数、每秒速率和活动矩形。
        invalid_cases = (
            # 时间不能倒流。
            (1, 0, -0.1, 160, (80, 172, 548, 328)),
            # 速度不能是负数。
            (1, 0, 0.05, -1, (80, 172, 548, 328)),
            # 输入方向不能使用非有限值。
            (float("nan"), 0, 0.05, 160, (80, 172, 548, 328)),
            # 布尔开关不能伪装纵向数值。
            (0, True, 0.05, 160, (80, 172, 548, 328)),
            # 无穷时间会破坏位移和动画累计。
            (1, 0, float("inf"), 160, (80, 172, 548, 328)),
            # 反向活动矩形没有合法夹紧范围。
            (1, 0, 0.05, 160, (548, 172, 80, 328)),
        )
        # 每个案例都从同一独立初始状态检查。
        for parameters in invalid_cases:
            # 初始状态包含非默认朝向，避免只验证两个坐标。
            actor = Actor("hero", 250, 230, direction="left", phase=0.1)
            # 完整复制原字段，判断异常前有无部分更新。
            before = vars(actor).copy()
            # 接口明确用ValueError报告非法运动数值。
            with self.assertRaises(ValueError):
                # 调用正式运动方法，不在测试里重写校验。
                actor.move(*parameters)
            # 错误调用不得改变位置、朝向、运动标志或时间。
            self.assertEqual(vars(actor), before)

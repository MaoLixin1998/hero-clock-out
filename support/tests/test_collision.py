"""验证连续接触、矩形过门与首次事件比例的几何边界。"""

# 标准测试框架报告几何边界的实际结果。
import unittest

# 连续碰撞函数检测整段相对轨迹，防止高速穿过被漏判。
from hero_game.model.collision import capture_contact_fraction, crossed_capture_radius, rectangle_entry_fraction


# 几何回归独立于游戏阶段与图像透明边缘。
class CollisionChecks(unittest.TestCase):
    # 检查碰撞看整段相对轨迹，不会漏掉两端都在外部的快速穿过。
    def test_swept_capture_detects_crossing_even_if_endpoints_miss(self) -> None:
        # 线段从左到右穿过原点，即使两端都在 22 像素外也应碰撞。
        self.assertTrue(crossed_capture_radius((-30, 0), (30, 0), 22))
        # 同样横穿但保持 23 像素高度，整段都在 22 像素范围外，不应碰撞。
        self.assertFalse(crossed_capture_radius((-30, 23), (30, 23), 22))
        # 双方相对位置完全重合且未移动，也应该判断为接触。
        self.assertTrue(crossed_capture_radius((0, 0), (0, 0), 22))

    # 两端都在圆外时仍返回首次进入比例，不能只检查终点或最近点时间。
    def test_capture_fraction_reports_first_contact_during_fast_crossing(self) -> None:
        # 从-30走到30需先走8像素才接触半径22的圆，因此首次比例是8/60。
        self.assertAlmostEqual(capture_contact_fraction((-30, 0), (30, 0), 22), 8 / 60)
        # 反向移动仍从靠近起点的一侧首次接触，而不是固定选择左侧圆周。
        self.assertAlmostEqual(capture_contact_fraction((30, 0), (-30, 0), 22), 8 / 60)
        # 3-4-5直角三角形给出圆上点(-4,3)，从(-10,3)走到(10,3)首次比例是6/20。
        self.assertAlmostEqual(capture_contact_fraction((-10, 3), (10, 3), 5), 0.3)
        # 同方向远离圆时，延长线上的交点不能成为本段事件。
        self.assertIsNone(capture_contact_fraction((30, 0), (40, 0), 22))

    # 擦到圆周也属于接触，圆外平行经过则没有事件。
    def test_capture_fraction_handles_tangency_and_near_miss(self) -> None:
        # 水平线在最高点相切，唯一接触发生在整段中间。
        self.assertAlmostEqual(capture_contact_fraction((-30, 22), (30, 22), 22), 0.5)
        # 终点恰好落在圆周上时，首次接触发生在当前段结束。
        self.assertEqual(capture_contact_fraction((-30, 0), (-22, 0), 22), 1)
        # 极长轨迹的细微偏移不能因大数平方抵消而被误判成相切。
        self.assertIsNone(capture_contact_fraction((-1e9, 1.1), (1e9, 1.1), 1))
        # 零半径仍允许轨迹经过原点，并给出明确的接触时间。
        self.assertAlmostEqual(capture_contact_fraction((-30, 0), (30, 0), 0), 0.5)

    # 已经在圆内立即接触，静止在圆外则始终没有接触。
    def test_capture_fraction_handles_inside_start_and_stationary_segment(self) -> None:
        # 起点在圆内，即使向外移动也不应返回稍后的离开时间。
        self.assertEqual(capture_contact_fraction((1, 2), (30, 0), 22), 0)
        # 起点恰在圆周上，向外移动仍首先发生边界接触。
        self.assertEqual(capture_contact_fraction((22, 0), (30, 0), 22), 0)
        # 完全静止且已重合时不进行除以零计算。
        self.assertEqual(capture_contact_fraction((0, 0), (0, 0), 0), 0)
        # 圆外没有位移时不能因零方向被误判为接触。
        self.assertIsNone(capture_contact_fraction((30, 0), (30, 0), 22))

    # 高速运动可以跨过整个出口，首次进入时间仍由门槛边界决定。
    def test_rectangle_fraction_detects_fast_crossing_and_reverse_direction(self) -> None:
        # 横向从0走到100，门区从40开始，所以先在四成处进入。
        self.assertAlmostEqual(rectangle_entry_fraction((0, 25), (100, 25), (40, 20, 60, 30)), 0.4)
        # 反向先遇到右边界60，首次比例同样是四成。
        self.assertAlmostEqual(rectangle_entry_fraction((100, 25), (0, 25), (40, 20, 60, 30)), 0.4)
        # 纵向首次接触上边界20，之后才沿出口区域继续移动。
        self.assertAlmostEqual(rectangle_entry_fraction((50, 0), (50, 100), (40, 20, 60, 30)), 0.2)
        # 斜线同时碰到出口左上角，四角也属于允许通过的边界。
        self.assertAlmostEqual(rectangle_entry_fraction((0, 0), (100, 100), (40, 40, 60, 60)), 0.4)

    # 含边界矩形允许沿边通过，也区分平行错过和完全静止。
    def test_rectangle_fraction_handles_parallel_boundary_and_stationary_cases(self) -> None:
        # 沿上边界移动仍会在左上角首次进入。
        self.assertAlmostEqual(rectangle_entry_fraction((0, 20), (100, 20), (40, 20, 60, 30)), 0.4)
        # 与出口平行但在上方，横坐标跨过门区仍不能判成功。
        self.assertIsNone(rectangle_entry_fraction((0, 19), (100, 19), (40, 20, 60, 30)))
        # 已在矩形内时，向外移动的首次事件发生在起点。
        self.assertEqual(rectangle_entry_fraction((50, 25), (100, 25), (40, 20, 60, 30)), 0)
        # 在矩形边界上保持静止也属于已进入的起点。
        self.assertEqual(rectangle_entry_fraction((40, 20), (40, 20), (40, 20, 60, 30)), 0)
        # 矩形外静止不会产生事件。
        self.assertIsNone(rectangle_entry_fraction((39, 20), (39, 20), (40, 20, 60, 30)))
        # 只在终点碰到角落时，首次进入比例必须保留为1。
        self.assertEqual(rectangle_entry_fraction((0, 0), (40, 20), (40, 20, 60, 30)), 1)

    # 两个轴必须在同一时间进入矩形，先后经过各自条带不能冒充真正过门。
    def test_rectangle_fraction_requires_overlapping_axis_intervals(self) -> None:
        # 横坐标在四到六成时位于门区，但纵坐标只在八到九成时位于门区。
        self.assertIsNone(rectangle_entry_fraction((0, 0), (100, 100), (40, 80, 60, 90)))
        # 门区完全位于运动终点之后，延长线相交不算当前段事件。
        self.assertIsNone(rectangle_entry_fraction((0, 25), (30, 25), (40, 20, 60, 30)))
        # 门区位于起点后方且角色向前走，也不应返回负数比例。
        self.assertIsNone(rectangle_entry_fraction((70, 25), (100, 25), (40, 20, 60, 30)))

    # 两种事件返回同一段时间的比例，模型可按大小稳定比较先过门还是先被抓。
    def test_first_event_fractions_preserve_capture_and_exit_order(self) -> None:
        # 圆半径10，相对运动从-30到30，首次接触在三分之一处。
        capture_fraction = capture_contact_fraction((-30, 0), (30, 0), 10)
        # 第一个门区从四分之一处开始，应早于同段捕获。
        early_exit_fraction = rectangle_entry_fraction((0, 5), (100, 5), (25, 0, 30, 10))
        # 第二个门区从一半处开始，应晚于同段捕获。
        late_exit_fraction = rectangle_entry_fraction((0, 5), (100, 5), (50, 0, 60, 10))
        # 用先后关系断言公开结果的业务用途，不在测试中另写求交算法。
        self.assertLess(early_exit_fraction, capture_fraction)
        # 较晚的门不能覆盖在此前已经发生的捕获事件。
        self.assertLess(capture_fraction, late_exit_fraction)
        # 同时发生的事件保留相同数值，最终平局策略由游戏模型决定。
        self.assertEqual(capture_contact_fraction((-30, 10), (30, 10), 10), late_exit_fraction)

    # 有限输入即使非常大或非常小，也不能因中间计算溢出而漏掉穿越。
    def test_fraction_queries_scale_extreme_finite_coordinates(self) -> None:
        # 相反极大端点的差会溢出，实际穿过小圆的时间仍约为一半。
        self.assertAlmostEqual(capture_contact_fraction((-1e308, 0), (1e308, 0), 22), 0.5)
        # 极小输入统一缩放后仍能区分进入点，而不是全部下溢到零。
        self.assertAlmostEqual(capture_contact_fraction((-3e-250, 0), (3e-250, 0), 1e-250), 1 / 3)
        # 过门查询也不能用无穷方向把跨过整张地图的时间误写为零。
        self.assertAlmostEqual(rectangle_entry_fraction((-1e308, 0), (1e308, 0), (-10, -10, 10, 10)), 0.5)

    # 结构、类型、有限性与非负半径在任何提前返回之前都必须校验。
    def test_capture_queries_reject_invalid_geometry(self) -> None:
        # 起点、终点和半径各自覆盖一个或多个实际错误边界。
        invalid_cases = (
            # 字符串不是二维几何点。
            ("00", (0, 0), 22),
            # 点坐标不能缺一个轴。
            ((0,), (0, 0), 22),
            # 布尔值不能作为坐标使用。
            ((False, 0), (0, 0), 22),
            # 即使起点已在圆内，也必须拒绝非法终点。
            ((0, 0), (float("nan"), 0), 22),
            # 无穷坐标不能进入运动比例计算。
            ((float("inf"), 0), (0, 0), 22),
            # 负半径没有几何含义。
            ((0, 0), (0, 0), -1),
            # 布尔开关不能冒充半径。
            ((0, 0), (0, 0), True),
            # 非有限半径不能把整个场景伪装成接触区域。
            ((0, 0), (0, 0), float("inf")),
        )
        # 新比例接口和旧布尔接口使用同一套边界，不能悄悄放宽旧契约。
        for query in (capture_contact_fraction, crossed_capture_radius):
            # 每种输入独立报告，避免某个早期错误遮住其他边界。
            for start, end, radius in invalid_cases:
                # 标记查询和输入，失败时便于定位具体的接口边界。
                with self.subTest(query=query.__name__, start=start, end=end, radius=radius):
                    # 几何无效必须明确失败，不能把错误输入解释成没有碰撞。
                    with self.assertRaises(ValueError):
                        # 直接调用正式接口，不在测试内复制校验逻辑。
                        query(start, end, radius)

    # 出口矩形必须有正宽高且所有几何输入合法，不因起点在里面就跳过校验。
    def test_rectangle_query_rejects_invalid_geometry(self) -> None:
        # 点和矩形分别覆盖错误维度、反向边界、布尔值和非有限输入。
        invalid_cases = (
            # 起点不能是任意字符串。
            ("00", (0, 0), (0, 0, 10, 10)),
            # 即使起点在门内，非法终点仍须被拒绝。
            ((0, 0), (float("nan"), 0), (0, 0, 10, 10)),
            # 布尔坐标不代表逻辑像素。
            ((0, 0), (True, 0), (0, 0, 10, 10)),
            # 矩形必须提供全部四条边界。
            ((0, 0), (0, 0), (0, 0, 10)),
            # 零宽区域不属于可通行的出口矩形。
            ((0, 0), (0, 0), (0, 0, 0, 10)),
            # 反向纵边界不能被自动交换后偷偷接受。
            ((0, 0), (0, 0), (0, 10, 10, 0)),
            # 无限边界不能作为有限地图区域。
            ((0, 0), (0, 0), (0, 0, float("inf"), 10)),
            # 布尔矩形边界同样违反数值契约。
            ((0, 0), (0, 0), (False, 0, 10, 10)),
        )
        # 每个非法组合都应通过公开接口明确抛出ValueError。
        for start, end, bounds in invalid_cases:
            # 为每种失败保留独立定位信息。
            with self.subTest(start=start, end=end, bounds=bounds):
                # 错误不能被无事件None掩盖。
                with self.assertRaises(ValueError):
                    # 使用实际过门查询进行契约验证。
                    rectangle_entry_fraction(start, end, bounds)

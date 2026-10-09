"""旧对话导入路径的兼容入口，正式实现位于 hero_game.model。"""

# 保留已有工具的 Dialogue 导入名称，不在根入口复制播放实现。
from hero_game.model.dialogue import Dialogue

# 公开兼容名称，避免把内部校验函数误当成根模块接口。
__all__ = ["Dialogue"]

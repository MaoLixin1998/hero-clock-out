"""应用层读取正式默认数据并组装纯游戏模型；显式注入时不访问文件。"""

# Mapping 表达调用者提供的只读配置，模型内部会取得独立数据副本。
from collections.abc import Mapping
# Any 只描述JSON字段边界，真实结构由模型校验。
from typing import Any

# 文件加载适配器只由应用组装层调用，不成为游戏模型的反向依赖。
from hero_game.config import load_game_dialogue, load_game_rules
# 纯模型只接收内存规则和正文，不负责寻找默认文件。
from hero_game.model.game import Game


# 保留原游戏构造的可选默认调用语义，明确在应用层加载缺失的正式数据。
# manifest 仅为兼容清单查询；None 表示缺失，合法空映射不会被默认值覆盖。
def create_game(
    # 资源清单可省略，缺省为空且模型不按其中路径读取媒体。
    manifest: Mapping[str, Any] | None = None,
    # 未提供规则时才读取包内正式game.json。
    rules: Mapping[str, Any] | None = None,
    # 未提供对白时才读取包内正式dialogue.json。
    dialogue_data: Mapping[str, Any] | None = None,
    # 首次运行默认播放正式开场，重试可明确跳过。
    play_intro: bool = True,
) -> Game:
    # 先拒绝非法清单，避免错误调用仍触发不必要的默认文件读取。
    if manifest is not None and not isinstance(manifest, Mapping):
        # 与纯模型保持同一清单类型契约，不隐式接收键值序列。
        raise TypeError("Game manifest must be a mapping")
    # 只有真正未提供规则时读文件，空规则应交给模型明确校验失败。
    actual_rules = load_game_rules() if rules is None else rules
    # 对白和运动参数分别注入，一项已提供时不会重复读取它的默认文件。
    actual_dialogue = load_game_dialogue() if dialogue_data is None else dialogue_data
    # 应用完成依赖组装，后续游戏更新不再涉及任何配置文件读取。
    return Game(
        # 校验和深拷贝由纯模型入口完成。
        rules=actual_rules,
        # 正文播放器取得独立数据，不与调用方共享可变台词。
        dialogue_data=actual_dialogue,
        # 兼容清单只保存内存描述，不改变资源加载职责。
        manifest=manifest,
        # 开场选择直接传入，不通过台词或显示文字反推状态。
        play_intro=play_intro,
    )

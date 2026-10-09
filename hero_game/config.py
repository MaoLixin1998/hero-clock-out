"""读取随安装包发布的正式游戏配置，不访问本机视频制作目录。"""

# JSON 仅作为数据解析，不执行配置中的任何文字。
import json
# 配置根目录由当前模块位置确定，与终端工作目录无关。
from pathlib import Path
# 文字模板只允许秒数占位，提前拒绝渲染时才会失败的格式。
from string import Formatter
# Mapping 允许调用方提供只读映射，Any 表示尚未校验的 JSON 值。
from typing import Any, Mapping

# 规则契约属于纯模型；此处保留既有公开名称，让旧配置调用者继续读取。
from hero_game.model.rules import (
    # 固定逻辑尺寸同时供加载适配器和绘制层查询。
    LOGICAL_SIZE,
    # 最小反应周期保持与模型时间切片边界一致。
    MIN_RETARGET_SECONDS,
    # 必须为正的规则字段保持原校验接口。
    POSITIVE_FIELDS,
    # 坐标字段维度由纯游戏契约统一定义。
    VECTOR_LENGTHS,
    # 校验函数不读文件，加载适配器在解析之后显式调用它。
    validate_game_rules,
)

# 正式配置随 Python 包分发，是运行参数与游戏文字的唯一默认来源。
DATA_ROOT = Path(__file__).resolve().parent / "data"
# 界面文字的稳定字段与显示内容分开，缺失或拼错字段不能推迟到绘制时才失败。
PRESENTATION_FIELDS = frozenset({"windowTitle", "caughtTitle", "caughtInstruction", "pausedTitle", "pausedInstruction",
                                # 英文备用字段保证缺少中文系统字体时也有完整操作提示。
                                "caughtTitleEnglish", "caughtInstructionEnglish", "pausedTitleEnglish", "pausedInstructionEnglish",
                                # 门的实时指引属于正式界面配置，结局不叠加文字。
                                "doorCountdown", "doorOpenInstruction",
                                # 开门指引也提供完整英文备用文字。
                                "doorCountdownEnglish", "doorOpenInstructionEnglish"})


# 读取包内指定 JSON 对象；坏文件明确失败，不回退到本机私人副本。
def load_data_object(name: str) -> dict[str, Any]:
    # 固定允许的配置名阻止调用者通过路径访问包外文件。
    if name not in {"game", "dialogue", "presentation"}:
        # 未登记的数据不是默认运行配置。
        raise ValueError("Unknown game data name")
    # UTF-8 和 JSON 解析错误保留原始原因供入口报告。
    result = json.loads((DATA_ROOT / f"{name}.json").read_text(encoding="utf-8"))
    # 顶层必须是映射，列表或空值不能作为配置。
    if not isinstance(result, dict):
        # 错误信息只标识正式文件，不输出台词正文。
        raise ValueError(f"Game data {name} must contain an object")
    # 新解析的对象由调用方独立拥有。
    return result


# 创建默认运行规则，调用时读取包内文件，不在模块导入时读取。
def load_game_rules() -> dict[str, Any]:
    # 所有实例都通过同一入口验证正式规则。
    return validate_game_rules(load_data_object("game"))


# 读取正式游戏对白；播放器负责进一步检查角色和场景契约。
def load_game_dialogue() -> dict[str, Any]:
    # 游戏台词可以随游戏分发，不依赖视频脚本。
    return load_data_object("dialogue")


# 校验并复制全部界面字符串字段；包内文件和显式注入都使用同一边界。
# 合法空字符串原样保留，错误类型、缺失和未知字段抛ValueError。
def validate_game_presentation(settings: Mapping[str, Any]) -> dict[str, str]:
    # 非映射不能被隐式转换成显示配置，避免界面持有含糊结构。
    if not isinstance(settings, Mapping):
        # 在窗口构造前报告输入结构问题。
        raise ValueError("Presentation settings must be an object")
    # 字符串不可变，因此独立外层字典足以分离显示配置所有权。
    actual = dict(settings)
    # 所有显示字段都须是字符串。
    if any(not isinstance(value, str) for value in actual.values()):
        # 不对数字或空值做隐式字符串转换。
        raise ValueError("Presentation values must be strings")
    # 缺失和拼错字段均明确失败。
    if set(actual) != PRESENTATION_FIELDS:
        # 不向本机视频目录寻找补丁文件。
        raise ValueError("Presentation fields do not match the game interface")
    # 中英倒计时模板使用同一秒数变量，空字符串仍可明确关闭该文字。
    for name in ("doorCountdown", "doorCountdownEnglish"):
        # 合法空字符串原样保留，不强制调用方显示提示。
        if not actual[name]:
            # 没有模板内容就无需检查占位符。
            continue
        # 格式语法错误也要在窗口构造之前报告。
        try:
            # 解析占位符，不执行配置中的任何代码或属性访问。
            fields = [(field, spec, conversion) for _, field, spec, conversion in Formatter().parse(actual[name])
                      # 纯文字片段没有变量，无须加入占位符契约。
                      if field is not None]
        # 不完整花括号属于显示配置错误，而不是运行时绘制错误。
        except ValueError as error:
            # 保留解析原因，帮助定位错误配置字段。
            raise ValueError(f"Presentation countdown template is invalid: {name}") from error
        # 恰好一个简单 seconds 变量即可完成倒计时，不接受属性、转换或格式表达式。
        if fields != [("seconds", "", None)]:
            # 在默认读取和显式注入两条路径上执行相同模板检查。
            raise ValueError(f"Presentation countdown template requires one seconds field: {name}")
    # 返回刚读取且独立的字符串映射。
    return actual


# 读取包内正式界面文字，不访问本机视频文案或制作目录。
def load_game_presentation() -> dict[str, str]:
    # 默认文件和外部注入遵守完全相同的字段与类型契约。
    return validate_game_presentation(load_data_object("presentation"))

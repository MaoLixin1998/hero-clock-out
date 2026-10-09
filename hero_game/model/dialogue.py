"""配置驱动的游戏对话播放器；不管理角色位移或任何拍摄流程。"""

# Mapping 表达对话配置的只读输入契约。
from collections.abc import Mapping
# 深拷贝让每个播放器独立持有台词与角色配置。
from copy import deepcopy
# Any 仅描述 JSON 边界，各字段仍进行真实类型校验。
from typing import Any

# 共享数值检查拒绝 NaN、无穷和布尔数值。
from hero_game.model.numeric import finite_number


# 校验并复制对话配置；intro/caught 是正式事件场景，其他命名列表可扩展场景。
# 稳定角色 ID 必须存在，所有正文与显示字段须为字符串，错误抛 ValueError。
def validate_dialogue_data(data: Mapping[str, Any]) -> dict[str, Any]:
    # 顶层必须是字段映射，不能把列表或空值当成对话数据。
    if not isinstance(data, Mapping):
        # 在读取字段前报告结构错误，避免含糊的后续索引异常。
        raise ValueError("Dialogue data must be an object")
    # 复制嵌套数据，不与调用方或其他播放器共享可变列表。
    settings = deepcopy(dict(data))
    # 逐字速率采用有限的每秒字符数，布尔值不是合法速度。
    characters_per_second = finite_number(settings.get("charactersPerSecond"), "charactersPerSecond")
    # 零或负速率会让显示和确认逻辑失效，因此提前拒绝。
    if characters_per_second <= 0:
        # 不用默认速率掩盖配置错误。
        raise ValueError("charactersPerSecond must be positive")
    # 保存经过转换的实际数值，播放时不重新解析输入。
    settings["charactersPerSecond"] = characters_per_second
    # 角色映射为每句提供姓名与立绘信息，身份使用稳定 ID。
    speakers = settings.get("speakers")
    # 只接受对象形式的角色配置，不从列表位置猜测身份。
    if not isinstance(speakers, Mapping):
        # 在模型边界指出错误，避免拖到绘制时才失败。
        raise ValueError("Dialogue speakers must be an object")
    # 逐个核对角色 ID 与绘制层需要的字段。
    for speaker_id, speaker_spec in speakers.items():
        # 稳定 ID 必须是非空字符串，不能用显示姓名或空值代替。
        if not isinstance(speaker_id, str) or not speaker_id:
            # 配置错误不自动生成另一个 ID。
            raise ValueError("Speaker IDs must be nonempty strings")
        # 每个角色提供字段映射，而不是一段裸文字。
        if not isinstance(speaker_spec, Mapping):
            # 错误信息只描述结构，不输出创作正文。
            raise ValueError("Speaker settings must be objects")
        # 姓名与立绘路径都是数据，本模型不读取图像文件。
        for field_name in ("name", "nameEnglish", "portrait"):
            # 空字符串保持原样，但缺失或非字符串不满足接口。
            if not isinstance(speaker_spec.get(field_name), str):
                # 字段名帮助定位配置，正文不复制进日志。
                raise ValueError(f"Speaker {field_name} must be a string")
    # 两种正式事件场景必须存在，空列表则是合法的无对白配置。
    for required_scene in ("intro", "caught"):
        # 缺失与空内容分开处理，不擅自播放另一段台词。
        if required_scene not in settings:
            # 明确报告缺少的稳定场景 ID。
            raise ValueError(f"Missing dialogue scene: {required_scene}")
    # 元数据以外的顶层字段都作为有序场景列表处理。
    for scene_name, lines in settings.items():
        # 速率与角色信息不是可播放场景。
        if scene_name in ("charactersPerSecond", "speakers"):
            # 当前项已经检查，继续处理其他场景。
            continue
        # 每个场景必须拥有非空字符串 ID 和列表内容。
        if not isinstance(scene_name, str) or not scene_name or not isinstance(lines, list):
            # 错误内容不能悄悄转换为空对白。
            raise ValueError("Dialogue scenes must be named lists")
        # 按原顺序校验台词，不在模型中拼接或写死具体句子。
        for line in lines:
            # 每句必须是明确记录说话者和正文的字段映射。
            if not isinstance(line, Mapping):
                # 拒绝混入的数字或裸字符串。
                raise ValueError("Dialogue lines must be objects")
            # 先取角色 ID，再检查其类型和注册状态。
            speaker_id = line.get("speaker")
            # 先校验字符串能避免不可哈希输入触发无关异常。
            if not isinstance(speaker_id, str) or speaker_id not in speakers:
                # 姓名和立绘缺失要在播放前明确报告。
                raise ValueError("Dialogue line references an unknown speaker")
            # 中英文都来自正式数据，播放器只选择语言字段。
            for field_name in ("text", "english"):
                # 空正文可表达留白，其他类型不是合法文字。
                if not isinstance(line.get(field_name), str):
                    # 提示错误字段，不输出台词原文。
                    raise ValueError(f"Dialogue line {field_name} must be a string")
    # 返回当前播放器独占的合法配置。
    return settings


# 独占当前段落、台词索引和逐字秒数；不读磁盘、不控制角色、不调用 AI。
# Game 负责创建和推进，界面只通过独立快照读取角色与台词。
class Dialogue:
    # 校验传入的对话数据，建立尚未启动任何段落的状态。
    def __init__(self, data: Mapping[str, Any]) -> None:
        # 每个实例独立持有配置，外部修改原数据不会影响播放。
        self._data = validate_dialogue_data(data)
        # 初始没有活动场景，空列表与已结束段落都可安全查询。
        self._lines: list[dict[str, Any]] = []
        # 当前句索引从零开始，达到列表长度时表示结束。
        self._index = 0
        # 当前句的显示时间只由播放方法修改，单位为秒。
        self._seconds = 0.0

    # 查询独立的完整配置快照，不把嵌套台词交给界面修改。
    # 属性查询不触发加载、计时或任何角色操作。
    @property
    def data(self) -> dict[str, Any]:
        # 深拷贝阻止浅层副本中的子列表泄露内部状态。
        return deepcopy(self._data)

    # 查询当前段落的独立列表快照，保持旧工具的读取接口。
    # 调用方不能通过修改返回值改变实际播放顺序。
    @property
    def lines(self) -> list[dict[str, Any]]:
        # 台词字段和嵌套对象均与内部播放数据分离。
        return deepcopy(self._lines)

    # 查询零起始的当前句索引，修改进度应调用 advance 或 skip。
    # 只读查询不会偷偷推进到下一句。
    @property
    def index(self) -> int:
        # 返回不可变的索引数值。
        return self._index

    # 查询当前句已经显示的秒数，外部补全使用 reveal 方法。
    # 时间状态由本对象独占，避免导出工具写入任意魔法数。
    @property
    def seconds(self) -> float:
        # 暂停时 Game 不再调用 update，因此数值保持不变。
        return self._seconds

    # 查询列表中是否仍有当前句，不另存容易失步的活动开关。
    # 空段落和已跳过段落都返回 False。
    @property
    def active(self) -> bool:
        # 只有索引处于列表范围内才允许读取正文。
        return self._index < len(self._lines)

    # 查询当前句独立快照；无活动台词时返回 None，而非报越界错误。
    # 渲染器修改结果不会改写播放原稿。
    @property
    def current(self) -> dict[str, Any] | None:
        # 先检查活动状态，结束场景后不访问失效索引。
        if not self.active:
            # 无当前句是合法状态，与错误配置分别处理。
            return None
        # 仅复制当前句，避免每帧复制整段正文。
        return deepcopy(self._lines[self._index])

    # 按稳定场景 ID 开始播放，未知 ID 抛 ValueError 并保持原场景。
    def start(self, scene: str) -> None:
        # 元数据字段不能当成场景，ID 也必须存在于合法配置中。
        if not isinstance(scene, str) or scene in ("charactersPerSecond", "speakers") or scene not in self._data:
            # 失败时不部分修改索引或显示秒数。
            raise ValueError("Unknown dialogue scene")
        # 新段落持有独立列表，不与外部配置或旧场景共享可变正文。
        self._lines = deepcopy(self._data[scene])
        # 从第一句开始，不沿用前一个场景的索引。
        self._index = 0
        # 首帧显示空文字，再按正常速度逐渐出现。
        self._seconds = 0.0

    # 查询完整正文；english 选择英文备用字段，无当前句返回空字符串。
    def text(self, english: bool = False) -> str:
        # 空场景绘制空文字，不应当成加载失败。
        if not self.active:
            # 文字接口统一返回字符串，界面无需反复处理 None。
            return ""
        # 读取已经校验的正文，查询不改原文或播放时间。
        return self._lines[self._index]["english" if english else "text"]

    # 按累计秒数裁出已经出现的字符，不修改完整正文。
    def visible_text(self, english: bool = False) -> str:
        # 当前正文长度是显示字符数量的自然上限。
        full_text = self.text(english)
        # 先限制到实际字数，长时间更新也不构造无意义的巨大整数。
        visible_count = int(min(len(full_text), self._seconds * self._data["charactersPerSecond"]))
        # 切片保留正文中的换行，尚未出现的部分只在绘制时隐藏。
        return full_text[:visible_count]

    # 推进逐字计时；负值保持兼容行为夹到零，非有限秒数抛 ValueError。
    def update(self, dt: float) -> None:
        # 无活动台词也先校验接口输入，不让错误时间被静默忽略。
        duration_seconds = finite_number(dt, "dt")
        # 只在当前场景仍活动时累计时间。
        if self.active:
            # 负值不倒放文字，也不改变已经出现的字符。
            self._seconds += max(0.0, duration_seconds)

    # 立即补全当前句但不推进索引，供确认操作和导出工具明确调用。
    def reveal(self, english: bool = False) -> None:
        # 没有当前句时补全操作保持无副作用。
        if not self.active:
            # 不为不存在的句子制造显示时长。
            return
        # 字数除速率得到完整时长，微小余量吸收浮点舍入。
        self._seconds = len(self.text(english)) / self._data["charactersPerSecond"] + 0.001

    # 第一次确认补全当前句，已完整时再次确认才切到下一句。
    def advance(self, english: bool = False) -> None:
        # 场景结束后反复确认不能访问越界正文。
        if not self.active:
            # 保持结束状态，等待 Game 显式启动另一段。
            return
        # 每种语言按其真实字符数计算显示时长。
        duration_seconds = len(self.text(english)) / self._data["charactersPerSecond"]
        # 尚未完整时只补全，避免跳过玩家还没看完的内容。
        if self._seconds < duration_seconds:
            # 复用补全方法，不重复写入时间余量规则。
            self.reveal(english)
        # 当前句完整后，再次确认才进入下一句。
        else:
            # 超过最后一句时 active 自然变为 False。
            self._index += 1
            # 下一句重新从空文字开始显示。
            self._seconds = 0.0

    # 跳过整段文字；游戏失败与重开状态仍由 Game 单独管理。
    def skip(self) -> None:
        # 放到列表末尾，重复调用也保持同样的合法结束状态。
        self._index = len(self._lines)

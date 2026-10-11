# 项目开发协作入口

开发前实际读取 [通用开发规范1.7](support/standards/general-coding-standard.md)和 [Python / pygame补充1.5](support/standards/python-pygame.md)。项目副本只提供技术规则，不自动改写本机全局设置；已有本机权威正文时核对版本与内容。

首次接手并准备编码、新增模块或改变职责与依赖边界时，按R02先在对话展示分层图、模块结构树、公开接口和状态归属，再实施。当前结构见 [技术架构](support/technical/architecture.md)。结构不变的局部修复可引用已展示的有效图；结构展示本身不增加审批。

每次开发按R03围绕一个明确功能或职责组织可独立审阅的变更，先说明目标、必要文件及验证。大需求按依赖拆成连续批次，不夹带无关功能、批量格式化、重命名、搬迁或顺手重构；必要的接口、测试、配置、文档与允许清单仍须同步。范围扩大前说明原因，已有完整实施授权不因拆批逐次审批。

## 代码职责

- `main.py`是源码入口；正式包为`hero_game`，安装入口`hero-clock-out`，模块入口`python -m hero_game`。
- `hero_game/model/`只处理规则与状态，不依赖pygame、文件读取、窗口或外部素材。`app/`组装依赖、处理输入与生命周期；`rendering/`读取公开状态与已加载资源进行绘制。
- `Game`拥有一局流程，组合角色、开场、对白、闪身与结局组件；各组件独占自己的状态。跨模块通过公开能力协作，不穿透私有字段，不引入万能公共模块或循环依赖。
- `hero_game/data/`是正式规则、对白与显示配置的唯一默认来源。资源根由入口显式传入，普通导入不启动设备或产生文件，退出在finally中清理SDL资源。
- 一个类一个文件；函数、类及逻辑代码的有意义中文说明写在正上方。新增或移动模块同步核对导入、资源定位、测试、打包、文档和Git允许范围。

## 技术辅助与内容边界

- `support/`是辅助内容的组织容器；正式测试、工具、规范、技术文档分别位于`tests/`、`tools/`、`standards/`、`technical/`。运行包不依赖辅助目录。
- 经正文审阅的源码、测试、依赖与构建配置、纯技术规则和正式游戏数据可进入Git。通用规范副本与权威正文保持一致，项目差异只写在项目补充中。
- `support/production/`、`support/tests/local_video/`、私人资源、本机混合协作规则和生成产物排除Git与发行；默认测试不发现本机场景。辅助目录不能整体暂存或递归打包。
- 默认入口使用程序生成的完整基础图形与提示音，不依赖私人素材。外部美术通过`--assets PATH`显式加载，其使用和分发权需单独核验。
- 任何混合文档保留本机原稿，技术结论另行提取。发现受限内容已跟踪时保留本机并移出索引；发现历史含受限内容时停止推送并报告，不擅自改写历史。
- 暂存、提交、推送前核对正文、实际索引与拟推送历史，不强制添加或跳过检查。具体Git写操作按用户当次授权执行。

## 检查与构建

```sh
python -m support.tools.check_project
python -m support.tools.check_project --staged
python -m support.tools.check_project --check-package --build-python /path/to/build-python
python -m support.tools.check_git_scope --staged --history
python -m support.tools.export_game
```

工作区模式运行受控回归；索引模式只读取实际blob，不执行索引代码。干净包验收检查源码、wheel离线安装、console与模块启动；构建解释器需预装setuptools>=70。注释语义、职责、状态所有权、正文用途及许可仍需人工审阅。区分工作区、索引、安装包与实际GUI的结果，不把本机虚拟显示检查写成远程CI或听感通过。

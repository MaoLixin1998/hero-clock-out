# 项目开发协作入口

本机开发先读取 `~/.codex/standards/general-coding-standard.md`（通用规范1.6），本机副本位于 `support/standards/general-coding-standard.md`；两者正文一致且不进入Git或发行物。其他电脑需单独配置通用规范。项目专用约定见 [Python / pygame补充1.3](support/standards/python-pygame.md)，不由仓库自动改写全局设置。

首次接手并准备编码，或新增模块、跨包能力、改变职责与依赖边界时，先按R02在对话展示分层图、包或模块结构树、公开接口与状态边界，再实施；不能只写本机文档或先写实现后补图。当前结构参考 [技术架构](support/technical/architecture.md) 和项目补充第2节；已有有效展示且结构不变的局部修改可引用原图并指出落点，明确授权后不增加重复审批。

## 范围与依赖

- `main.py` 是源码工作区启动器；正式包为 `hero_game`，安装入口 `hero-clock-out`，也支持 `python -m hero_game`。
- `hero_game/model/` 只处理规则与状态，不依赖pygame、窗口、录制或视频文件；`rendering/`读取资源与状态，`app/`负责输入、依赖组装和生命周期。
- 按通用G04，实际目录、公开边界及依赖方向见项目补充第2节；跨模块通过公开能力协作，不穿透私有状态，不用万能公共模块或延迟导入掩盖循环依赖。新增或移动模块同步核对导入、资源路径、测试发现、打包范围和Git允许集合。
- 正式规则、游戏对白与显示文字唯一默认来源为 `hero_game/data/`。它们是游戏运行数据，可随仓库发布；不得从视频剧本反向覆盖正式数据。
- 每个类独立文件；新增或修改代码按通用规范使用有实际含义的中文上方说明、清晰英文命名、类型、输入校验和明确状态所有权。
- 普通导入不启动设备、读取制作目录或产生文件；应用退出在finally中清理显示、字体和声音。

## 视频拍摄与文档边界

- 为视频拍摄编写的代码不得侵入主体代码。优先放入独立、本机保留的测试场景，通过注入、测试替身或组合复用主体能力；不能在主体中散布拍摄分支、修改正式实现或使主体反向依赖拍摄目录。
- `support/`集中项目辅助内容，内部按测试、工具、规范、技术文档及本机制作资料分区；它是组织容器，游戏运行包不依赖它，不能整体放行Git或发行。
- 本项目本机场景位于 `support/tests/local_video/`，没有包入口，不参与默认unittest发现、CI、Git和发行包；保留在测试区是为了显式测试驱动主体，属于本机资料集中规则的路径例外。
- `support/technical/`及项目专用补充是可审阅发布的技术内容；通用规范正文仅本机。视频文档、素材、旧配置和备份集中在 `support/production/`，全部排除Git。公开技术入口为 `TECHNICAL.md`。
- 如本机任务涉及视频制作，继续读取 `support/production/collaboration/AGENTS.video.md`；该本机记录可能不存在于干净代码副本，正式开发和运行不依赖它。它不属于产品需求或发布授权。
- 入镜开发对话须与制作指导分开：开录前交接实现范围与规则；入镜回复、代码说明及主动输出只围绕人物需求、游戏逻辑、真实改动和运行结果，不复述拍摄、分镜、素材编号、OBS或剪辑安排。具体执行见上述本机制作入口“入镜开发对话约束”。此要求不改变独立本机场景、Git和真实实现边界；不能靠伪造开发过程满足画面。

## Git与发行

- Git仅保留已审阅的源码、测试、依赖/构建配置、纯技术文档及正式游戏数据；视频方案、草稿、拍摄代码、头像、第三方配乐、录屏、素材提示词和来源记录留本机。
- 本机美术位于 `support/production/game_assets/`，通过 `--assets PATH`显式加载。所有正式入口默认提供程序绘制的基础画面与提示音，缺少整个辅助目录仍能运行安装后的游戏。
- 同步维护 `.gitignore`与 `support/tools/check_git_scope.py`允许范围。暂存、提交、推送前核对实际索引与拟推送历史，不强制添加或跳过检查。
- 原文件备份位于 `support/production/local_git_archive/`，旧根配置只在制作区归档，不是正式数据来源。忽略文件不删除本机原稿；内部Codex树快照不等于分支commit，不自行删除引用或改写历史。
- 当前任务授权重构、验证及更新技术暂存区，未授权commit、push或上传。后续操作按用户实际授权执行。

## 检查与构建入口

```sh
.venv/bin/python -m support.tools.check_project
.venv/bin/python -m support.tools.check_project --staged
.venv/bin/python -m support.tools.check_project --check-package --build-python /path/to/build-python
.venv/bin/python -m support.tools.export_game
```

工作区检查运行受控回归；索引模式只解析实际blob，不执行索引代码。包验收从干净快照验证源码运行、wheel离线安装和console启动，构建解释器需预装setuptools>=70。注释含义、职责、可变状态所有权、正文用途与资源许可仍需人工审阅。GUI与实际听感另行验证，不把虚拟显示或工作区通过写成远程CI通过。

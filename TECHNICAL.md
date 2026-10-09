# 游戏技术入口

这是可独立安装、运行与打包的Python / pygame小游戏。正式代码与游戏数据保存在`hero_game/`；代码仓库使用程序绘制的基础图形和生成提示音，不依赖本机制作目录或私人素材。

## 开发规则

- 本机开发先读取`~/.codex/standards/general-coding-standard.md`（通用规范1.6）或同版本本机副本；正文仅本机配置，不随Git或发行物分发。项目约定见[Python / pygame补充1.3](support/standards/python-pygame.md)及[项目协作入口](AGENTS.md)。
- 首次实现、接手项目或改变结构前，按R02在对话展示分层图、包结构树与边界；当前结构见[架构与边界](support/technical/architecture.md)，结构不变的局部修改可引用有效图。
- 一个类一个文件，中文说明写在定义与逻辑代码正上方；模型、资源、绘图、输入与生命周期按职责分离。
- 正式游戏剧情与界面文字是包内数据，可随游戏提交；视频拍摄代码优先使用独立本机测试场景，不侵入主体、不参与默认测试、Git与发行。
- 项目辅助内容统一在`support/`内分类。可发布技术文档在`support/technical/`，项目专用补充为`support/standards/python-pygame.md`；通用规范本机副本在`support/standards/general-coding-standard.md`并排除Git。混合旧稿、视频文档、素材及旧配置集中于`support/production/`，全部保留本机。

## 安装与启动

需要Python3.10+。依赖为pygame-ce2.5.8、Pillow12.3.0，与`pyproject.toml`一致。

```sh
python -m pip install .
hero-clock-out
python -m hero_game
python main.py
```

源码、模块及安装入口默认使用完整基础画面。外部美术可通过`--assets PATH`显式提供，媒体不因被程序使用而自动进入Git。

WASD/方向键移动，空格/Esc暂停或恢复，对话中回车/空格补全与推进，Tab/Esc跳过，被抓或下班成功后R重开，Q退出。

默认从17:29开始，累计60秒有效游戏时间后到17:30，右上方的门开放。钟面下方显示剩余秒数；门前绿色门槛是实际可达的出口，开门后走入即可下班。开场、对白、暂停和胜负终态冻结计时；起跑保护期间玩家可动，时间正常推进。失败或成功后重开会恢复17:29和关闭的门。

正式规则位于`hero_game/data/game.json`：`clockText`为开始钟面，`shiftEndText`为下班钟面，`gameSecondsPerMinute`为一个游戏分钟对应的有效秒数，`exitBounds`为脚底可进入的左、上、右、下边界。时间可跨午夜；钟面到下班时封顶，门保持开放直到结果或重开。碰撞与进入门槛按一段移动中首次发生的时间比较，同刻被抓优先。

## 检查与打包

```sh
python -m support.tools.check_project
python -m support.tools.check_project --staged
python -m support.tools.check_project --check-package --build-python /path/to/build-python
python -m support.tools.export_game
python -m support.tools.export_game --wheel --build-python /path/to/build-python
```

构建解释器需预装setuptools>=70；默认产物位于`support/tools/output/`，不进入Git。源码ZIP和wheel仅使用正式白名单快照。干净包验收在临时目录运行源码，离线安装wheel并启动实际console和模块入口，不借用本机资源或视频测试代码。wheel需要Python及声明依赖，不是包含解释器的原生应用。

工作区模式运行回归；索引模式只读取实际blob进行规范和范围检查，不执行索引代码。自动项不替代注释含义、职责、配置所有权和正文用途的人工审阅；无显示检查不等于真实GUI或听感验收。

详见[架构与边界](support/technical/architecture.md)、[运行发行与验证](support/technical/packaging.md)。原代码与制作记录备份留在本机，重构不代表已提交、推送或上传。

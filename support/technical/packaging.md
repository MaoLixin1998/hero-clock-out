# 运行、发行与验证

需要Python3.10或更新版本，运行依赖见根`requirements.txt`与`pyproject.toml`：pygame-ce2.5.8、Pillow12.3.0。安装依赖需要相应安装源或本地缓存；离线验收复用已安装依赖，不代表发行物内含Python解释器或第三方库。

```sh
python -m pip install .
hero-clock-out
python -m hero_game
python main.py
```

WASD/方向键移动；E闪身，随后原地喘息两次，期间敌人继续追击；空格或Esc暂停/恢复；对话中回车/空格补全和推进，Tab/Esc跳过；被抓后R重开，Q退出。到17:30后走向右下方出口，自动跨门，在门外向右走出画面并由夕阳过渡到夜晚；结局无文字，R重开、Q退出仍可用。其他界面没有中文系统字体时显示英文备用文字。所有入口默认采用内置基础资源，`--assets PATH`可显式指定外部游戏美术。

## 产物

```sh
python -m support.tools.export_game
python -m support.tools.export_game --wheel --build-python /path/to/build-python
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir support/tools/output
```

默认产物集中在`support/tools/output/`并排除Git。源码ZIP由正式白名单快照生成，保留源码、正式数据、检查与技术文档；解压后安装依赖即可运行`python main.py`。wheel提供可安装包、三份正式JSON及console入口。构建后端为setuptools>=70；需要使用已安装该后端的解释器，常规pip构建隔离可能安装构建依赖。

两种产物均排除本机混合规则、视频测试场景、制作文档、原混合README、本机配置、旧美术目录、个人头像、配乐和录屏。源码ZIP可包含已审通用规范与项目补充；wheel只分发运行包与正式数据，不带辅助目录。源码打包与wheel构建在临时目录中完成，校验成功后原子替换目标，失败保留旧产物；不把整个工作区递归压缩。wheel是Python安装包，尚未提供包含解释器的原生.app或Windows可执行程序。

## 检查范围

```sh
python -m support.tools.check_project
python -m support.tools.check_project --staged
python -m support.tools.check_project --check-package --build-python /path/to/build-python
python -m support.tools.check_git_scope --staged --history
```

默认检查工作区Python语法、UTF-8、末尾换行、注释位置、单类文件、名称形式、正式文件范围和回归测试。索引模式读取真实索引blob，拒绝冲突与非普通文件；它不执行待提交源码、测试或构建。正文用途、注释准确性、职责、许可和隐私仍需人工审阅。

包验收从白名单生成干净快照，在无本机素材与制作目录的临时目录启动源码；再构建wheel，使用`--no-index --no-deps`离线安装到全新目录，运行实际console和`python -m hero_game`模块入口。无显示启动命令为`--headless --frames 3 --silent`，实际执行绘制和清理流程。每次报告区分工作区、索引、安装包和真实GUI，不把虚拟驱动或自动测试等同于人工画面与听感验收。

正式Git数据是`hero_game/data/{game,dialogue,presentation}.json`。旧根配置已归档至`support/production/legacy_config/`，不继续作为配置来源。可发布纯技术文档位于`support/technical/`、项目专用补充`support/standards/python-pygame.md`及根技术入口；已审阅的`support/standards/general-coding-standard.md`随技术源码提供，与权威版本1.7保持一致；它不是运行依赖，缺少它不影响游戏启动。视频与制作文档集中在`support/production/`。新增技术文件仍要审阅正文并同步允许清单，不因为后缀为.py、.json或.md而自动准许上传。

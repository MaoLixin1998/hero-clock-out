# Hero Clock Out

一个Python / pygame二维追逐小游戏：勇者等待下班，避开史莱姆，使用E闪身，直到17:30门开放后离开办公室。

## 运行

需要Python 3.10或更新版本。

```sh
python -m pip install .
hero-clock-out
```

也可使用 `python -m hero_game`；源码工作区入口为 `python main.py`。

WASD或方向键移动，E闪身，之后原地喘息两次再继续移动；空格或Esc暂停；对白中回车或空格推进、Tab跳过；R重开，Q退出。有效游戏时间累计60秒后门开放，出口在办公室右下方。成功后自动跨门并进入日夜过渡的门外结局。

默认图形和提示音由程序生成，完整游戏不需要外部美术、录屏或本机目录。`--assets PATH`可显式加载兼容的外部资源包；外部素材不随此仓库提供。

## 开发与验证

```sh
python -m support.tools.check_project
python -m support.tools.check_project --staged
python -m support.tools.check_project --check-package --build-python /path/to/build-python
```

构建解释器需预装setuptools>=70。正式源码按 `app/`、`model/`、`rendering/`与 `data/`分离，测试、工具、技术规范和文档集中在 `support/`的对应子目录。Python包不反向依赖辅助目录。

详细安装、架构、数据边界与打包说明见 [技术入口](TECHNICAL.md)、[架构](support/technical/architecture.md)、[发行与验证](support/technical/packaging.md)。开发前读取 [项目规则](AGENTS.md)、[通用规范1.6.1](support/standards/general-coding-standard.md)及 [Python / pygame补充](support/standards/python-pygame.md)。

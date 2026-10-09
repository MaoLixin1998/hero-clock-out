"""支持python -m hero_game运行已安装的游戏。"""

# 启动状态通过终端退出码返回。
import sys

# 正式入口不依赖源码工作区。
from hero_game.app.cli import main


# 普通导入不启动游戏。
if __name__ == "__main__":
    # 模块启动使用包内基础资源。
    sys.exit(main())

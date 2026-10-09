"""源码工作区启动器；正式安装入口为hero-clock-out。"""

# 启动状态交给终端。
import sys

# 游戏逻辑位于独立包，入口只负责组装。
from hero_game.app.cli import main


# 导入启动器不启动窗口。
if __name__ == "__main__":
    # 统一使用正式命令行入口，外部美术只由用户通过--assets显式提供。
    sys.exit(main())

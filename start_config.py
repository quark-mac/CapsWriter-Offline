# coding: utf-8
"""
CapsWriter 设置窗口独立入口

用法：
    python start_config.py

无需启动服务端 / 客户端，即可独立编辑配置与开机自启动。
仅依赖 Python 标准库，无需安装 rich 等第三方依赖。
"""

import os
import sys

# 确保项目根目录在模块搜索路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from settings.gui import main

if __name__ == "__main__":
    main()

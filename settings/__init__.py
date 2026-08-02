# coding: utf-8
"""
CapsWriter 设置工具包（仅依赖 Python 标准库，可独立运行 / 打包为 exe）

- config_editor: 配置文件的 AST 读写
- autostart:     注册表开机自启动
- gui:           设置窗口
"""

import sys
from pathlib import Path


def get_base_dir():
    """
    返回项目根目录。

    源码运行时：基于本文件的绝对路径上溯两级（settings/ -> 根目录）。
    打包为 exe 后：exe 内部文件解压到临时目录，__file__ 不可靠，
    改为基于可执行文件所在目录（exe 需放在项目根目录）。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

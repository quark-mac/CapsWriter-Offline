# coding: utf-8
"""
开机自启动模块

通过写入注册表 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
实现开机自启动。HKCU 键不需要管理员权限。
"""

import os
from pathlib import Path

from . import get_base_dir

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

# wscript.exe 路径固定，可在任何环境下生成自启动命令（不依赖 python 路径）
WSCRIPT_EXE = os.path.join(
    os.environ.get("SystemRoot", r"C:\Windows"), "System32", "wscript.exe"
)

# 自启动程序定义：(注册表项名, exe 文件名, 中文名)
AUTOSTART_APPS = [
    ("CapsWriter Server", "start_server.exe", "服务端"),
    ("CapsWriter Client", "start_client.exe", "客户端"),
]

# 无感启动脚本参数映射（脚本以隐藏窗口方式启动对应 exe，避免开机弹控制台）
LAUNCHER_ARGS = {
    "CapsWriter Server": "server",
    "CapsWriter Client": "client",
}


def get_app_exe(name):
    """返回自启动程序对应的可执行文件绝对路径（不存在返回 None）"""
    exe_name = dict((n, e) for n, e, _ in AUTOSTART_APPS)[name]
    exe = get_base_dir() / exe_name
    return str(exe) if exe.exists() else None


def get_autostart_command(name):
    """读取注册表中的自启动命令，未设置返回 None"""
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH)
    except FileNotFoundError:
        return None
    try:
        value, _ = winreg.QueryValueEx(key, name)
        return value
    except FileNotFoundError:
        return None
    finally:
        winreg.CloseKey(key)


def is_autostart_enabled(name):
    """检查某项是否已设置自启动"""
    return get_autostart_command(name) is not None


def _exe_name(name):
    for n, e, _ in AUTOSTART_APPS:
        if n == name:
            return e
    return name


def get_launcher_command(name):
    """
    生成无感启动命令：wscript + 启动CapsWriter.vbs + 参数

    启动脚本以隐藏窗口方式启动对应 exe，使开机自启动不弹出控制台。
    未找到启动脚本时返回 None。
    """
    vbs = get_base_dir() / "启动CapsWriter.vbs"
    if not vbs.exists():
        return None
    arg = LAUNCHER_ARGS[name]
    return f'"{WSCRIPT_EXE}" "{vbs}" {arg}'


def enable_autostart(name):
    """启用某项自启动，返回命令字符串；失败抛异常"""
    import winreg
    exe = get_app_exe(name)
    if not exe:
        raise FileNotFoundError(f"未找到可执行文件：{_exe_name(name)}")
    command = get_launcher_command(name)
    if not command:
        raise FileNotFoundError("未找到无感启动脚本：启动CapsWriter.vbs")
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH)
    try:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
    finally:
        winreg.CloseKey(key)
    return command


def disable_autostart(name):
    """取消某项自启动"""
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE)
    except FileNotFoundError:
        return
    try:
        winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass
    finally:
        winreg.CloseKey(key)


def repair_autostart():
    """
    修复自启动项路径：若某项已启用，但其命令指向的不是当前项目目录，
    自动更新为当前目录下的无感启动命令。

    用于「整个文件夹移动/换路径」场景：换路径后首次运行程序，自启动
    自动指向新位置，无需手动重新勾选。返回修复的项数。
    """
    base = str(get_base_dir())
    fixed = 0
    for name, _exe, _cn in AUTOSTART_APPS:
        cmd = get_autostart_command(name)
        if not cmd:
            continue  # 未启用，无需处理
        if base in cmd:
            continue  # 路径正确
        try:
            enable_autostart(name)
            fixed += 1
        except Exception:
            pass
    return fixed


def get_registry_path():
    """返回注册表键的显示路径"""
    return f"HKEY_CURRENT_USER\\{RUN_KEY_PATH}"


if __name__ == "__main__":
    # 简易命令行测试
    for name, exe, cn in AUTOSTART_APPS:
        status = "已启用" if is_autostart_enabled(name) else "未启用"
        print(f"{cn}（{name}）: {status}")
        cmd = get_autostart_command(name)
        if cmd:
            print(f"  命令: {cmd}")

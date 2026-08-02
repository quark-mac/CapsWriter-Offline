# coding: utf-8
"""
桌面快捷方式管理模块

通过 PowerShell + WScript.Shell 创建 / 删除 / 读取 / 更新桌面快捷方式。
软件换路径后，repair_shortcuts() 会自动把已存在的快捷方式更新为当前目录，
无需手动重新创建。

所有 PowerShell 调用均以 CREATE_NO_WINDOW 运行，不弹控制台窗口。
"""

import ctypes
import os
import subprocess
from pathlib import Path

from . import get_base_dir

BASE = get_base_dir()

PWSH = os.path.join(
    os.environ.get("SystemRoot", r"C:\Windows"),
    "System32", "WindowsPowerShell", "v1.0", "powershell.exe",
)
PS1 = BASE / "settings" / "manage_shortcut.ps1"

CREATE_NO_WINDOW = 0x08000000

# 桌面快捷方式定义：(名称, 目标 exe, 描述)
# 目标均为自包含的可执行文件，不依赖系统 Python
SHORTCUTS = [
    ("CapsWriter", "start_caps.exe", "启动 CapsWriter 语音输入"),
    ("CapsWriter 设置", "start_config.exe", "打开 CapsWriter 设置"),
]

_script_map = {name: script for name, script, _ in SHORTCUTS}


def get_desktop_path():
    """获取桌面路径（支持 OneDrive 重定向）"""
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.shell32.SHGetFolderPathW(0, 0x0010, 0, 0, buf)  # CSIDL_DESKTOP
    return buf.value


def _build_params(name):
    """构造快捷方式参数：指向自包含 exe，工作目录与图标指向当前目录"""
    exe = BASE / _script_map[name]
    return {
        "Target": str(exe),
        "Arguments": "",
        "Icon": f'{BASE / "assets" / "icon.ico"},0',
        "WorkDir": str(BASE),
    }


def _run(action, name):
    params = _build_params(name) if action in ("create", "repair") else {}
    cmd = [
        PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1),
        "-BaseDir", str(BASE), "-Desktop", get_desktop_path(),
        "-Action", action, "-Name", name,
    ]
    for k, v in params.items():
        cmd += [f"-{k}", v]
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            creationflags=CREATE_NO_WINDOW, timeout=30,
        )
        return (r.stdout or "").strip(), r.returncode
    except Exception:
        return "", -1


def shortcut_exists(name):
    """桌面是否已存在该快捷方式"""
    out, _ = _run("read", name)
    return "TARGET=" in out


def get_shortcut_info(name):
    """读取快捷方式信息，返回 dict（target/arguments）或 None"""
    out, _ = _run("read", name)
    if out == "absent":
        return None
    info = {}
    for line in out.splitlines():
        if line.startswith("TARGET="):
            info["target"] = line[7:]
        elif line.startswith("ARGS="):
            info["arguments"] = line[5:]
    return info or None


def create_shortcut(name):
    """创建（或覆盖）快捷方式"""
    out, _ = _run("create", name)
    return out == "created"


def delete_shortcut(name):
    """删除快捷方式"""
    out, _ = _run("delete", name)
    return out in ("deleted", "absent")


def repair_shortcuts():
    """
    更新已存在的快捷方式：若其指向不是当前目录，则更新为当前目录。
    返回被更新的快捷方式名称列表。
    """
    fixed = []
    for name, _script, _desc in SHORTCUTS:
        out, _ = _run("repair", name)
        if out == "updated":
            fixed.append(name)
    return fixed


if __name__ == "__main__":
    print("桌面路径:", get_desktop_path())
    for name, _s, _d in SHORTCUTS:
        info = get_shortcut_info(name)
        print(f"{name}: {'已创建 -> ' + info['target'] if info else '未创建'}")

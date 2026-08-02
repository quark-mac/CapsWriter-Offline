# coding: utf-8
"""
无感启动 CapsWriter 服务端与客户端

用 pythonw 运行本脚本（无窗口），以「创建独立控制台但隐藏窗口」的方式启动
start_server.exe / start_client.exe。

配合 core/ui/tray.py 启动时的「强制隐藏」（而非 toggle_window），控制台窗口
从创建起即不可见，不会出现启动闪烁，也不会被托盘 SW_RESTORE 恢复显示。
"""

import os
import subprocess
import sys
import time

# 创建新控制台，并通过 STARTUPINFO 隐藏其窗口
CREATE_NEW_CONSOLE = 0x00000010
SW_HIDE = 0


def _get_base():
    """项目根目录：源码运行用 __file__，打包为 exe 后用 exe 所在目录"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


base = _get_base()


def _start(exe, tag):
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = SW_HIDE
        p = subprocess.Popen(
            [exe],
            cwd=base,
            creationflags=CREATE_NEW_CONSOLE,
            startupinfo=si,
        )
        _log(f"{tag} Popen ok, pid={p.pid}")
        return p
    except Exception as e:
        _log(f"{tag} Popen 失败: {e!r}")
        return None


def _stop_old():
    """结束已运行的旧进程，避免端口占用（服务端无托盘后无法自行重启）"""
    for exe in ("start_server.exe", "start_client.exe"):
        # taskkill 是控制台程序，必须用 CREATE_NO_WINDOW 隐藏，否则会弹出控制台
        subprocess.run(
            ["taskkill", "/F", "/IM", exe],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )


def _repair_autostart():
    """文件夹移动/换路径后，自动把自启动命令更新为当前目录"""
    try:
        sys.path.insert(0, base)
        from settings.autostart import repair_autostart
        return repair_autostart()
    except Exception:
        return 0


def _log(msg):
    """记录启动器运行日志（windowed 模式下无控制台，便于排查）"""
    try:
        log_dir = os.path.join(base, "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "launcher_error.txt"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


def main():
    _log(f"start_caps 启动，base={base}")
    server = os.path.join(base, "start_server.exe")
    client = os.path.join(base, "start_client.exe")
    if not (os.path.exists(server) and os.path.exists(client)):
        _log("缺少 start_server.exe 或 start_client.exe")
        raise SystemExit("缺少 start_server.exe 或 start_client.exe")

    _log("开始修复自启动")
    _repair_autostart()
    _log("结束旧进程")
    _stop_old()
    time.sleep(0.8)  # 等待旧进程完全退出
    _log("启动服务端")
    _start(server, "服务端")
    time.sleep(1.0)  # 等服务端先起来
    _log("启动客户端")
    _start(client, "客户端")
    _log("启动流程完成")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log(f"启动器异常: {e!r}")
    except SystemExit as e:
        _log(f"启动器退出: {e}")

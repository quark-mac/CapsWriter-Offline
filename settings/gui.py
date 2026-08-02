# coding: utf-8
"""
CapsWriter 设置窗口 GUI

提供三个功能页：
1. 开机自启动：通过注册表一键开关服务端 / 客户端自启动
2. 客户端设置：可视化编辑 config_client.py
3. 服务端设置：可视化编辑 config_server.py

可在独立进程运行（start_config.py），也可由托盘菜单在独立线程中打开。
本模块仅依赖 Python 标准库，不依赖 core 包（core 依赖 rich 等第三方库）。
"""

import ast
import ctypes
import logging
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pprint import pformat

from .config_editor import (
    CONFIG_SCHEMA,
    parse_config,
    save_config,
    get_config_path,
)
from .autostart import (
    AUTOSTART_APPS,
    is_autostart_enabled,
    enable_autostart,
    disable_autostart,
    get_autostart_command,
    get_registry_path,
)
from .shortcut import (
    SHORTCUTS,
    shortcut_exists,
    get_shortcut_info,
    create_shortcut,
    delete_shortcut,
    repair_shortcuts,
)

logger = logging.getLogger("settings.gui")

# DPI 感知（与项目其它 UI 模块保持一致）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except (OSError, AttributeError):
    pass

# 有预设选项的字符串字段
STR_CHOICES = {
    "language": ["auto", "chinese", "english", "japanese"],
    "model_type": ["qwen_asr", "fun_asr_nano", "sensevoice", "paraformer"],
    "log_level": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    "traditional_locale": ["zh-hant", "zh-tw", "zh-hk"],
}

_open_state = {"lock": threading.Lock(), "open": False}


def _field_kind(field):
    """根据字段当前值推断编辑控件类型"""
    if field["kind"] == "expr":
        return "text"
    v = field["value"]
    if isinstance(v, bool):
        return "check"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, (list, tuple, dict)):
        return "text"
    return "str"


def _build_label_map(groups):
    m = {}
    for _gname, items in groups:
        for name, label, _help in items:
            m[name] = label
    return m


class SettingsApp:
    """设置窗口主类"""

    def __init__(self, root):
        self.root = root
        self._controls = {"client": {}, "server": {}}  # name -> {type, widget, var, original}
        self._fields = {}
        self._canvases = {}
        self._label_maps = {}
        self._autostart_vars = {}
        self._autostart_labels = {}
        self._shortcut_vars = {}
        self._shortcut_labels = {}
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

    # ------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------

    def _build(self):
        self.root.title("CapsWriter 设置")
        self.root.geometry("780x640")
        self.root.minsize(640, 480)

        try:
            icon = os.path.join(os.path.dirname(get_config_path("client")), "assets", "icon.ico")
            if os.path.exists(icon):
                self.root.iconbitmap(icon)
        except Exception:
            pass

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=6, pady=(6, 0))

        # 开机自启动页
        self._build_autostart_tab(notebook)
        # 桌面快捷方式页
        self._build_shortcut_tab(notebook)
        # 配置页
        self._build_config_tab(notebook, "client")
        self._build_config_tab(notebook, "server")

        # 底部按钮
        btn_bar = ttk.Frame(self.root)
        btn_bar.pack(fill="x", padx=10, pady=8)
        ttk.Button(btn_bar, text="重新载入", command=self._on_reload).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="保存设置", command=self._on_save).pack(side="left", padx=4)
        ttk.Label(
            btn_bar,
            text="配置保存后需重启服务端 / 客户端生效（托盘菜单「🔄 重启」）",
            foreground="#888",
        ).pack(side="right")

    def _build_autostart_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="开机自启动")

        pad = ttk.Frame(frame)
        pad.pack(fill="both", expand=True, padx=14, pady=12)

        ttk.Label(
            pad,
            text="开启后，Windows 登录时将自动启动以下程序：",
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w")

        for name, exe, cn in AUTOSTART_APPS:
            box = ttk.LabelFrame(pad, text=f"{cn}（{exe}）")
            box.pack(fill="x", pady=8)

            row = ttk.Frame(box)
            row.pack(fill="x", padx=10, pady=6)

            var = tk.BooleanVar(value=is_autostart_enabled(name))
            self._autostart_vars[name] = var
            chk = ttk.Checkbutton(
                row,
                text="开机自启动",
                variable=var,
                command=lambda n=name: self._apply_autostart(n),
            )
            chk.pack(side="left")

            lbl = ttk.Label(row, text="", foreground="#666")
            lbl.pack(side="left", padx=10)
            self._autostart_labels[name] = lbl
            self._refresh_autostart_label(name)

        ttk.Label(
            pad,
            text=f"保存位置：{get_registry_path()}（当前用户，无需管理员权限）",
            foreground="#888",
        ).pack(anchor="w", pady=(12, 0))
        ttk.Label(
            pad,
            text="此项立即生效，无需重启。",
            foreground="#888",
        ).pack(anchor="w", pady=(2, 0))

    # ------------------------------------------------------------
    # 桌面快捷方式
    # ------------------------------------------------------------

    def _build_shortcut_tab(self, notebook):
        # 软件路径改变后，自动把已存在的快捷方式更新为当前目录
        try:
            repair_shortcuts()
        except Exception:
            pass

        frame = ttk.Frame(notebook)
        notebook.add(frame, text="桌面快捷方式")

        pad = ttk.Frame(frame)
        pad.pack(fill="both", expand=True, padx=14, pady=12)

        ttk.Label(
            pad,
            text="勾选后将在桌面创建快捷方式；软件路径改变后会自动更新其指向。",
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w")

        for name, script, _desc in SHORTCUTS:
            box = ttk.LabelFrame(pad, text=f"{name}（{script}）")
            box.pack(fill="x", pady=8)

            row = ttk.Frame(box)
            row.pack(fill="x", padx=10, pady=6)

            var = tk.BooleanVar(value=shortcut_exists(name))
            self._shortcut_vars[name] = var
            chk = ttk.Checkbutton(
                row,
                text=f"在桌面创建「{name}」快捷方式",
                variable=var,
                command=lambda n=name: self._apply_shortcut(n),
            )
            chk.pack(side="left")

            lbl = ttk.Label(row, text="", foreground="#666")
            lbl.pack(side="left", padx=10)
            self._shortcut_labels[name] = lbl
            self._refresh_shortcut_label(name)

        ttk.Label(
            pad,
            text="说明：创建后若移动了 CapsWriter 文件夹，重新打开本界面或启动程序即可自动更新快捷方式指向。",
            foreground="#888",
        ).pack(anchor="w", pady=(12, 0))

    def _apply_shortcut(self, name):
        var = self._shortcut_vars[name]
        try:
            if var.get():
                if not create_shortcut(name):
                    raise RuntimeError("创建失败")
            else:
                delete_shortcut(name)
        except Exception as e:
            var.set(not var.get())  # 回滚
            messagebox.showerror("操作失败", f"快捷方式操作失败：\n{e}")
            return
        self._refresh_shortcut_label(name)

    def _refresh_shortcut_label(self, name):
        info = get_shortcut_info(name)
        if info:
            self._shortcut_labels[name].config(
                text=f"已创建 -> {info.get('arguments') or info.get('target') or ''}"
            )
        else:
            self._shortcut_labels[name].config(text="未创建")

    def _build_config_tab(self, notebook, key):
        info = CONFIG_SCHEMA[key]
        self._label_maps[key] = _build_label_map(info["groups"])

        outer = ttk.Frame(notebook)
        notebook.add(outer, text=info["title"])

        canvas = tk.Canvas(outer, highlightthickness=0, bg="#f7f7f7")
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._canvases[key] = canvas

        inner = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(window_id, width=e.width),
        )

        _, self._fields[key] = parse_config(get_config_path(key), info["class"])
        self._controls[key] = {}

        for group_name, items in info["groups"]:
            group = ttk.LabelFrame(inner, text=group_name)
            group.pack(fill="x", padx=8, pady=6)
            for name, _label, _help in items:
                if name not in self._fields[key]:
                    continue
                self._add_field_row(group, key, name, self._fields[key][name])

    def _add_field_row(self, parent, key, name, field):
        kind = _field_kind(field)
        label = self._label_maps[key].get(name, name)

        row = ttk.Frame(parent)
        row.pack(fill="x", padx=10, pady=3)

        ttk.Label(row, text=label, width=18, anchor="w").pack(side="left")

        ctrl = {"type": kind, "name": name}

        if kind == "check":
            var = tk.BooleanVar(value=bool(field["value"]))
            ctrl["var"] = var
            ctrl["original"] = bool(field["value"])
            ttk.Checkbutton(row, variable=var).pack(side="left")
            ctrl["widget"] = None

        elif kind in ("int", "float"):
            original = str(field["value"])
            entry = ttk.Entry(row, width=30)
            entry.insert(0, original)
            entry.pack(side="left", fill="x", expand=True)
            ctrl["widget"] = entry
            ctrl["original"] = original

        elif kind == "str":
            original = field["value"] if isinstance(field["value"], str) else str(field["value"])
            if name in STR_CHOICES:
                combo = ttk.Combobox(row, values=STR_CHOICES[name], width=27)
                combo.set(original)
                combo.pack(side="left", fill="x", expand=True)
                ctrl["widget"] = combo
            else:
                entry = ttk.Entry(row, width=30)
                entry.insert(0, original)
                entry.pack(side="left", fill="x", expand=True)
                ctrl["widget"] = entry
            ctrl["original"] = original

        elif kind == "text":
            if field["kind"] == "expr":
                original = field["value"]
            else:
                try:
                    original = pformat(field["value"])
                except Exception:
                    original = str(field["value"])
            # 使用 tk.Text + ttk.Scrollbar，避免依赖 tkinter.scrolledtext
            # （PyInstaller 打包的 internal/tkinter 不含该子模块）
            text = tk.Text(
                row,
                height=4,
                width=44,
                wrap="none",
                font=("Microsoft YaHei UI", 9),
            )
            scrollbar = ttk.Scrollbar(row, command=text.yview)
            text.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side="left", fill="y")
            text.pack(side="left", fill="x", expand=True, padx=(0, 4))
            text.insert("1.0", original)
            ctrl["widget"] = text
            ctrl["original"] = original

        self._controls[key][name] = ctrl

    # ------------------------------------------------------------
    # 自启动
    # ------------------------------------------------------------

    def _apply_autostart(self, name):
        var = self._autostart_vars[name]
        try:
            if var.get():
                cmd = enable_autostart(name)
                logger.info("已启用开机自启动: %s -> %s", name, cmd)
            else:
                disable_autostart(name)
                logger.info("已取消开机自启动: %s", name)
        except Exception as e:
            var.set(not var.get())  # 回滚
            messagebox.showerror("操作失败", f"修改开机自启动失败：\n{e}")
            return
        self._refresh_autostart_label(name)

    def _refresh_autostart_label(self, name):
        cmd = get_autostart_command(name)
        self._autostart_labels[name].config(text=cmd if cmd else "未启用")

    # ------------------------------------------------------------
    # 配置读写
    # ------------------------------------------------------------

    def _read_control(self, key, name, ctrl):
        """读取控件当前值，返回 AST 表达式节点；未修改返回 None"""
        kind = ctrl["type"]
        if kind == "check":
            cur = ctrl["var"].get()
            if cur == ctrl["original"]:
                return None
            return ast.Constant(bool(cur))

        if kind == "int":
            cur = ctrl["widget"].get().strip()
            if cur == ctrl["original"]:
                return None
            if not cur:
                raise ValueError("不能为空")
            return ast.Constant(int(cur))

        if kind == "float":
            cur = ctrl["widget"].get().strip()
            if cur == ctrl["original"]:
                return None
            if not cur:
                raise ValueError("不能为空")
            return ast.Constant(float(cur))

        if kind == "str":
            cur = ctrl["widget"].get()
            if cur == ctrl["original"]:
                return None
            return ast.Constant(cur)

        if kind == "text":
            cur = ctrl["widget"].get("1.0", "end-1c")
            if cur == ctrl["original"]:
                return None
            try:
                return ast.parse(cur, mode="eval").body
            except SyntaxError as e:
                raise ValueError(f"Python 表达式语法错误（第 {e.lineno} 行）：{e.msg}")

        return None

    def _on_save(self):
        updates = {}  # name -> AST 节点
        errors = []
        for key in ("client", "server"):
            for name, ctrl in self._controls[key].items():
                try:
                    node = self._read_control(key, name, ctrl)
                except Exception as e:
                    errors.append(f"{key}: {name} → {e}")
                    continue
                if node is not None:
                    updates[name] = node

        if errors:
            messagebox.showerror("保存失败", "以下字段有误：\n\n" + "\n".join(errors))
            return

        if not updates:
            messagebox.showinfo("提示", "没有需要保存的修改。")
            return

        for key in ("client", "server"):
            names = [n for n in updates if n in self._fields[key]]
            if names:
                try:
                    save_config(key, {n: updates[n] for n in names})
                except Exception as e:
                    messagebox.showerror("保存失败", f"写入 {CONFIG_SCHEMA[key]['file']} 失败：\n{e}")
                    return

        messagebox.showinfo(
            "保存成功",
            "设置已保存。\n\n请通过托盘菜单「🔄 重启」重启服务端和客户端，使设置生效。",
        )

    def _on_reload(self):
        for key in ("client", "server"):
            _, self._fields[key] = parse_config(get_config_path(key), CONFIG_SCHEMA[key]["class"])
            for name, ctrl in self._controls[key].items():
                if name not in self._fields[key]:
                    continue
                self._reset_control(ctrl, self._fields[key][name])
        messagebox.showinfo("已重载", "已从配置文件重新读取所有设置。")

    def _reset_control(self, ctrl, field):
        """将控件重置为字段当前值"""
        kind = ctrl["type"]
        if kind == "check":
            v = bool(field["value"])
            ctrl["var"].set(v)
            ctrl["original"] = v
        elif kind in ("int", "float", "str"):
            s = field["value"] if isinstance(field["value"], str) else str(field["value"])
            w = ctrl["widget"]
            w.delete(0, "end")
            w.insert(0, s)
            ctrl["original"] = s
        elif kind == "text":
            if field["kind"] == "expr":
                s = field["value"]
            else:
                try:
                    s = pformat(field["value"])
                except Exception:
                    s = str(field["value"])
            w = ctrl["widget"]
            w.delete("1.0", "end")
            w.insert("1.0", s)
            ctrl["original"] = s

    # ------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------

    def _on_mousewheel(self, event):
        step = int(-1 * (event.delta / 120))
        for canvas in self._canvases.values():
            canvas.yview_scroll(step, "units")


# ------------------------------------------------------------
# 入口
# ------------------------------------------------------------

def main():
    """在调用线程创建窗口并进入事件循环（独立运行入口）"""
    root = tk.Tk()
    SettingsApp(root)
    root.mainloop()


def open_settings_window():
    """在独立线程中打开设置窗口（托盘菜单调用，不阻塞主程序）"""
    with _open_state["lock"]:
        if _open_state["open"]:
            return
        _open_state["open"] = True

    def _run():
        try:
            main()
        except Exception as e:
            logger.error("设置窗口运行异常: %s", e)
        finally:
            with _open_state["lock"]:
                _open_state["open"] = False

    threading.Thread(target=_run, daemon=True).start()


if __name__ == "__main__":
    main()

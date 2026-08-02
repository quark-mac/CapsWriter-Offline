# coding: utf-8
"""
配置文件编辑器模块

负责对根目录 config_client.py / config_server.py 两个 Python 源码配置文件的
读取与写入。配置以"类属性赋值"形式存在，为保证不丢失注释和其它内容，
通过 ast 精确解析并改写赋值语句所在行。

读取：定位 class 体内的 Assign 节点，收集字段名与行范围。
写入：用 ast.unparse 生成新的赋值表达式，只替换对应行。
"""

import ast
import shutil
from pathlib import Path

# 项目根目录（settings/config_editor.py -> 上溯两级）
BASE_DIR = Path(__file__).resolve().parents[1]

# 客户端配置字段分组：(分组名, [(字段名, 标签, 说明), ...])
CLIENT_GROUPS = [
    ("网络", [
        ("addr", "服务器地址", "连接的服务端地址"),
        ("port", "服务器端口", "连接的服务端端口"),
        ("udp_broadcast", "UDP 广播", "是否启用 UDP 广播输出结果"),
        ("udp_broadcast_targets", "广播目标", "(地址, 端口) 列表，可用文本框编辑"),
        ("udp_control", "UDP 控制录音", "允许外部程序发送 START/STOP 命令"),
        ("udp_control_addr", "控制监听地址", "127.0.0.1 仅本机；0.0.0.0 允许外部"),
        ("udp_control_port", "控制监听端口", "UDP 控制监听端口"),
    ]),
    ("快捷键", [
        ("shortcuts", "快捷键列表", "键盘/鼠标快捷键配置，Python 列表，可用文本框编辑"),
        ("threshold", "触发阈值（秒）", "快捷键长按判定阈值"),
        ("paste", "粘贴输出", "以「写剪贴板 + Ctrl-V」的方式输出"),
        ("restore_clip", "恢复剪贴板", "模拟粘贴后是否恢复剪贴板"),
        ("paste_apps", "强制粘贴应用", "匹配这些应用名时强制粘贴，Python 列表"),
        ("enter_apps", "自动回车应用", "输出后自动回车，(应用名, 延迟) 列表"),
    ]),
    ("输出", [
        ("context", "识别上下文", "辅助 ASR 识别的提示词（人名、地名等）"),
        ("language", "识别语言", "auto / chinese / english / japanese 等"),
        ("trash_punc", "去除末尾标点", "识别结果要消除的末尾标点字符"),
        ("trash_punc_thresh", "去标点字数阈值", "单词数低于此阈值时强制去除末尾标点"),
        ("trash_punc_apps", "强制去标点应用", "指定应用强制去除末尾标点，Python 列表"),
        ("traditional_convert", "繁体转换", "是否将识别结果转换为繁体中文"),
        ("traditional_locale", "繁体地区", "zh-hant / zh-tw / zh-hk"),
    ]),
    ("热词", [
        ("hot", "启用热词替换", "是否启用基于音素 RAG 的热词替换"),
        ("hot_thresh", "热词替换阈值", "RAG 替换热词阈值（高阈值）"),
        ("hot_similar", "相似热词阈值", "RAG 相似热词阈值（低阈值）"),
        ("hot_rule", "启用规则替换", "是否启用 hot-rule.txt 自定义正则规则"),
    ]),
    ("录音", [
        ("save_audio", "保存录音", "是否保存录音文件"),
        ("audio_name_len", "录音文件名长度", "识别结果前多少字写入文件名（建议 ≤200）"),
        ("mic_seg_duration", "听写分段长度", "麦克风听写时分段长度（秒）"),
        ("mic_seg_overlap", "听写分段重叠", "麦克风听写时分段重叠（秒）"),
    ]),
    ("文件转录", [
        ("file_seg_duration", "转录分段长度", "转录文件时分段长度（秒）"),
        ("file_seg_overlap", "转录分段重叠", "转录文件时分段重叠（秒）"),
        ("file_save_srt", "保存 srt 字幕", "转录时是否保存 .srt 字幕"),
        ("file_save_txt", "保存 txt 文本", "转录时是否保存 .txt 文本"),
        ("file_save_json", "保存 json 结果", "转录时是否保存带时间戳的 .json"),
        ("file_save_merge", "保存 merge 长文本", "转录时是否保存未切分的段落长文本"),
    ]),
    ("LLM", [
        ("llm_enabled", "启用 LLM 润色", "需要配置 LLM/ 目录下的角色文件"),
        ("llm_stop_key", "中断 LLM 快捷键", "中断 LLM 输出的快捷键"),
    ]),
    ("其它", [
        ("enable_tray", "启用托盘", "客户端默认启用托盘图标"),
        ("log_level", "日志级别", "DEBUG / INFO / WARNING / ERROR / CRITICAL"),
    ]),
]

# 服务端配置字段分组
SERVER_GROUPS = [
    ("网络", [
        ("addr", "监听地址", "绑定的服务地址"),
        ("port", "监听端口", "绑定的服务端口"),
    ]),
    ("模型", [
        ("model_type", "语音模型", "qwen_asr / fun_asr_nano / sensevoice / paraformer"),
        ("format_num", "数字格式化", "中文数字转为阿拉伯数字"),
        ("format_spell", "中英空格调整", "调整中英文字之间的空格"),
    ]),
    ("托盘", [
        ("enable_tray", "启用托盘", "服务端是否启用托盘图标"),
        ("hotwords_path", "全局热词路径", "热词配置文件路径（表达式）"),
    ]),
    ("日志与对齐", [
        ("log_level", "日志级别", "DEBUG / INFO / WARNING / ERROR / CRITICAL"),
        ("aligner_idle_timeout", "对齐引擎空闲释放", "空闲多少秒后自动释放显存（0 不释放）"),
    ]),
    ("GPU 加速", [
        ("gpu_boost_enabled", "GPU 预加速", "有识别任务时提前调高显存频率，需管理员权限"),
        ("gpu_boost_cmd", "预加速命令", "锁定显存频率的命令"),
        ("gpu_unboost_cmd", "取消加速命令", "恢复显存默认频率的命令"),
        ("gpu_unboost_timeout", "取消加速等待", "空闲多少秒后取消加速"),
    ]),
]

# 各配置文件信息
CONFIG_SCHEMA = {
    "client": {
        "file": "config_client.py",
        "class": "ClientConfig",
        "title": "客户端设置",
        "groups": CLIENT_GROUPS,
    },
    "server": {
        "file": "config_server.py",
        "class": "ServerConfig",
        "title": "服务端设置",
        "groups": SERVER_GROUPS,
    },
}


def parse_config(path, class_name=None):
    """
    解析配置文件，返回 (源码, 字段信息 dict)

    若指定 class_name，只收集该类的字段；否则收集文件内所有类的字段。
    字段信息: {name: {'lineno', 'end_lineno', 'indent', 'value', 'kind'}}
    - value: 可字面量解析时为 Python 对象，否则为表达式源码文本
    - kind:  'literal' 可用 ast.literal_eval 解析；'expr' 为普通表达式
    """
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    fields = {}

    def _collect(class_node):
        for stmt in class_node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                continue
            name = stmt.targets[0].id
            try:
                value = ast.literal_eval(stmt.value)
                kind = "literal"
            except Exception:
                value = ast.unparse(stmt.value)
                kind = "expr"
            fields[name] = {
                "lineno": stmt.lineno,
                "end_lineno": stmt.end_lineno,
                "indent": stmt.col_offset,
                "value": value,
                "kind": kind,
            }

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and (class_name is None or node.name == class_name):
            _collect(node)
    return source, fields


def _to_ast_node(value):
    """将 Python 对象或 AST 节点统一转换为 AST 表达式节点"""
    if isinstance(value, ast.AST):
        return value
    return ast.parse(repr(value), mode="eval").body


def save_config(key, updates, backup=True):
    """
    保存配置。updates: {字段名: 值}

    值为 AST 表达式节点（GUI 校验后传入），或用 repr 能还原的 Python 对象。
    写回前自动备份为 config_xxx.py.bak，写回后校验语法。
    """
    info = CONFIG_SCHEMA[key]
    path = BASE_DIR / info["file"]
    source, fields = parse_config(path, info["class"])

    lines = source.splitlines(keepends=True)

    # 从后往前替换，避免行号偏移
    targets = sorted(
        (name for name in updates if name in fields),
        key=lambda n: fields[n]["lineno"],
        reverse=True,
    )
    for name in targets:
        field = fields[name]
        new_expr = ast.unparse(_to_ast_node(updates[name]))
        indent = " " * field["indent"]
        new_line = f"{indent}{name} = {new_expr}\n"
        lines[field["lineno"] - 1: field["end_lineno"]] = [new_line]

    new_source = "".join(lines)

    # 语法校验
    ast.parse(new_source)

    if backup:
        bak = path.with_name(path.name + ".bak")
        shutil.copy2(path, bak)

    path.write_text(new_source, encoding="utf-8")
    return list(targets)


def get_config_path(key):
    """返回配置文件的绝对路径"""
    return str(BASE_DIR / CONFIG_SCHEMA[key]["file"])

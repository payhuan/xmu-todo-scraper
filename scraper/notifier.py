"""桌面快捷方式图标管理 — 有24h内截止的待办时切换为警示图标。"""
import os
import subprocess
from datetime import datetime, timedelta

from .models import TodoItem


def _get_icon_paths(data_dir: str) -> tuple[str, str]:
    """返回 (normal_path, warning_path)。"""
    return (
        os.path.join(data_dir, "normal.ico"),
        os.path.join(data_dir, "warning.ico"),
    )


def _powershell(script: str) -> None:
    """执行 PowerShell 脚本。"""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def update_shortcut_icon(shortcut_path: str, icon_path: str) -> None:
    """更新 .lnk 快捷方式的图标。"""
    if not os.path.exists(shortcut_path):
        print(f"  快捷方式不存在: {shortcut_path}")
        return
    abs_icon = os.path.abspath(icon_path).replace("\\", "\\\\")
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$sc = $ws.CreateShortcut('{shortcut_path.replace(chr(92), chr(92)+chr(92))}'); "
        f"$sc.IconLocation = '{abs_icon}'; "
        "$sc.Save()"
    )
    _powershell(ps)


def create_shortcut(shortcut_path: str, target_path: str, icon_path: str) -> None:
    """创建指向 target 的快捷方式（如不存在）。"""
    if os.path.exists(shortcut_path):
        return
    abs_target = os.path.abspath(target_path).replace("\\", "\\\\")
    abs_icon = os.path.abspath(icon_path).replace("\\", "\\\\")
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$sc = $ws.CreateShortcut('{shortcut_path.replace(chr(92), chr(92)+chr(92))}'); "
        f"$sc.TargetPath = '{abs_target}'; "
        f"$sc.IconLocation = '{abs_icon}'; "
        "$sc.Save()"
    )
    _powershell(ps)
    print(f"  已创建桌面快捷方式: {shortcut_path}")


def has_urgent(items: list[TodoItem], hours: int = 24) -> bool:
    """是否有未过期且 N 小时内截止的待办。"""
    tz = None
    for item in items:
        if item.end_time and item.end_time.tzinfo:
            tz = item.end_time.tzinfo
            break
    now = datetime.now(tz=tz) if tz else datetime.now()
    deadline = now + timedelta(hours=hours)
    for item in items:
        if item.end_time and item.end_time <= deadline and not item.is_overdue:
            return True
    return False


def apply_icon_state(courses, config: dict) -> None:
    """根据待办紧急程度更新桌面快捷方式图标。"""
    notifier_cfg = config.get("notifier", {})
    shortcut_path = os.path.expandvars(notifier_cfg.get("shortcut", ""))
    if not shortcut_path:
        return

    data_dir = os.path.dirname(config.get("auth", {}).get("state_file", "./data/auth_state.json"))
    data_dir = data_dir or "./data"

    normal_icon, warning_icon = _get_icon_paths(data_dir)

    all_items = [item for c in courses for item in c.items]
    urgent = has_urgent(all_items)

    icon = warning_icon if urgent else normal_icon
    update_shortcut_icon(shortcut_path, icon)

    target_path = os.path.abspath(
        os.path.join(config["output"]["dir"], config["output"]["filename"] + ".html")
    )
    create_shortcut(shortcut_path, target_path, icon)

    if urgent:
        print("  有待办事项将在24h内截止")
    else:
        print("  暂无紧急待办")

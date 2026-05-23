"""XMU 课程网待办爬取工具

统一爬取所有未完成待办（含超时），按课程分类、按截止时间排序。

用法:
  python main.py --login              手动登录，保存会话
  python main.py --run                 爬取待办并输出报告
  python main.py --save-cred           保存账号密码（自动登录用）
  python main.py --account <名称>     切换账号
  python main.py --list-accounts       列出已保存账号
"""

import argparse
import os
import sys
from datetime import datetime, timezone

import yaml

from scraper import auth, api, notifier
from scraper.models import TodoItem, CourseTodos
from scraper.formatter import print_console, write_outputs


# ── 配置 ──────────────────────────────────────────────

def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _data_dir(config: dict) -> str:
    return os.path.dirname(config["auth"]["state_file"]) or "./data"


def _active_account(config: dict) -> str:
    return config.get("auth", {}).get("account", "default")


def _try_auto_login(config: dict) -> bool:
    data_dir = _data_dir(config)
    account = _active_account(config)
    creds = auth.load_credentials(data_dir, account)
    if not creds:
        print(f"未找到账号 '{account}' 的凭据，请先保存: python main.py --save-cred")
        return False
    return auth.auto_login(
        config["base_url"],
        creds["username"],
        creds["password"],
        config["auth"]["state_file"],
    )


# ── 日期 ──────────────────────────────────────────────

def parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


# ── 核心 ──────────────────────────────────────────────

def scrape_all(config: dict) -> list[CourseTodos]:
    """遍历本学期全部课程，通过 API 直调获取所有未完成活动，按课程分组。"""
    base_url = config["base_url"]
    state_path = config["auth"]["state_file"]
    headless = config["browser"].get("headless", True)

    if not auth.state_file_exists(state_path):
        print("未找到登录状态，尝试自动登录...")
        if not _try_auto_login(config):
            return []

    pw, browser, context = auth.create_context(state_path, headless=headless)

    try:
        if not auth.check_session_valid(context, base_url):
            print("会话已过期，尝试自动登录...")
            context.close()
            browser.close()
            pw.stop()
            if not _try_auto_login(config):
                return []
            pw, browser, context = auth.create_context(state_path, headless=headless)

        print("获取课程列表...")
        courses = api.fetch_my_courses(context, base_url, semester_only=True)
        print(f"  本学期共 {len(courses)} 门课程")

        all_items: list[TodoItem] = []
        for course in courses:
            cid = course["id"]
            cname = course["name"]
            print(f"  检查 {cname}...")

            activities = api.fetch_course_activities(context, base_url, cid)
            completeness_map = api.fetch_learning_task_stat(context, base_url, cid)

            found = 0
            for act in activities:
                act_id = act.get("id", 0)
                completeness = completeness_map.get(act_id, 0)
                if completeness >= 100:
                    continue

                end_time = parse_datetime(act.get("end_time") or act.get("deadline"))
                if end_time is None:
                    continue

                all_items.append(TodoItem(
                    activity_id=str(act_id),
                    title=act.get("title") or act.get("name") or "",
                    course_id=str(cid),
                    course_name=cname,
                    end_time=end_time,
                    todo_type=act.get("type") or "",
                    completeness=completeness,
                ))
                found += 1

            if found:
                print(f"    发现 {found} 项待办")

        context.storage_state(path=state_path)
        print(f"\n  共 {len(all_items)} 项未完成待办")
        return api.group_by_course(all_items)

    finally:
        try:
            context.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass


# ── 桌面图标 ──────────────────────────────────────────

def apply_icon(courses: list[CourseTodos], config: dict) -> None:
    """有 24h 内截止的待办 → warning.ico，否则 → normal.ico。"""
    notifier_cfg = config.get("notifier", {})
    shortcut_path = os.path.expandvars(notifier_cfg.get("shortcut", ""))
    if not shortcut_path:
        return

    data_dir = os.path.dirname(config.get("auth", {}).get("state_file", "./data/auth_state.json"))
    data_dir = data_dir or "./data"

    warning_icon = os.path.join(data_dir, "warning.ico")
    normal_icon = os.path.join(data_dir, "normal.ico")

    all_items = [item for c in courses for item in c.items]
    urgent = notifier.has_urgent(all_items)
    icon = warning_icon if urgent else normal_icon

    target_path = os.path.abspath(os.path.join(config["output"]["dir"], "todos.html"))
    notifier.create_shortcut(shortcut_path, target_path, icon)
    notifier.update_shortcut_icon(shortcut_path, icon)

    if urgent:
        print("  有 24h 内截止的待办，图标已切换为警示")
    else:
        print("  暂无紧急待办")


# ── 命令 ──────────────────────────────────────────────

def cmd_login(config: dict) -> None:
    auth.login_and_save_state(config["base_url"], config["auth"]["state_file"])


def cmd_save_cred(config: dict) -> None:
    account = _active_account(config)
    username = input("学号/工号: ").strip()
    password = input("密码: ").strip()
    if not username or not password:
        print("用户名和密码不能为空")
        return
    auth.save_credentials(_data_dir(config), account, username, password)


def cmd_list_accounts(config: dict) -> None:
    accounts = auth.list_accounts(_data_dir(config))
    if not accounts:
        print("未保存任何账号，请先执行: python main.py --save-cred")
        return
    active = _active_account(config)
    for a in accounts:
        marker = " *" if a == active else ""
        print(f"  {a}{marker}")


def cmd_run(config: dict) -> None:
    courses = scrape_all(config)
    if not courses:
        print("\n未获取到待办数据。")
        apply_icon([], config)
        return

    print_console(courses)
    write_outputs(courses, config)
    apply_icon(courses, config)


# ── 入口 ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="XMU TronClass 待办爬取工具")
    parser.add_argument("--login", action="store_true", help="手动登录并保存会话")
    parser.add_argument("--run", action="store_true", help="爬取待办数据")
    parser.add_argument("--save-cred", action="store_true", help="保存账号密码")
    parser.add_argument("--account", type=str, metavar="NAME", help="切换/指定账号")
    parser.add_argument("--list-accounts", action="store_true", help="列出已保存账号")
    args = parser.parse_args()

    config = load_config()

    if args.account:
        config["auth"]["account"] = args.account

    if args.save_cred:
        cmd_save_cred(config)

    if args.list_accounts:
        cmd_list_accounts(config)

    if args.login:
        cmd_login(config)

    if args.run:
        cmd_run(config)

    if not any([args.login, args.run, args.save_cred, args.list_accounts]):
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

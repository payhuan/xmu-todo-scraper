import json
import os
from datetime import datetime

from .models import TodoItem, CourseTodos


def format_datetime(dt: datetime | None, fmt: str = "%m-%d %H:%M") -> str:
    if dt is None:
        return "无截止"
    return dt.strftime(fmt)


def _overdue_days(end_time: datetime) -> int:
    now = datetime.now(end_time.tzinfo) if end_time.tzinfo else datetime.now()
    return max(0, (now - end_time).days)


def _overdue_label(end_time: datetime) -> str:
    days = _overdue_days(end_time)
    if days == 0:
        return "今天截止"
    elif days == 1:
        return "超时1天"
    else:
        return f"超时{days}天"


def _severity_class(item) -> str:
    if not item.is_overdue or item.end_time is None:
        return ""
    d = _overdue_days(item.end_time)
    if d <= 1:
        return "warn"
    elif d <= 7:
        return "danger"
    else:
        return "critical"


# ── 分组工具 ──────────────────────────────────────────

def _split_courses(courses: list[CourseTodos]) -> tuple[list[CourseTodos], list[CourseTodos]]:
    """将课程列表拆分为 (已超时, 进行中)，各自按课程分组。"""
    overdue_map: dict[str, CourseTodos] = {}
    pending_map: dict[str, CourseTodos] = {}

    for course in courses:
        for item in course.items:
            target = overdue_map if item.is_overdue else pending_map
            key = course.course_id
            if key not in target:
                target[key] = CourseTodos(course_id=course.course_id, course_name=course.course_name)
            target[key].items.append(item)

    overdue = sorted(overdue_map.values(), key=lambda c: c.course_name)
    pending = sorted(pending_map.values(), key=lambda c: c.course_name)
    return overdue, pending


# ── Markdown ──────────────────────────────────────────

def markdown(courses: list[CourseTodos], today: datetime | None = None) -> str:
    if today is None:
        today = datetime.now()

    all_items = [item for c in courses for item in c.items]
    overdue, pending = _split_courses(courses)
    overdue_count = sum(len(c.items) for c in overdue)
    urgent_count = sum(
        1 for item in all_items
        if not item.is_overdue and item.urgency_days is not None and item.urgency_days <= 3
    )

    lines = [f"# 待办事项 — {today.strftime('%Y-%m-%d')}", ""]
    lines.append(f"共 **{len(courses)}** 门课程，**{len(all_items)}** 项待办")
    if overdue_count:
        lines.append(f" | **{overdue_count}** 项已过期")
    if urgent_count:
        lines.append(f" | **{urgent_count}** 项3天内截止")
    lines.append("")

    for section_title, section_courses in [("## 进行中", pending), ("## 已超时", overdue)]:
        if not section_courses:
            continue
        lines.append(section_title)
        lines.append("")
        for course in section_courses:
            lines.append(f"### {course.course_name}")
            lines.append("")
            lines.append("| 截止时间 | 类型 | 标题 | 完成度 | 状态 |")
            lines.append("|----------|------|------|--------|------|")
            for item in course.sorted_items:
                deadline = format_datetime(item.end_time)
                status = _overdue_label(item.end_time) if item.is_overdue else ""
                lines.append(f"| {deadline} | {item.todo_type or '-'} | {item.title} | {item.completeness}% | {status} |")
            lines.append("")
    return "\n".join(lines)


# ── JSON ──────────────────────────────────────────────

def to_json(courses: list[CourseTodos]) -> str:
    overdue, pending = _split_courses(courses)

    def _serialize(clist: list[CourseTodos]) -> list[dict]:
        result = []
        for course in clist:
            items = []
            for item in course.sorted_items:
                items.append({
                    "title": item.title,
                    "type": item.todo_type,
                    "deadline": item.end_time.isoformat() if item.end_time else None,
                    "overdue": item.is_overdue,
                    "completeness": item.completeness,
                    "overdue_days": _overdue_days(item.end_time) if item.is_overdue and item.end_time else 0,
                })
            result.append({
                "course": course.course_name,
                "course_id": course.course_id,
                "count": len(items),
                "items": items,
            })
        return result

    return json.dumps({
        "in_progress": _serialize(pending),
        "overdue": _serialize(overdue),
    }, ensure_ascii=False, indent=2)


# ── HTML ──────────────────────────────────────────────

def _render_course_blocks(courses: list[CourseTodos], section_class: str, section_title: str) -> str:
    if not courses:
        return ""
    blocks = []
    for course in courses:
        rows = []
        for item in course.sorted_items:
            deadline = format_datetime(item.end_time, "%Y-%m-%d %H:%M")
            row_class = ""
            badge = ""

            if item.is_overdue:
                row_class = _severity_class(item)
                label = _overdue_label(item.end_time)
                badge = f'<span class="badge overdue-badge {row_class}">{label}</span>'
            elif item.urgency_days is not None and item.urgency_days <= 1:
                row_class = "urgent"
                badge = '<span class="badge urgent-badge">即将截止</span>'

            rows.append(f"""<tr class="{row_class}">
        <td class="deadline">{deadline}</td>
        <td class="type">{item.todo_type or '-'}</td>
        <td class="title">{item.title}</td>
        <td class="completeness">{item.completeness}%</td>
        <td class="status">{badge}</td>
    </tr>""")
        blocks.append(f"""<section class="course">
    <h2>{course.course_name} <span class="count">({len(course.items)}项)</span></h2>
    <table>
        <thead>
            <tr><th>截止时间</th><th>类型</th><th>标题</th><th>完成度</th><th>状态</th></tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
</section>""")
    return f"""<div class="section {section_class}">
    <div class="section-header">{section_title}</div>
    {''.join(blocks)}
</div>"""


def to_html(courses: list[CourseTodos], today: datetime | None = None) -> str:
    if today is None:
        today = datetime.now()

    all_items = [item for c in courses for item in c.items]
    overdue, pending = _split_courses(courses)
    overdue_count = sum(len(c.items) for c in overdue)
    urgent_count = sum(
        1 for item in all_items
        if not item.is_overdue and item.urgency_days is not None and item.urgency_days <= 3
    )

    badges = []
    if overdue_count:
        badges.append(f'<span class="summary-badge overdue">{overdue_count} 项已过期</span>')
    if urgent_count:
        badges.append(f'<span class="summary-badge urgent">{urgent_count} 项3天内截止</span>')

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>待办事项 — {today.strftime('%Y-%m-%d')}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
        background: #f0f2f5; color: #1a1a2e; line-height: 1.6;
    }}
    .container {{ max-width: 900px; margin: 0 auto; padding: 24px 16px; }}
    header {{ text-align: center; padding: 32px 0 24px; }}
    header h1 {{ font-size: 28px; font-weight: 700; color: #1a1a2e; margin-bottom: 8px; }}
    header .date {{ color: #888; font-size: 14px; }}
    .summary {{ text-align: center; margin-bottom: 24px; font-size: 15px; }}
    .summary-badge {{
        display: inline-block; padding: 4px 14px; border-radius: 20px;
        font-size: 13px; font-weight: 600; margin: 0 6px;
    }}
    .summary-badge.overdue {{ background: #fff1f0; color: #cf1322; }}
    .summary-badge.urgent {{ background: #fff7e6; color: #d46b08; }}
    .section-header {{
        text-align: center; font-size: 18px; font-weight: 700; padding: 12px 0; margin-bottom: 16px;
        border-radius: 8px;
    }}
    .section.overdue-section .section-header {{
        background: #fff1f0; color: #cf1322;
    }}
    .section.pending-section .section-header {{
        background: #e6f7ff; color: #1677ff;
    }}
    .course {{
        background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }}
    .overdue-section .course h2 {{
        border-bottom-color: #cf1322;
    }}
    .pending-section .course h2 {{
        border-bottom-color: #1677ff;
    }}
    .course h2 {{
        font-size: 20px; font-weight: 600; margin-bottom: 16px;
        color: #1a1a2e; border-bottom: 2px solid #1677ff; padding-bottom: 10px;
    }}
    .course h2 .count {{ color: #999; font-size: 14px; font-weight: 400; margin-left: 8px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ text-align: left; padding: 10px 12px; font-size: 13px; color: #888; font-weight: 500; border-bottom: 1px solid #f0f0f0; }}
    td {{ padding: 12px; font-size: 14px; border-bottom: 1px solid #f5f5f5; }}
    tr:last-child td {{ border-bottom: none; }}
    tr.warn {{ background: #fffdf7; }}
    tr.danger {{ background: #fffbfb; }}
    tr.critical {{ background: #fdf7ff; }}
    tr.urgent {{ background: #f0f9ff; border-left: 3px solid #1677ff; }}
    tr.urgent .deadline {{ color: #1677ff; font-weight: 600; }}
    .deadline {{ color: #555; white-space: nowrap; font-variant-numeric: tabular-nums; }}
    .type {{
        color: #1677ff; background: #e6f4ff; padding: 2px 10px;
        border-radius: 4px; font-size: 12px; font-weight: 500;
    }}
    .badge.overdue-badge {{
        padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 500;
    }}
    .badge.overdue-badge.warn {{ background: #fff7e6; color: #d46b08; }}
    .badge.overdue-badge.danger {{ background: #fff1f0; color: #cf1322; }}
    .badge.overdue-badge.critical {{ background: #f9f0ff; color: #531dab; }}
    .badge.urgent-badge {{
        background: #e6f4ff; color: #1677ff;
        padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 600;
        animation: pulse 1.5s ease-in-out infinite;
    }}
    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.5; }}
    }}
    .completeness {{ color: #888; }}
    footer {{ text-align: center; padding: 24px; color: #bbb; font-size: 12px; }}
    @media (max-width: 600px) {{
        .container {{ padding: 12px; }}
        .course {{ padding: 16px; }}
        td, th {{ padding: 8px 6px; font-size: 13px; }}
    }}
</style>
</head>
<body>
<div class="container">
    <header>
        <h1>待办事项</h1>
        <div class="date">上次更新: {today.strftime('%Y-%m-%d %H:%M')}</div>
    </header>
    <div class="summary">
        共 <strong>{len(courses)}</strong> 门课程，<strong>{len(all_items)}</strong> 项待办
        {''.join(badges)}
    </div>
    {_render_course_blocks(pending, 'pending-section', '进行中')}
    {_render_course_blocks(overdue, 'overdue-section', '已超时')}
    <footer>XMU 课程网待办爬取 · {today.strftime('%Y-%m-%d %H:%M')}</footer>
</div>
</body>
</html>"""


# ── 输出 ──────────────────────────────────────────────

def write_outputs(courses: list[CourseTodos], config: dict) -> None:
    output_dir = config["output"]["dir"]
    os.makedirs(output_dir, exist_ok=True)

    today = datetime.now()
    filename_base = config["output"]["filename"].replace("{date}", today.strftime("%Y-%m-%d"))

    for fmt in config["output"]["formats"]:
        if fmt == "html":
            path = os.path.join(output_dir, f"{filename_base}.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(to_html(courses, today))
            print(f"已输出: {path}")

        elif fmt == "markdown":
            path = os.path.join(output_dir, f"{filename_base}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(markdown(courses, today))
            print(f"已输出: {path}")

        elif fmt == "json":
            path = os.path.join(output_dir, f"{filename_base}.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(to_json(courses))
            print(f"已输出: {path}")


def print_console(courses: list[CourseTodos]) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        console = Console()

        all_items = [item for c in courses for item in c.items]
        overdue, pending = _split_courses(courses)
        console.print(f"\n待办事项 — {datetime.now().strftime('%Y-%m-%d')}")
        console.print(f"共 {len(courses)} 门课程，{len(all_items)} 项待办\n")

        for section_title, section_courses, style in [
            ("进行中", pending, "blue"),
            ("已超时", overdue, "red"),
        ]:
            if not section_courses:
                continue
            console.print(Panel.fit(f"[bold {style}]{section_title}[/bold {style}]"))
            for course in section_courses:
                table = Table(title=course.course_name)
                table.add_column("截止时间", style="cyan")
                table.add_column("类型")
                table.add_column("标题")
                table.add_column("完成度")
                table.add_column("状态")
                for item in course.sorted_items:
                    deadline = format_datetime(item.end_time)
                    status = f"[red]{_overdue_label(item.end_time)}[/red]" if item.is_overdue else ""
                    table.add_row(deadline, item.todo_type or "-", item.title, f"{item.completeness}%", status)
                console.print(table)
                console.print()
    except ImportError:
        print(markdown(courses))

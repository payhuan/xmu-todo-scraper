import json
from datetime import datetime

from .models import TodoItem, CourseTodos


KNOWN_TODO_URLS = [
    "/api/todos",
    "/api/v1/todos",
    "/api/user/todos",
    "/api/activities/todo",
]


def intercept_todos(context, base_url: str, timeout_ms: int = 60000) -> list[dict]:
    """用 Playwright 打开首页，拦截网络请求，返回待办数据列表。"""
    captured = []

    page = context.new_page()

    def on_response(response):
        url = response.url
        if not response.ok:
            return
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            return

        try:
            body = response.json()
        except Exception:
            return

        if isinstance(body, dict) and ("todo_list" in body or "todos" in body or "activities" in body):
            captured.append((url, body))
            return

        if isinstance(body, list) and len(body) > 0:
            item = body[0]
            if isinstance(item, dict) and ("end_time" in item or "deadline" in item or "due_date" in item):
                captured.append((url, body))
                return

        for pattern in KNOWN_TODO_URLS:
            if pattern in url:
                captured.append((url, body))
                return

    page.on("response", on_response)
    page.goto(f"{base_url}/user/index#/", timeout=timeout_ms, wait_until="networkidle")

    page.wait_for_timeout(3000)
    page.close()

    for url, body in captured:
        print(f"  发现待办数据源: {url}")
        items = []
        if isinstance(body, dict):
            items = body.get("todo_list") or body.get("todos") or body.get("activities") or body.get("data") or []
        elif isinstance(body, list):
            items = body

        if items and isinstance(items, list):
            return items

    print(f"捕获了 {len(captured)} 个可能的响应，但未识别出待办结构。")
    for url, body in captured:
        preview = list(body.keys()) if isinstance(body, dict) else f"list(length={len(body)})"
        print(f"  {url}: keys={preview}")

    return []


def parse_todo_items(raw_items: list[dict]) -> list[TodoItem]:
    """将 API 返回的原始字典列表解析为 TodoItem 列表。"""
    items = []
    for raw in raw_items:
        end_time = None
        for key in ("end_time", "endTime", "deadline", "due_date", "dueDate"):
            val = raw.get(key)
            if val:
                try:
                    end_time = datetime.fromisoformat(val.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass
                break

        items.append(TodoItem(
            activity_id=str(raw.get("id") or raw.get("activity_id") or ""),
            title=raw.get("title") or raw.get("name") or "",
            course_id=str(raw.get("course_id") or raw.get("courseId") or ""),
            course_name=raw.get("course_name") or raw.get("courseName") or "",
            end_time=end_time,
            todo_type=raw.get("type") or raw.get("activity_type") or "",
        ))

    return items


def group_by_course(items: list[TodoItem]) -> list[CourseTodos]:
    """按课程分组。"""
    course_map: dict[str, CourseTodos] = {}
    for item in items:
        key = item.course_id
        if key not in course_map:
            course_map[key] = CourseTodos(
                course_id=item.course_id,
                course_name=item.course_name,
            )
        course_map[key].items.append(item)

    return list(course_map.values())


# ── 直接 API 调用（超时待办用）──────────────────────

def _api_get_json(context, url: str) -> dict:
    """用 Playwright 发 API 请求并返回 JSON，失败时返回 {} 并打印警告。"""
    page = context.new_page()
    try:
        resp = page.goto(url, timeout=30000, wait_until="domcontentloaded")
        if resp and resp.ok:
            return resp.json()
        status = resp.status if resp else "no response"
        print(f"  [WARN] API 请求失败: {url} (status={status})")
        return {}
    except Exception as e:
        print(f"  [WARN] API 请求异常: {url} ({e})")
        return {}
    finally:
        page.close()


def _current_semester_prefix() -> str:
    """根据当前月份推算学期前缀，如 202520262（2025-2026 学年第 2 学期）。"""
    from datetime import datetime
    now = datetime.now()
    if 2 <= now.month <= 7:
        return f"{now.year - 1}{now.year}2"
    else:
        return f"{now.year}{now.year + 1}1"


def fetch_my_courses(context, base_url: str, semester_only: bool = True) -> list[dict]:
    """获取当前用户课程列表，可选只保留本学期课程。"""
    data = _api_get_json(context, f"{base_url}/api/my-courses")
    courses = data.get("courses", [])
    if not courses or not semester_only:
        return courses

    prefix = _current_semester_prefix()
    return [c for c in courses if (c.get("course_code") or "").startswith(prefix)]


def fetch_course_activities(context, base_url: str, course_id: int) -> list[dict]:
    """获取指定课程的所有活动（含 title、end_time、type 等）。"""
    data = _api_get_json(context, f"{base_url}/api/courses/{course_id}/activities")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "activities" in data:
            return data["activities"] or []
        if "data" in data:
            return data["data"] or []
        print(f"  [WARN] activities 响应结构异常 course={course_id}: keys={list(data.keys())}")
        return []
    print(f"  [WARN] activities 响应类型异常 course={course_id}: type={type(data).__name__}")
    return []


def fetch_learning_task_stat(context, base_url: str, course_id: int) -> dict[int, int]:
    """获取课程完成度统计，返回 {activity_id: completeness}。"""
    data = _api_get_json(context, f"{base_url}/api/courses/{course_id}/learning-task-stat")
    completeness_list = data.get("completeness", []) if isinstance(data, dict) else []
    if isinstance(data, dict) and "completeness" not in data:
        print(f"  [WARN] learning-task-stat 缺少 completeness 字段 course={course_id}")
    return {
        int(item["activity_id"]): item.get("completeness", 0)
        for item in completeness_list
    }

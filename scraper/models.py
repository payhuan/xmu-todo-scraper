from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TodoItem:
    activity_id: str
    title: str
    course_id: str
    course_name: str
    end_time: datetime | None = None
    todo_type: str = ""
    completeness: int = 0

    @property
    def is_overdue(self) -> bool:
        if self.end_time is None:
            return False
        now = datetime.now(tz=self.end_time.tzinfo) if self.end_time.tzinfo else datetime.now()
        return now > self.end_time

    @property
    def urgency_days(self) -> int | None:
        if self.end_time is None:
            return None
        now = datetime.now(tz=self.end_time.tzinfo) if self.end_time.tzinfo else datetime.now()
        return (self.end_time - now).days


@dataclass
class CourseTodos:
    course_id: str
    course_name: str
    items: list[TodoItem] = field(default_factory=list)

    @property
    def sorted_items(self) -> list[TodoItem]:
        """按截止时间升序排列，无截止时间的排最后"""
        return sorted(
            self.items,
            key=lambda x: (
                x.end_time is None,
                x.end_time or datetime.max,
            ),
        )

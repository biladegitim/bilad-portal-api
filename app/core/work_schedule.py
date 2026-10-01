import json
from datetime import time
from typing import Any

from app.models.user import User


def parse_time(value: str | None) -> time | None:
    if not value:
        return None

    try:
        parts = value.split(":")
        return time(int(parts[0]), int(parts[1]))
    except (TypeError, ValueError, IndexError):
        return None


def time_to_string(value: time | None) -> str | None:
    if not value:
        return None

    return value.strftime("%H:%M")


def raw_weekly_schedule(user: User) -> list[dict[str, Any]]:
    if not user.weekly_work_schedule:
        return []

    try:
        schedule = json.loads(user.weekly_work_schedule)
    except (TypeError, json.JSONDecodeError):
        return []

    return schedule if isinstance(schedule, list) else []


def serialize_weekly_schedule(user: User) -> list[dict[str, Any]]:
    schedule_by_day: dict[int, dict[str, Any]] = {}

    for item in raw_weekly_schedule(user):
        if not isinstance(item, dict):
            continue

        try:
            weekday = int(item.get("weekday"))
        except (TypeError, ValueError):
            continue

        if weekday < 0 or weekday > 6:
            continue

        is_working = bool(item.get("is_working"))
        start_time = item.get("start_time")
        end_time = item.get("end_time")
        schedule_by_day[weekday] = {
            "weekday": weekday,
            "is_working": is_working,
            "start_time": start_time if is_working else None,
            "end_time": end_time if is_working else None,
        }

    return [
        schedule_by_day.get(
            weekday,
            {
                "weekday": weekday,
                "is_working": False,
                "start_time": None,
                "end_time": None,
            },
        )
        for weekday in range(7)
    ]


def work_hours_for_date(user: User, record_date):
    if getattr(user, "work_type", "full_time") != "part_time":
        return user.work_start_time, user.work_end_time

    weekday = record_date.weekday()

    for item in serialize_weekly_schedule(user):
        if item["weekday"] != weekday or not item["is_working"]:
            continue

        return parse_time(item.get("start_time")), parse_time(item.get("end_time"))

    return None, None

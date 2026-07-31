from datetime import datetime, timedelta


TURKEY_OFFSET = timedelta(hours=3)


def utc_now() -> datetime:
    return datetime.utcnow()


def turkey_now() -> datetime:
    return utc_now() + TURKEY_OFFSET


def turkey_today():
    return turkey_now().date()


def local_day_bounds(day=None):
    selected_day = day or turkey_today()
    return (
        datetime.combine(selected_day, datetime.min.time()),
        datetime.combine(selected_day, datetime.max.time()),
    )


def turkey_day_bounds_as_utc(day=None):
    start_local, end_local = local_day_bounds(day)
    return start_local - TURKEY_OFFSET, end_local - TURKEY_OFFSET


def utc_to_turkey(value: datetime) -> datetime:
    return value + TURKEY_OFFSET

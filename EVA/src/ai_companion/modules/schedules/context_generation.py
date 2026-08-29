from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from ai_companion.core.schedules import (
    FRIDAY_SCHEDULE,
    MONDAY_SCHEDULE,
    SATURDAY_SCHEDULE,
    SUNDAY_SCHEDULE,
    THURSDAY_SCHEDULE,
    TUESDAY_SCHEDULE,
    WEDNESDAY_SCHEDULE,
)

# Standard Pakistan Timezone (Asia/Karachi, UTC+05:00)
# Pakistan Standard Time is strictly UTC+5 year-round
try:
    from zoneinfo import ZoneInfo
    KARACHI_TZ = ZoneInfo("Asia/Karachi")
except Exception:
    KARACHI_TZ = timezone(timedelta(hours=5), name="PKT")


def get_pakistan_now() -> datetime:
    """Return the current datetime in Pakistan Standard Time (Asia/Karachi, UTC+05:00)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Karachi"))
    except Exception:
        return datetime.now(timezone(timedelta(hours=5), name="PKT"))


def get_pakistan_datetime_context() -> str:
    """Generate dynamic formatted string representing current date & time in Pakistan."""
    pkt_now = get_pakistan_now()
    formatted_date = pkt_now.strftime("%A, %d %B %Y")
    formatted_time_12h = pkt_now.strftime("%I:%M %p")
    formatted_time_24h = pkt_now.strftime("%H:%M")
    day_name = pkt_now.strftime("%A")

    return (
        f"Current Date: {formatted_date}\n"
        f"Current Time: {formatted_time_12h} PKT (24-hour: {formatted_time_24h}, UTC+05:00)\n"
        f"Timezone: Asia/Karachi (Pakistan Standard Time)\n"
        f"Day of the Week: {day_name}"
    )


class ScheduleContextGenerator:
    """Class to generate context about Ava's current activity based on schedules in Pakistan time."""

    SCHEDULES = {
        0: MONDAY_SCHEDULE,  # Monday
        1: TUESDAY_SCHEDULE,  # Tuesday
        2: WEDNESDAY_SCHEDULE,  # Wednesday
        3: THURSDAY_SCHEDULE,  # Thursday
        4: FRIDAY_SCHEDULE,  # Friday
        5: SATURDAY_SCHEDULE,  # Saturday
        6: SUNDAY_SCHEDULE,  # Sunday
    }

    @staticmethod
    def _parse_time_range(time_range: str) -> tuple[datetime.time, datetime.time]:
        """Parse a time range string (e.g., '06:00-07:00') into start and end times."""
        start_str, end_str = time_range.split("-")
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        return start_time, end_time

    @classmethod
    def get_current_activity(cls) -> Optional[str]:
        """Get Ava's current activity based on the current Pakistan time and day of the week.

        Returns:
            str: Description of current activity, or None if no matching time slot is found
        """
        # Always use Pakistan Standard Time (Asia/Karachi)
        current_datetime = get_pakistan_now()
        current_time = current_datetime.time()
        current_day = current_datetime.weekday()

        # Get schedule for current day
        schedule = cls.SCHEDULES.get(current_day, {})

        # Find matching time slot
        for time_range, activity in schedule.items():
            start_time, end_time = cls._parse_time_range(time_range)

            # Handle overnight activities (e.g., 23:00-06:00)
            if start_time > end_time:
                if current_time >= start_time or current_time <= end_time:
                    return activity
            else:
                if start_time <= current_time <= end_time:
                    return activity

        return None

    @classmethod
    def get_schedule_for_day(cls, day: int) -> Dict[str, str]:
        """Get the complete schedule for a specific day.

        Args:
            day: Day of week as integer (0 = Monday, 6 = Sunday)

        Returns:
            Dict[str, str]: Schedule for the specified day
        """
        return cls.SCHEDULES.get(day, {})

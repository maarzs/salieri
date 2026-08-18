import sqlite3
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("salieri.reminders")


class ReminderStore:
    """SQLite-backed reminder store using the same DB pattern as MemoryStore."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        """Create reminders table if it doesn't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                fire_at INTEGER NOT NULL,
                recurring TEXT,
                created_at INTEGER NOT NULL
            )
        """)
        self.conn.commit()

    def add_reminder(self, message: str, fire_at: int, recurring: Optional[str] = None) -> int:
        """Add a new reminder. Returns the reminder ID."""
        created_at = int(datetime.now().timestamp())
        cursor = self.conn.execute(
            "INSERT INTO reminders (message, fire_at, recurring, created_at) VALUES (?, ?, ?, ?)",
            (message, fire_at, recurring, created_at),
        )
        self.conn.commit()
        return cursor.lastrowid

    def list_reminders(self) -> list[dict]:
        """Return all pending reminders."""
        rows = self.conn.execute(
            "SELECT id, message, fire_at, recurring FROM reminders ORDER BY fire_at ASC"
        ).fetchall()
        return [
            {
                "id": row[0],
                "message": row[1],
                "fire_at": row[2],
                "recurring": row[3],
            }
            for row in rows
        ]

    def cancel_reminder(self, query: str) -> int:
        """Cancel a reminder by id (numeric) or message text. Returns count removed."""
        if query.isdigit():
            cursor = self.conn.execute("DELETE FROM reminders WHERE id = ?", (int(query),))
        else:
            cursor = self.conn.execute(
                "DELETE FROM reminders WHERE lower(message) = lower(?)",
                (query.strip(),),
            )
        self.conn.commit()
        return cursor.rowcount or 0

    def get_due_reminders(self) -> list[dict]:
        """Return reminders that are due (fire_at <= now)."""
        now = int(datetime.now().timestamp())
        rows = self.conn.execute(
            "SELECT id, message, fire_at, recurring FROM reminders WHERE fire_at <= ?",
            (now,),
        ).fetchall()
        return [
            {
                "id": row[0],
                "message": row[1],
                "fire_at": row[2],
                "recurring": row[3],
            }
            for row in rows
        ]

    def delete_reminder(self, reminder_id: int):
        """Delete a reminder by ID."""
        self.conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        self.conn.commit()

    def update_reminder(self, reminder_id: int, fire_at: int):
        """Update fire_at for a recurring reminder."""
        self.conn.execute(
            "UPDATE reminders SET fire_at = ? WHERE id = ?",
            (fire_at, reminder_id),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()


def _to_24h(hour: int, ampm: Optional[str]) -> int:
    """Convert a 12-hour clock hour (+am/pm suffix) to 24-hour format."""
    if not ampm:
        return hour
    ampm = ampm.lower()
    if ampm == "am" and hour == 12:
        return 0
    if ampm == "pm" and hour != 12:
        return hour + 12
    return hour


def parse_time(natural_time: str) -> Optional[int]:
    """Parse natural language time into Unix timestamp.

    Supports:
    - 'in N minutes' / 'in N hours' / 'in N days'
    - 'at HH:MM' or 'at H(am|pm)' (today, or tomorrow if already past)
    - 'tomorrow at HH:MM'
    - ISO format (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD HH:MM:SS)
    """
    natural_time = natural_time.strip()

    match = re.match(r'^in\s+(\d+)\s+(minute|minutes|hour|hours|day|days?)$', natural_time, re.I)
    if match:
        value = int(match.group(1))
        unit = match.group(2).lower()
        if unit.startswith('minute'):
            delta = timedelta(minutes=value)
        elif unit.startswith('hour'):
            delta = timedelta(hours=value)
        else:
            delta = timedelta(days=value)
        return int((datetime.now() + delta).timestamp())

    match = re.match(r'^at\s+(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?\s*(am|pm)?$', natural_time, re.I)
    if match:
        hour = _to_24h(int(match.group(1)), match.group(4))
        minute = int(match.group(2) or 0)
        second = int(match.group(3) or 0)
        now = datetime.now()
        fire = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        if fire < now:
            fire = fire + timedelta(days=1)
        return int(fire.timestamp())

    match = re.match(
        r'^tomorrow\s+at\s+(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?\s*(am|pm)?$',
        natural_time, re.I,
    )
    if match:
        hour = _to_24h(int(match.group(1)), match.group(4))
        minute = int(match.group(2) or 0)
        second = int(match.group(3) or 0)
        fire = datetime.now().replace(hour=hour, minute=minute, second=second, microsecond=0)
        fire = fire + timedelta(days=1)
        return int(fire.timestamp())

    iso_patterns = [
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S.%f',
    ]
    for pattern in iso_patterns:
        try:
            fire = datetime.strptime(natural_time, pattern)
            return int(fire.timestamp())
        except ValueError:
            continue

    return None


def parse_reminder_intent(text: str) -> Optional[dict]:
    """Detect 'remind me...' patterns and extract message/time/recurring.

    Patterns supported:
    - 'remind me in N minutes to <message>'
    - 'remind me at HH:MM to <message>'
    - 'remind me tomorrow at HH:MM to <message>'
    - 'remind me every day at HH:MM to <message>'
    - 'remind me every weekday at HH:MM to <message>'
    - 'remind me every week at HH:MM to <message>'
    """
    text_lower = text.lower()

    recurring_map = {
        "every day": "daily",
        "every weekday": "weekdays",
        "every week": "weekly",
    }

    recurring = None
    for pattern, value in recurring_map.items():
        if pattern in text_lower:
            recurring = value
            text_lower = text_lower.replace(pattern, "").strip()
            break

    pattern_defs = [
        (r'remind me\s+(in\s+\d+\s+(?:minute|minutes|hour|hours|day|days?))\s+to\s+(.+)', None),
        (r'remind me\s+(at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+to\s+(.+)', None),
        (r'remind me\s+(tomorrow\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+to\s+(.+)', None),
    ]

    for pattern, _ in pattern_defs:
        match = re.match(pattern, text_lower, re.I)
        if match:
            time_str = match.group(1).strip()
            message = match.group(2).strip()
            fire_at = parse_time(time_str)
            if fire_at:
                return {
                    "message": message,
                    "fire_at": time_str,
                    "recurring": recurring,
                }
    return None


async def reminder_scheduler(store: ReminderStore, on_fire, interval: float = 5.0):
    """Scheduler loop: every ``interval`` seconds fire due reminders.

    ``on_fire`` is an async callback receiving the reminder dict
    ({id, message, fire_at, recurring}). Recurring reminders are rescheduled,
    one-shot reminders deleted. Runs until cancelled.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            for reminder in store.get_due_reminders():
                if reminder["recurring"]:
                    next_fire = None
                    if reminder["recurring"] == "daily":
                        next_fire = reminder["fire_at"] + 86400
                    elif reminder["recurring"] == "weekdays":
                        dt = datetime.fromtimestamp(reminder["fire_at"])
                        while True:
                            dt = dt + timedelta(days=1)
                            if dt.weekday() < 5:
                                break
                        next_fire = int(dt.timestamp())
                    elif reminder["recurring"] == "weekly":
                        next_fire = reminder["fire_at"] + 7 * 86400

                    if next_fire:
                        store.update_reminder(reminder["id"], next_fire)
                    else:
                        store.delete_reminder(reminder["id"])
                else:
                    store.delete_reminder(reminder["id"])

                logger.info(f"Reminder fired: {reminder['message']}")
                await on_fire(reminder)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Reminder scheduler error: {e}")

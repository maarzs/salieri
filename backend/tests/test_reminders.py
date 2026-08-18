"""Tests for reminders.py — store CRUD, time parsing, and scheduler."""

import pytest


@pytest.fixture
def reminder_store(tmp_path):
    """An isolated ReminderStore backed by temp DB."""
    from tools.reminders import ReminderStore

    db_path = str(tmp_path / "reminders.db")
    store = ReminderStore(db_path)
    yield store
    store.close()


def test_add_and_list_reminders(reminder_store):
    import time
    now = int(time.time())

    id1 = reminder_store.add_reminder("Buy milk", now + 300)
    id2 = reminder_store.add_reminder("Call mom", now + 600, "daily")

    reminders = reminder_store.list_reminders()
    assert len(reminders) == 2

    first = next(r for r in reminders if r["id"] == id1)
    assert first["message"] == "Buy milk"
    assert first["fire_at"] == now + 300
    assert first["recurring"] is None

    second = next(r for r in reminders if r["id"] == id2)
    assert second["message"] == "Call mom"
    assert second["recurring"] == "daily"


def test_cancel_reminder_by_id(reminder_store):
    now = int(__import__("time").time())
    id_ = reminder_store.add_reminder("Test", now + 100)

    removed = reminder_store.cancel_reminder(str(id_))
    assert removed == 1
    assert reminder_store.list_reminders() == []


def test_cancel_reminder_by_message(reminder_store):
    now = int(__import__("time").time())
    reminder_store.add_reminder("Test this", now + 100)
    reminder_store.add_reminder("Test this", now + 200)

    removed = reminder_store.cancel_reminder("Test this")
    assert removed == 2


def test_get_due_reminders(reminder_store):
    import time
    now = int(time.time())

    reminder_store.add_reminder("Past", now - 100)
    reminder_store.add_reminder("Future", now + 3600)

    due = reminder_store.get_due_reminders()
    assert len(due) == 1
    assert due[0]["message"] == "Past"


def test_time_parser_relative(reminder_store):
    from tools.reminders import parse_time

    future = parse_time("in 5 minutes")
    now = int(__import__("time").time())
    assert future is not None
    assert 290 < (future - now) < 310

    future = parse_time("in 2 hours")
    assert future is not None
    assert 7100 < (future - now) < 7300

    future = parse_time("in 1 day")
    assert future is not None
    assert 86300 < (future - now) < 86500


def test_time_parser_at_24h(reminder_store):
    from tools.reminders import parse_time
    from datetime import datetime

    now = datetime.now()
    future = parse_time("at 18:30")

    assert future is not None
    fire_dt = datetime.fromtimestamp(future)
    assert fire_dt.hour == 18
    assert fire_dt.minute == 30


def test_time_parser_at_am_pm(reminder_store):
    from tools.reminders import parse_time
    from datetime import datetime

    future_am = parse_time("at 9am")
    future_pm = parse_time("at 3pm")

    assert future_am is not None
    assert future_pm is not None

    fire_am = datetime.fromtimestamp(future_am)
    fire_pm = datetime.fromtimestamp(future_pm)
    assert fire_am.hour == 9
    assert fire_pm.hour == 15


def test_time_parser_tomorrow(reminder_store):
    from tools.reminders import parse_time
    from datetime import datetime, timedelta

    now = datetime.now()
    future = parse_time("tomorrow at 08:00")

    assert future is not None
    fire_dt = datetime.fromtimestamp(future)
    expected = now + timedelta(days=1)
    assert fire_dt.hour == 8
    assert fire_dt.day == expected.day


def test_time_parser_iso(reminder_store):
    from tools.reminders import parse_time
    from datetime import datetime

    future = parse_time("2025-12-31T23:59:00")
    assert future is not None
    # local-time parse — compare against locally-computed ts, not a hardcoded tz value
    assert future == int(datetime(2025, 12, 31, 23, 59).timestamp())


def test_reminder_intent_parser_basic(reminder_store):
    from tools.reminders import parse_reminder_intent

    intent = parse_reminder_intent("remind me in 10 minutes to call john")
    assert intent is not None
    assert intent["message"] == "call john"
    assert intent["fire_at"] == "in 10 minutes"
    assert intent["recurring"] is None


def test_reminder_intent_parser_at_time(reminder_store):
    from tools.reminders import parse_reminder_intent

    intent = parse_reminder_intent("remind me at 18:00 to turn off the oven")
    assert intent is not None
    assert intent["message"] == "turn off the oven"
    assert intent["fire_at"] == "at 18:00"


def test_reminder_intent_parser_recurring(reminder_store):
    from tools.reminders import parse_reminder_intent

    intent = parse_reminder_intent("remind me every day at 09:00 to water the plants")
    assert intent is not None
    assert intent["message"] == "water the plants"
    assert intent["recurring"] == "daily"

    intent = parse_reminder_intent("remind me every weekday at 08:00 to check emails")
    assert intent["recurring"] == "weekdays"

    intent = parse_reminder_intent("remind me every week at 10:00 to review notes")
    assert intent["recurring"] == "weekly"


def test_reminder_scheduler_sends_fired(reminder_store):
    """Scheduler fires due reminders via callback."""
    import time
    import asyncio

    from tools.reminders import reminder_scheduler

    async def run():
        now = int(time.time())
        reminder_id = reminder_store.add_reminder("Test fired", now - 1)
        fired = []

        async def on_fire(r):
            fired.append(r)

        task = asyncio.create_task(
            reminder_scheduler(reminder_store, on_fire, interval=0.05)
        )
        try:
            for _ in range(40):  # wait up to ~2s
                if fired:
                    break
                await asyncio.sleep(0.05)
            assert fired and fired[0]["id"] == reminder_id
            assert fired[0]["message"] == "Test fired"
        finally:
            task.cancel()

    asyncio.run(run())

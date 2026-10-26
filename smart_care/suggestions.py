"""Rule based care suggestions for today. No ML: a pair (plant, task type) is suggested when it is due.

`build_suggestions` is a pure function (no database, no clock) so every rule can be tested directly.
Suggestions are never stored; the page rebuilds them on each load, and they only exist for today.
"""
from collections import namedtuple

# Days between two completions before the task is suggested again. Change them here.
# Pruning, repotting and harvesting are manual only.
INTERVALS = {
    "watering": 2,
    "fertilizing": 14,
    "inspection": 7,
}

# Types suggested for a plant that has never had one recorded. All three by default, which means three
# suggestions per new plant on the first day; trim this tuple (e.g. to ("watering", "inspection")) to quiet it down.
NEVER_RECORDED_TYPES = tuple(INTERVALS)

# Past participle used in the reason text ("Terakhir disiram 3 hari lalu")
VERBS = {
    "watering": "disiram",
    "fertilizing": "dipupuk",
    "inspection": "diperiksa",
}

# One row of care history. `completed_on` is the day it was completed (None unless status is completed).
HistoryEntry = namedtuple("HistoryEntry", "plant_name task_type status due_date completed_on")


def normalize(name):
    """Names are typed by hand, so 'Cabai ' and 'cabai' are the same plant."""
    return " ".join(name.split()).casefold()


def _reason(task_type, last_completed, today):
    if last_completed is None:
        return "Belum pernah dicatat"
    days = (today - last_completed).days
    verb = VERBS[task_type]
    return f"Terakhir {verb} kemarin" if days == 1 else f"Terakhir {verb} {days} hari lalu"


def build_suggestions(plants, history, today, intervals=INTERVALS, never_recorded=NEVER_RECORDED_TYPES,
                      watering_days=None):
    """Return [{plant_name, task_type, is_outdoor, reason}] for `today`.

    plants:  iterable of (plant_name, is_outdoor)
    history: iterable of HistoryEntry. It must include every task dated `today` (any status), so a
             pair that already has a task today is not suggested again, plus completed tasks.
    watering_days: optional {normalized plant name: days}; a plant listed there is watered at its own
             interval instead of intervals["watering"]. Other task types never change.
    """
    watering_days = watering_days or {}
    history = list(history)
    suggestions = []
    for plant_name, is_outdoor in plants:
        key = normalize(plant_name)
        for task_type, interval in intervals.items():
            if task_type == "watering":
                interval = watering_days.get(key, interval)
            same = [e for e in history if normalize(e.plant_name) == key and e.task_type == task_type]
            if any(e.due_date == today for e in same):
                continue
            completed = [e.completed_on for e in same if e.status == "completed" and e.completed_on]
            last = max(completed) if completed else None
            if last is None and task_type not in never_recorded:
                continue
            if last is None or (today - last).days >= interval:
                suggestions.append({
                    "plant_name": plant_name,
                    "task_type": task_type,
                    "is_outdoor": is_outdoor,
                    "reason": _reason(task_type, last, today),
                })
    return suggestions


def _days_since(history, key, task_type, today):
    done = [
        e.completed_on for e in history
        if normalize(e.plant_name) == key and e.task_type == task_type and e.status == "completed" and e.completed_on
    ]
    return (today - max(done)).days if done else None


def plant_status(plant, history, today, intervals=INTERVALS, watering_days=None):
    """How one plant is doing, for its pot. An estimate from the schedule, not a sensor reading.

    plant:   (plant_name, is_outdoor)
    history: iterable of HistoryEntry (same shape as for build_suggestions)
    watering_days: optional {normalized plant name: days}, as for build_suggestions

    Returns water (0..1, what is left of the watering interval), a short label, watering_due, never_recorded
    and fertilizing_ok / inspection_ok (True while the last completion is still inside its interval).
    """
    plant_name, is_outdoor = plant
    key = normalize(plant_name)
    history = list(history)

    interval = (watering_days or {}).get(key, intervals["watering"])
    days = _days_since(history, key, "watering", today)
    if days is None:
        water, label, due, never = 0.0, "Belum dicatat", False, True
    else:
        water = max(0.0, min(1.0, 1 - days / interval))
        remaining = interval - days
        never = False
        due = remaining <= 0
        if due:
            label = "Waktunya siram"
        elif days <= 0:
            label = "Baru disiram"
        elif remaining == 1:
            label = "Siram besok"
        else:
            label = f"Siram {remaining} hari lagi"

    def inside_interval(task_type):
        since = _days_since(history, key, task_type, today)
        return since is not None and since < intervals[task_type]

    return {
        "plant_name": plant_name,
        "key": key,
        "is_outdoor": is_outdoor,
        "water": round(water, 3),
        "label": label,
        "watering_due": due,
        "never_recorded": never,
        "fertilizing_ok": inside_interval("fertilizing"),
        "inspection_ok": inside_interval("inspection"),
    }

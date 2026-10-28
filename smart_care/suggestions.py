"""Rule based care suggestions for today. No ML: a pair (plant, task type) is suggested when it is due.

`build_suggestions` is a pure function (no database, no clock) so every rule can be tested directly.
Suggestions are never stored; the page rebuilds them on each load, and they only exist for today.
"""
from collections import Counter, namedtuple

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
# `patch_plant_id` says which plant row the task belongs to; it is None for a task made before tasks were linked to plants.
HistoryEntry = namedtuple(
    "HistoryEntry", "plant_name task_type status due_date completed_on patch_plant_id", defaults=(None,)
)


def normalize(name):
    """Names are typed by hand, so 'Cabai ' and 'cabai' are the same plant."""
    return " ".join(name.split()).casefold()


def _unpack(plant):
    """(plant_name, is_outdoor[, patch_plant_id[, place]]) -> the four values. The last two are optional: without an id
    a plant is told apart by its name only, which is how a plant typed by hand (and every older test) is handled."""
    plant_name, is_outdoor, *rest = plant
    plant_id = rest[0] if rest else None
    place = rest[1] if len(rest) > 1 else ""
    return plant_name, is_outdoor, plant_id, place


def _belongs(entry, key, plant_id, name_is_unique):
    """Whether a history entry is about this pot.

    A pot that has an id only takes the entries linked to that same id, so the same plant name in two places keeps two
    separate histories. A task made before tasks were linked (no id) can only be matched by name, and only when that
    name is not shared by several pots; otherwise it is ambiguous and counts for none of them.
    """
    if plant_id is None:
        return normalize(entry.plant_name) == key
    if entry.patch_plant_id is not None:
        return entry.patch_plant_id == plant_id
    return name_is_unique and normalize(entry.plant_name) == key


def _watering_interval(watering_days, plant_id, key, default):
    """The pot's own watering interval: looked up by id first (how the page passes them), then by name."""
    if plant_id is not None and plant_id in watering_days:
        return watering_days[plant_id]
    return watering_days.get(key, default)


def _reason(task_type, last_completed, today):
    if last_completed is None:
        return "Belum pernah dicatat"
    days = (today - last_completed).days
    verb = VERBS[task_type]
    return f"Terakhir {verb} kemarin" if days == 1 else f"Terakhir {verb} {days} hari lalu"


def build_suggestions(plants, history, today, intervals=INTERVALS, never_recorded=NEVER_RECORDED_TYPES,
                      watering_days=None):
    """Return [{plant_name, task_type, is_outdoor, patch_plant_id, place, reason}] for `today`.

    plants:  iterable of (plant_name, is_outdoor[, patch_plant_id[, place]]), one per pot
    history: iterable of HistoryEntry. It must include every task dated `today` (any status), so a
             pair that already has a task today is not suggested again, plus completed tasks.
    watering_days: optional {patch_plant_id (or normalized plant name): days}; a plant listed there is watered at its
             own interval instead of intervals["watering"]. Other task types never change.
    """
    # Alur: untuk setiap pasangan (pot, jenis tugas) tentukan apakah hari ini waktunya.
    #   1. Ambil riwayat pasangan itu saja (pot yang sama, lewat ID tanaman; lihat _belongs).
    #   2. Sudah ada tugas hari ini (status apa pun, termasuk skipped)? Lewati, supaya tidak muncul dua kali.
    #   3. Cari tanggal selesai terakhir. Skipped tidak dihitung sebagai selesai.
    #   4. Belum pernah selesai: disarankan bila jenisnya ada di never_recorded.
    #   5. Pernah selesai: disarankan bila selisih hari >= interval.
    watering_days = watering_days or {}
    history = list(history)
    plants = list(plants)
    name_counts = Counter(normalize(_unpack(plant)[0]) for plant in plants)
    suggestions = []
    for plant in plants:
        plant_name, is_outdoor, plant_id, place = _unpack(plant)
        key = normalize(plant_name)
        name_is_unique = name_counts[key] == 1
        for task_type, interval in intervals.items():
            # Interval siram bisa berbeda per tanaman (dari Plant Library). Jenis lain memakai interval bawaan.
            if task_type == "watering":
                interval = _watering_interval(watering_days, plant_id, key, interval)
            same = [e for e in history if e.task_type == task_type and _belongs(e, key, plant_id, name_is_unique)]
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
                    "patch_plant_id": plant_id,
                    "place": place,
                    "reason": _reason(task_type, last, today),
                })
    return suggestions


def _days_since(history, key, plant_id, name_is_unique, task_type, today):
    done = [
        e.completed_on for e in history
        if e.task_type == task_type and e.status == "completed" and e.completed_on
        and _belongs(e, key, plant_id, name_is_unique)
    ]
    return (today - max(done)).days if done else None


def plant_status(plant, history, today, intervals=INTERVALS, watering_days=None, name_is_unique=True):
    """How one plant is doing, for its pot. An estimate from the schedule, not a sensor reading.

    plant:   (plant_name, is_outdoor[, patch_plant_id[, place]])
    history: iterable of HistoryEntry (same shape as for build_suggestions)
    watering_days: optional {patch_plant_id (or normalized plant name): days}, as for build_suggestions
    name_is_unique: False when another pot has the same name; an older, unlinked task then counts for neither

    Returns water (0..1, what is left of the watering interval), a short label, watering_due, never_recorded
    and fertilizing_ok / inspection_ok (True while the last completion is still inside its interval).
    """
    plant_name, is_outdoor, plant_id, place = _unpack(plant)
    key = normalize(plant_name)
    history = list(history)

    interval = _watering_interval(watering_days or {}, plant_id, key, intervals["watering"])
    days = _days_since(history, key, plant_id, name_is_unique, "watering", today)
    if days is None:
        water, label, due, never = 0.0, "Belum dicatat", False, True
    else:
        # water = sisa interval siram: 1.0 saat baru disiram, turun linear ke 0.0 saat jatuh tempo.
        # Contoh interval 2 hari: hari ke-0 -> 1.0, ke-1 -> 0.5, ke-2 -> 0.0. min/max menjaga nilai tetap
        # di 0..1, jadi telat siram 5 hari tidak menghasilkan angka negatif.
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
        since = _days_since(history, key, plant_id, name_is_unique, task_type, today)
        return since is not None and since < intervals[task_type]

    return {
        "plant_name": plant_name,
        # The page finds a pot by this key: the plant row's id, or the name for a plant that has no id
        "key": str(plant_id) if plant_id is not None else key,
        "patch_plant_id": plant_id,
        "place": place,
        "is_outdoor": is_outdoor,
        "water": round(water, 3),
        "label": label,
        "watering_due": due,
        "never_recorded": never,
        "fertilizing_ok": inside_interval("fertilizing"),
        "inspection_ok": inside_interval("inspection"),
    }

# core/io.py
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.schema import (
    Calendar,
    CourseRequirement,
    Group,
    ObjectiveWeights,
    Room,
    RoomType,
    ScheduledEvent,
    Slot,
    SolveConfig,
    Subject,
    Teacher,
    TeacherPolicy,
    TimetableProblem,
    TimetableSolution,
)


def _slot_from_dict(d: Dict[str, Any]) -> Slot:
    return Slot(day=str(d["day"]), period=int(d["period"]))


def _slots_from_list(xs: Optional[Iterable[Dict[str, Any]]]) -> Tuple[Slot, ...]:
    if not xs:
        return tuple()
    return tuple(_slot_from_dict(x) for x in xs)


def _roomtype(v: Any) -> RoomType:
    # admite "LAB" o RoomType.LAB ya serializado como string
    return RoomType(str(v))


def _teacherpolicy(v: Any) -> TeacherPolicy:
    return TeacherPolicy(str(v))


def _frozenset_str(xs: Optional[Iterable[Any]]) -> frozenset[str]:
    if not xs:
        return frozenset()
    return frozenset(str(x) for x in xs)


def _frozenset_int(xs: Optional[Iterable[Any]]) -> Optional[frozenset[int]]:
    if xs is None:
        return None
    return frozenset(int(x) for x in xs)


def calendar_from_dict(d: Dict[str, Any]) -> Calendar:
    return Calendar(
        days=tuple(d["days"]),
        periods_per_day=int(d["periods_per_day"]),
        blocked_slots=frozenset(_slots_from_list(d.get("blocked_slots"))),
    )


def problem_from_dict(d: Dict[str, Any]) -> TimetableProblem:
    cal = calendar_from_dict(d["calendar"])

    groups = tuple(
        Group(id=g["id"], size=int(g["size"]))
        for g in d.get("groups", [])
    )

    subjects = tuple(
        Subject(
            id=s["id"],
            room_type_required=_roomtype(s.get("room_type_required", "NORMAL")),
            max_per_day=(int(s["max_per_day"]) if s.get("max_per_day") is not None else None),
        )
        for s in d.get("subjects", [])
    )

    teachers = tuple(
        Teacher(
            id=t["id"],
            can_teach=_frozenset_str(t.get("can_teach")),
            unavailable=frozenset(_slots_from_list(t.get("unavailable"))),
            max_periods_per_day=(int(t["max_periods_per_day"]) if t.get("max_periods_per_day") is not None else None),
            max_periods_per_week=(int(t["max_periods_per_week"]) if t.get("max_periods_per_week") is not None else None),
            min_periods_per_day=(int(t["min_periods_per_day"]) if t.get("min_periods_per_day") is not None else None),
            min_periods_per_week=(int(t["min_periods_per_week"]) if t.get("min_periods_per_week") is not None else None),
        )
        for t in d.get("teachers", [])
    )

    rooms = tuple(
        Room(
            id=r["id"],
            type=_roomtype(r.get("type", "NORMAL")),
            capacity=int(r.get("capacity", 9999)),
            unavailable=frozenset(_slots_from_list(r.get("unavailable"))),
        )
        for r in d.get("rooms", [])
    )

    requirements = tuple(
        CourseRequirement(
            group_id=req["group_id"],
            subject_id=req["subject_id"],
            periods_per_week=int(req["periods_per_week"]),
            max_consecutive=(int(req["max_consecutive"]) if req.get("max_consecutive") is not None else 2),
            teacher_policy=_teacherpolicy(req.get("teacher_policy", "FIXED")),
            teacher_id=req.get("teacher_id"),
            teacher_pool=(tuple(req["teacher_pool"]) if req.get("teacher_pool") is not None else None),
            preferred_periods=_frozenset_int(req.get("preferred_periods")),
            forbidden_periods=_frozenset_int(req.get("forbidden_periods")),
            allow_double=bool(req.get("allow_double", False)),
        )
        for req in d.get("requirements", [])
    )

    w = d.get("config", {}).get("weights", {})
    weights = ObjectiveWeights(
        teacher_gaps=int(w.get("teacher_gaps", 1000)),
        teacher_late=int(w.get("teacher_late", 100)),
        subject_same_day_excess=int(w.get("subject_same_day_excess", 10)),
        preferred_period_penalty=int(w.get("preferred_period_penalty", 1)),
        forbidden_period_penalty=int(w.get("forbidden_period_penalty", 50)),
    )

    cfg = d.get("config", {})
    config = SolveConfig(
        max_seconds=(int(cfg["max_seconds"]) if cfg.get("max_seconds") is not None else 30),
        random_seed=(int(cfg["random_seed"]) if cfg.get("random_seed") is not None else None),
        weights=weights,
        forbidden_periods_hard=bool(cfg.get("forbidden_periods_hard", True)),
    )

    return TimetableProblem(
        calendar=cal,
        groups=groups,
        subjects=subjects,
        teachers=teachers,
        rooms=rooms,
        requirements=requirements,
        config=config,
    )


def solution_to_dict(sol: TimetableSolution) -> Dict[str, Any]:
    # TimetableSolution contiene Slot y TeacherKey (tuple), así que serializamos “bonito”.
    scheduled = [
        {
            "event_id": se.event_id,
            "slot": {"day": se.slot.day, "period": se.slot.period},
            "room_id": se.room_id,
        }
        for se in sol.scheduled
    ]

    teacher_assignment = [
        {"group_id": k[0], "subject_id": k[1], "teacher_id": tid}
        for k, tid in sol.teacher_assignment.items()
    ]

    return {
        "scheduled": scheduled,
        "teacher_assignment": teacher_assignment,
        "objective_value": sol.objective_value,
        "objective_breakdown": dict(sol.objective_breakdown),
    }

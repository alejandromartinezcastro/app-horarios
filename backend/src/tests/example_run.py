# run_demo_ultra.py
from __future__ import annotations

from collections import defaultdict

from solver.schema import (
    Calendar, Slot,
    Group, Subject, Teacher, Room,
    RoomType, TeacherPolicy,
    CourseRequirement, SolveConfig, ObjectiveWeights,
    TimetableProblem,
)
from solver.validate import validate_problem
from solver.solve import solve


def build_problem() -> TimetableProblem:
    # -------------------------
    # Calendar
    # -------------------------
    days = ("mon", "tue", "wed", "thu", "fri")
    cal = Calendar(
        days=days,
        periods_per_day=6,
        blocked_slots=frozenset({
            Slot("wed", 3),  # recreo general
            Slot("fri", 6),  # reunión centro
        }),
    )

    # -------------------------
    # Groups
    # -------------------------
    groups = (
        Group(id="1ESO_A", size=28),
        Group(id="1ESO_B", size=27),
        Group(id="2ESO_A", size=30),
    )

    # -------------------------
    # Subjects
    # -------------------------
    subjects = (
        Subject(id="MATH",  room_type_required=RoomType.NORMAL, max_per_day=1),
        Subject(id="LANG",  room_type_required=RoomType.NORMAL, max_per_day=1),
        Subject(id="ENG",   room_type_required=RoomType.NORMAL, max_per_day=None),
        Subject(id="SCI",   room_type_required=RoomType.LAB,    max_per_day=1),
        Subject(id="HIST",  room_type_required=RoomType.NORMAL, max_per_day=1),
        Subject(id="PE",    room_type_required=RoomType.GYM,    max_per_day=1),
        Subject(id="TECH",  room_type_required=RoomType.IT,     max_per_day=1),
        Subject(id="MUSIC", room_type_required=RoomType.MUSIC,  max_per_day=None),
        Subject(id="ART",   room_type_required=RoomType.OTHER,  max_per_day=None),
        Subject(id="TUTOR", room_type_required=RoomType.NORMAL, max_per_day=None),
    )

    # -------------------------
    # Teachers
    # -------------------------
    teachers = (
        Teacher(
            id="T_MATH1",
            can_teach=frozenset({"MATH"}),
            unavailable=frozenset({Slot("mon", 6), Slot("wed", 1)}),
            max_periods_per_week=10,
        ),
        Teacher(
            id="T_MATH2",
            can_teach=frozenset({"MATH"}),
            unavailable=frozenset({Slot("tue", 2), Slot("thu", 6)}),
            max_periods_per_week=10,
        ),
        Teacher(
            id="T_LANG1",
            can_teach=frozenset({"LANG"}),
            unavailable=frozenset({Slot("mon", 1), Slot("wed", 6)}),
            max_periods_per_week=18,
        ),
        Teacher(
            id="T_ENG1",
            can_teach=frozenset({"ENG"}),
            unavailable=frozenset({Slot("tue", 6), Slot("thu", 1)}),
            max_periods_per_week=15,
        ),
        Teacher(
            id="T_SCI1",
            can_teach=frozenset({"SCI"}),
            unavailable=frozenset({Slot("wed", 2), Slot("fri", 1)}),
            max_periods_per_week=12,
        ),
        Teacher(
            id="T_HIST1",
            can_teach=frozenset({"HIST"}),
            unavailable=frozenset({Slot("mon", 5), Slot("thu", 2)}),
            max_periods_per_week=15,
        ),
        Teacher(
            id="T_PE1",
            can_teach=frozenset({"PE"}),
            unavailable=frozenset({Slot("mon", 2), Slot("wed", 5)}),
            max_periods_per_week=10,
        ),
        Teacher(
            id="T_TECH1",
            can_teach=frozenset({"TECH"}),
            unavailable=frozenset({Slot("tue", 3), Slot("fri", 2)}),
            max_periods_per_week=10,
        ),
        Teacher(
            id="T_MUSIC1",
            can_teach=frozenset({"MUSIC"}),
            unavailable=frozenset({Slot("wed", 4), Slot("thu", 4)}),
            max_periods_per_week=8,
        ),
        Teacher(
            id="T_ART1",
            can_teach=frozenset({"ART"}),
            unavailable=frozenset({Slot("mon", 3), Slot("fri", 5)}),
            max_periods_per_week=10,
        ),
        Teacher(
            id="T_TUTOR1",
            can_teach=frozenset({"TUTOR"}),
            unavailable=frozenset({Slot("thu", 5)}),
            max_periods_per_week=6,
        ),
    )

    # -------------------------
    # Rooms
    # -------------------------
    rooms = (
        Room(id="N101", type=RoomType.NORMAL, capacity=30),
        Room(id="N102", type=RoomType.NORMAL, capacity=30),
        Room(id="N103", type=RoomType.NORMAL, capacity=30),

        Room(id="L201", type=RoomType.LAB, capacity=30, unavailable=frozenset({Slot("thu", 3)})),
        Room(id="G01",  type=RoomType.GYM, capacity=60, unavailable=frozenset({Slot("tue", 5)})),
        Room(id="IT1",  type=RoomType.IT, capacity=30,  unavailable=frozenset({Slot("wed", 6)})),
        Room(id="M01",  type=RoomType.MUSIC, capacity=30, unavailable=frozenset({Slot("mon", 4)})),
        Room(id="A01",  type=RoomType.OTHER, capacity=30, unavailable=frozenset({Slot("tue", 1)})),
    )

    # -------------------------
    # Requirements (por grupo)
    # 27 sesiones/semana por grupo (<= 28 slots lectivos por bloqueos)
    # -------------------------
    def reqs_for_group(gid: str) -> list[CourseRequirement]:
        return [
            CourseRequirement(
                group_id=gid, subject_id="MATH", periods_per_week=5, max_consecutive=2,
                teacher_policy=TeacherPolicy.CHOOSE,
                teacher_pool=("T_MATH1", "T_MATH2"),
                preferred_periods=frozenset({2, 3, 4, 5}),
                forbidden_periods=frozenset({6}),
            ),
            CourseRequirement(
                group_id=gid, subject_id="LANG", periods_per_week=4, max_consecutive=2,
                teacher_policy=TeacherPolicy.FIXED, teacher_id="T_LANG1",
                preferred_periods=frozenset({1, 2, 3, 4, 5}),
                forbidden_periods=frozenset({6}),
            ),
            CourseRequirement(
                group_id=gid, subject_id="ENG", periods_per_week=3, max_consecutive=2,
                teacher_policy=TeacherPolicy.FIXED, teacher_id="T_ENG1",
                preferred_periods=frozenset({2, 3, 4, 5}),
                forbidden_periods=None,
            ),
            CourseRequirement(
                group_id=gid, subject_id="SCI", periods_per_week=3, max_consecutive=2,
                teacher_policy=TeacherPolicy.FIXED, teacher_id="T_SCI1",
                preferred_periods=frozenset({2, 3, 4, 5}),
                forbidden_periods=frozenset({1, 6}),
            ),
            CourseRequirement(
                group_id=gid, subject_id="HIST", periods_per_week=4, max_consecutive=2,
                teacher_policy=TeacherPolicy.FIXED, teacher_id="T_HIST1",
                preferred_periods=frozenset({1, 2, 3, 4, 5}),
                forbidden_periods=frozenset({6}),
            ),
            CourseRequirement(
                group_id=gid, subject_id="PE", periods_per_week=2, max_consecutive=2,
                teacher_policy=TeacherPolicy.FIXED, teacher_id="T_PE1",
                preferred_periods=frozenset({2, 3, 4, 5}),
                forbidden_periods=frozenset({1, 6}),
            ),
            CourseRequirement(
                group_id=gid, subject_id="TECH", periods_per_week=2, max_consecutive=2,
                teacher_policy=TeacherPolicy.FIXED, teacher_id="T_TECH1",
                preferred_periods=frozenset({2, 3, 4, 5}),
                forbidden_periods=frozenset({1, 6}),
            ),
            CourseRequirement(
                group_id=gid, subject_id="MUSIC", periods_per_week=1, max_consecutive=1,
                teacher_policy=TeacherPolicy.FIXED, teacher_id="T_MUSIC1",
                preferred_periods=frozenset({3, 4, 5}),
                forbidden_periods=None,
            ),
            CourseRequirement(
                group_id=gid, subject_id="ART", periods_per_week=2, max_consecutive=2,
                teacher_policy=TeacherPolicy.FIXED, teacher_id="T_ART1",
                preferred_periods=frozenset({2, 3, 4, 5}),
                forbidden_periods=frozenset({6}),
            ),
            CourseRequirement(
                group_id=gid, subject_id="TUTOR", periods_per_week=1, max_consecutive=1,
                teacher_policy=TeacherPolicy.FIXED, teacher_id="T_TUTOR1",
                preferred_periods=None,
                forbidden_periods=frozenset({6}),
            ),
        ]

    requirements = tuple(req for g in groups for req in reqs_for_group(g.id))

    # -------------------------
    # Config
    # -------------------------
    config = SolveConfig(
        max_seconds=30,
        random_seed=42,
        forbidden_periods_hard=False,
        weights=ObjectiveWeights(
            teacher_gaps=1000,
            teacher_late=100,
            subject_same_day_excess=10,
            preferred_period_penalty=1,
            forbidden_period_penalty=50,
        ),
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


def pretty_print_solution(problem: TimetableProblem, sol) -> None:
    # Mapa: event_id -> ScheduledEvent
    ev_by_id = {se.event_id: se for se in sol.scheduled}

    # Parse event_id "GROUP-SUBJECT-XX"
    def parse_event_id(eid: str) -> tuple[str, str]:
        parts = eid.split("-")
        # group puede tener "_" pero no "-"
        # subject tampoco tiene "-"
        return parts[0], parts[1]

    # Construye (group -> (slot -> (subject, room)))
    by_group = defaultdict(dict)
    for eid, se in ev_by_id.items():
        g, sub = parse_event_id(eid)
        by_group[g][se.slot] = (sub, se.room_id)

    # Imprime por grupo
    days = problem.calendar.days
    ppd = problem.calendar.periods_per_day
    blocked = problem.calendar.blocked_slots

    print("\n" + "=" * 90)
    print("HORARIOS POR GRUPO")
    print("=" * 90)

    for g in problem.groups:
        print(f"\n--- {g.id} (size={g.size}) ---")
        for d in days:
            row = []
            for p in range(1, ppd + 1):
                slot = Slot(d, p)
                if slot in blocked:
                    row.append("   [BLOQ]   ")
                else:
                    item = by_group[g.id].get(slot)
                    if not item:
                        row.append("   (LIB)    ")
                    else:
                        sub, rid = item
                        row.append(f"{sub}@{rid}".ljust(11)[:11])
            print(f"{d}: " + " | ".join(row))

    # Horario por profesor (según teacher_assignment)
    print("\n" + "=" * 90)
    print("HORARIOS POR PROFESOR (según teacher_assignment del solver)")
    print("=" * 90)

    # (group,subject) -> teacher_id
    ta = sol.teacher_assignment

    # Mapa: teacher_id -> (slot -> "GROUP-SUBJECT@ROOM")
    by_teacher = defaultdict(dict)

    for eid, se in ev_by_id.items():
        g, sub = parse_event_id(eid)
        tid = ta[(g, sub)]
        by_teacher[tid][se.slot] = f"{g}-{sub}@{se.room_id}"

    for t in problem.teachers:
        print(f"\n--- {t.id} ---")
        for d in days:
            row = []
            for p in range(1, ppd + 1):
                slot = Slot(d, p)
                if slot in blocked:
                    row.append("   [BLOQ]   ")
                else:
                    item = by_teacher[t.id].get(slot)
                    if not item:
                        row.append("   (LIB)    ")
                    else:
                        row.append(item.ljust(11)[:11])
            print(f"{d}: " + " | ".join(row))

    print("\n" + "=" * 90)
    print("OBJETIVO")
    print("=" * 90)
    print("objective_value:", sol.objective_value)
    print("objective_breakdown:", sol.objective_breakdown)


def main():
    problem = build_problem()

    # 1) Validar
    report = validate_problem(problem, raise_on_error=False)
    if not report.ok:
        print("❌ Validation errors:")
        for e in report.errors:
            print(" -", e)
        return
    if report.warnings:
        print("⚠️ Validation warnings:")
        for w in report.warnings:
            print(" -", w)

    # 2) Resolver
    sol = solve(problem)

    # 3) Mostrar
    pretty_print_solution(problem, sol)


if __name__ == "__main__":
    main()

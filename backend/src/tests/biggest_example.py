# run_instituto_full_occupancy.py
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from solver.schema import (
    Calendar, Slot,
    Group, Subject, Teacher, Room,
    RoomType, TeacherPolicy,
    CourseRequirement, SolveConfig, ObjectiveWeights,
    TimetableProblem,
)
from solver.validate import validate_problem
from solver.solve import solve


DAYS = ("mon", "tue", "wed", "thu", "fri")


def parse_event_id(eid: str) -> tuple[str, str]:
    # "GROUP-SUBJECT-XX"
    parts = eid.split("-")
    return parts[0], parts[1]


def print_group_timetables(problem: TimetableProblem, sol, *, limit_groups: int | None = None) -> None:
    ev_by_id = {se.event_id: se for se in sol.scheduled}

    by_group: Dict[str, Dict[Slot, Tuple[str, str]]] = defaultdict(dict)
    for eid, se in ev_by_id.items():
        g, sub = parse_event_id(eid)
        by_group[g][se.slot] = (sub, se.room_id)

    days = problem.calendar.days
    ppd = problem.calendar.periods_per_day
    blocked = problem.calendar.blocked_slots

    groups = list(problem.groups)
    if limit_groups is not None:
        groups = groups[:limit_groups]

    print("\n" + "=" * 140)
    print("HORARIOS POR GRUPO (FULL OCCUPANCY)")
    print("=" * 140)

    for g in groups:
        print(f"\n--- {g.id} (size={g.size}) ---")
        for d in days:
            row = []
            for p in range(1, ppd + 1):
                s = Slot(d, p)
                if s in blocked:
                    row.append("[BLOQ]".ljust(12))
                else:
                    item = by_group[g.id].get(s)
                    if not item:
                        row.append("(VACIO?)".ljust(12))
                    else:
                        sub, rid = item
                        row.append(f"{sub}@{rid}".ljust(12)[:12])
            print(f"{d}: " + " | ".join(row))


def print_objective(sol) -> None:
    print("\n" + "=" * 140)
    print("OBJETIVO")
    print("=" * 140)
    print("objective_value:", sol.objective_value)
    print("objective_breakdown:", sol.objective_breakdown)


def build_full_occupancy_institute() -> TimetableProblem:
    # ------------------------------------------------------------------
    # CALENDARIO: 5 días x 7 periodos = 35 slots lectivos (sin bloqueos)
    # ------------------------------------------------------------------
    periods_per_day = 7
    cal = Calendar(
        days=DAYS,
        periods_per_day=periods_per_day,
        blocked_slots=frozenset(),  # clave para "clase SIEMPRE"
    )
    slots_per_week = len(cal.teaching_slots())  # 35

    # ------------------------------------------------------------------
    # GRUPOS (12): 1ESO..4ESO (A/B) + 1BACH/2BACH (A/B)
    # ------------------------------------------------------------------
    groups = (
        Group("1ESO_A", 28), Group("1ESO_B", 27),
        Group("2ESO_A", 29), Group("2ESO_B", 28),
        Group("3ESO_A", 30), Group("3ESO_B", 29),
        Group("4ESO_A", 30), Group("4ESO_B", 28),
        Group("1BACH_A", 32), Group("1BACH_B", 31),
        Group("2BACH_A", 30), Group("2BACH_B", 29),
    )

    # ------------------------------------------------------------------
    # ASIGNATURAS
    # Nota: evitamos max_per_day hard salvo PE para no hacer el problema durísimo.
    # ------------------------------------------------------------------
    subjects = (
        Subject("MATH",  RoomType.NORMAL, max_per_day=None),
        Subject("LANG",  RoomType.NORMAL, max_per_day=None),
        Subject("ENG",   RoomType.NORMAL, max_per_day=None),
        Subject("HIST",  RoomType.NORMAL, max_per_day=None),
        Subject("PHIL",  RoomType.NORMAL, max_per_day=None),
        Subject("ECON",  RoomType.NORMAL, max_per_day=None),
        Subject("TUTOR", RoomType.NORMAL, max_per_day=None),

        Subject("SCI",   RoomType.LAB,    max_per_day=None),  # ESO
        Subject("PHYS",  RoomType.LAB,    max_per_day=None),  # BACH
        Subject("CHEM",  RoomType.LAB,    max_per_day=None),
        Subject("BIO",   RoomType.LAB,    max_per_day=None),

        Subject("TECH",  RoomType.IT,     max_per_day=None),
        Subject("PE",    RoomType.GYM,    max_per_day=1),     # única hard “razonable”
        Subject("MUSIC", RoomType.MUSIC,  max_per_day=None),
        Subject("ART",   RoomType.OTHER,  max_per_day=None),

        # comodín para rellenar hasta 35/semana (estudio, guardia, taller, refuerzo…)
        Subject("STUDY", RoomType.NORMAL, max_per_day=None),
    )

    # ------------------------------------------------------------------
    # AULAS (MUCHAS para que no haya cuellos)
    # Con full occupancy, necesitas al menos ~n_grupos aulas normales simultáneas.
    # ------------------------------------------------------------------
    rooms: List[Room] = []

    # 30 aulas normales cap 35
    for i in range(101, 131):
        rooms.append(Room(id=f"N{i}", type=RoomType.NORMAL, capacity=35))

    # 8 labs cap 35
    for i in range(201, 209):
        rooms.append(Room(id=f"L{i}", type=RoomType.LAB, capacity=35))

    # 4 gimnasios
    for i in range(1, 5):
        rooms.append(Room(id=f"G0{i}", type=RoomType.GYM, capacity=80))

    # 6 aulas IT
    for i in range(1, 7):
        rooms.append(Room(id=f"IT{i}", type=RoomType.IT, capacity=35))

    # 2 música + 2 arte
    rooms.append(Room(id="M01", type=RoomType.MUSIC, capacity=35))
    rooms.append(Room(id="M02", type=RoomType.MUSIC, capacity=35))
    rooms.append(Room(id="A01", type=RoomType.OTHER, capacity=35))
    rooms.append(Room(id="A02", type=RoomType.OTHER, capacity=35))

    rooms = tuple(rooms)

    # ------------------------------------------------------------------
    # PROFESORES (muchos) y SIN unavailable agresivos (para que sea resoluble rápido)
    # Cada profe tiene max_week alto para no cortar por carga.
    # ------------------------------------------------------------------
    teachers: List[Teacher] = []

    def add_teachers(prefix: str, n: int, subject_id: str, max_week: int = 28):
        for i in range(1, n + 1):
            teachers.append(
                Teacher(
                    id=f"{prefix}{i}",
                    can_teach=frozenset({subject_id}),
                    unavailable=frozenset(),      # simplifica (rápido y feasible)
                    max_periods_per_week=max_week
                )
            )

    add_teachers("T_MATH_", 10, "MATH", max_week=28)
    add_teachers("T_LANG_", 8,  "LANG", max_week=28)
    add_teachers("T_ENG_",  8,  "ENG",  max_week=26)
    add_teachers("T_HIST_", 8,  "HIST", max_week=26)
    add_teachers("T_PHIL_", 6,  "PHIL", max_week=24)
    add_teachers("T_ECON_", 6,  "ECON", max_week=24)
    add_teachers("T_TUT_",  6,  "TUTOR",max_week=18)

    add_teachers("T_SCI_",  8,  "SCI",  max_week=24)
    add_teachers("T_PHY_",  8,  "PHYS", max_week=24)
    add_teachers("T_CHE_",  8,  "CHEM", max_week=24)
    add_teachers("T_BIO_",  8,  "BIO",  max_week=24)

    add_teachers("T_TECH_", 8,  "TECH", max_week=22)
    add_teachers("T_PE_",   8,  "PE",   max_week=22)
    add_teachers("T_MUS_",  6,  "MUSIC",max_week=18)
    add_teachers("T_ART_",  6,  "ART",  max_week=18)

    # STUDY: muchos (sirve para rellenar y dar flexibilidad)
    add_teachers("T_STD_",  14, "STUDY", max_week=30)

    teachers = tuple(teachers)

    # Pools por asignatura
    teachers_by_subject: Dict[str, Tuple[str, ...]] = defaultdict(tuple)
    for t in teachers:
        for s in t.can_teach:
            teachers_by_subject[s] = tuple(list(teachers_by_subject[s]) + [t.id])

    # ------------------------------------------------------------------
    # REQUIREMENTS: FULL OCCUPANCY
    # Para cada grupo: suma(periods_per_week) = 35 (slots_per_week)
    #
    # Estrategia:
    # - ESO: un bloque realista + STUDY rellena hasta 35
    # - BACH: más ciencias específicas + STUDY rellena lo que falte
    # ------------------------------------------------------------------
    def cr(gid: str, sub: str, n: int, max_consec: int = 3) -> CourseRequirement:
        return CourseRequirement(
            group_id=gid,
            subject_id=sub,
            periods_per_week=n,
            max_consecutive=max_consec,
            teacher_policy=TeacherPolicy.CHOOSE,
            teacher_pool=teachers_by_subject[sub],
            preferred_periods=None,
            forbidden_periods=None,
        )

    requirements: List[CourseRequirement] = []

    def add_eso(gid: str):
        # Base ESO = 26 horas + STUDY 9 = 35
        base = [
            ("MATH", 5),
            ("LANG", 4),
            ("ENG", 3),
            ("HIST", 3),
            ("SCI", 4),
            ("TECH", 2),
            ("PE", 2),
            ("PHIL", 2),
            ("ECON", 2),
            ("MUSIC", 1),
            ("ART", 1),
            ("TUTOR", 1),
        ]
        total = sum(x[1] for x in base)
        filler = slots_per_week - total
        assert filler >= 0

        for sub, n in base:
            requirements.append(cr(gid, sub, n, max_consec=3 if sub != "PE" else 2))
        if filler:
            requirements.append(cr(gid, "STUDY", filler, max_consec=4))

    def add_bach(gid: str):
        # Base BACH = 34 horas + STUDY 1 = 35 (puedes subir/bajar y STUDY ajusta)
        base = [
            ("MATH", 5),
            ("LANG", 3),
            ("ENG", 3),
            ("HIST", 2),
            ("PHIL", 2),
            ("ECON", 3),
            ("PHYS", 4),
            ("CHEM", 4),
            ("BIO", 3),
            ("TECH", 2),
            ("PE", 2),
            ("TUTOR", 1),
        ]
        total = sum(x[1] for x in base)
        filler = slots_per_week - total
        assert filler >= 0

        for sub, n in base:
            requirements.append(cr(gid, sub, n, max_consec=3 if sub != "PE" else 2))
        if filler:
            requirements.append(cr(gid, "STUDY", filler, max_consec=4))

    for g in groups:
        if "BACH" in g.id:
            add_bach(g.id)
        else:
            add_eso(g.id)

    # ------------------------------------------------------------------
    # CONFIG: sin forbidden hard; objetivo normal
    # Nota: full occupancy hace el problema más duro. Dale tiempo razonable.
    # ------------------------------------------------------------------
    config = SolveConfig(
        max_seconds=500,      # sube a 120 si tu PC va justo
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
        requirements=tuple(requirements),
        config=config,
    )


def main():
    problem = build_full_occupancy_institute()

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

    sol = solve(problem)

    # imprime 6 grupos para no inundar. Pon None para todos.
    print_group_timetables(problem, sol, limit_groups=None)
    print_objective(sol)


if __name__ == "__main__":
    main()

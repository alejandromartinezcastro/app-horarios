# run_instituto_grande.py
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
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


# -----------------------------
# Utilidades
# -----------------------------

DAYS = ("mon", "tue", "wed", "thu", "fri")

def slots_for_day(day: str, periods_per_day: int) -> List[Slot]:
    return [Slot(day, p) for p in range(1, periods_per_day + 1)]

def mk_unavail(pattern: List[Tuple[str, int]]) -> frozenset[Slot]:
    return frozenset(Slot(d, p) for d, p in pattern)

def parse_event_id(eid: str) -> tuple[str, str]:
    # "GROUP-SUBJECT-XX"  (ojo: group/subject no deben contener '-')
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

    print("\n" + "=" * 120)
    print("HORARIOS POR GRUPO")
    print("=" * 120)

    for g in groups:
        print(f"\n--- {g.id} (size={g.size}) ---")
        for d in days:
            row = []
            for p in range(1, ppd + 1):
                s = Slot(d, p)
                if s in blocked:
                    row.append("[BLOQ]".ljust(10))
                else:
                    item = by_group[g.id].get(s)
                    if not item:
                        row.append("(LIB)".ljust(10))
                    else:
                        sub, rid = item
                        row.append(f"{sub}@{rid}".ljust(10)[:10])
            print(f"{d}: " + " | ".join(row))

def print_teacher_summary(problem: TimetableProblem, sol) -> None:
    # Resumen: profesor asignado a cada (group, subject)
    print("\n" + "=" * 120)
    print("ASIGNACIÓN DE PROFESORES (group,subject) -> teacher")
    print("=" * 120)
    items = sorted(sol.teacher_assignment.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    for (g, sub), tid in items:
        print(f"{g:8s} {sub:6s} -> {tid}")

def print_objective(sol) -> None:
    print("\n" + "=" * 120)
    print("OBJETIVO")
    print("=" * 120)
    print("objective_value:", sol.objective_value)
    print("objective_breakdown:", sol.objective_breakdown)


# -----------------------------
# Construcción “instituto entero”
# -----------------------------

def build_institute_problem() -> TimetableProblem:
    # Semana tipo: 5 días x 7 periodos = 35
    # Bloqueamos: recreo wed-4 y reunión fri-7 => quedan 33 slots lectivos
    periods_per_day = 7
    cal = Calendar(
        days=DAYS,
        periods_per_day=periods_per_day,
        blocked_slots=frozenset({
            Slot("wed", 4),  # recreo/descanso
            Slot("fri", 7),  # reunión/claustro
        }),
    )

    # 12 grupos (instituto grande):
    groups = (
        Group("1ESO_A", 28), Group("1ESO_B", 27),
        Group("2ESO_A", 29), Group("2ESO_B", 28),
        Group("3ESO_A", 30), Group("3ESO_B", 29),
        Group("4ESO_A", 30), Group("4ESO_B", 28),
        Group("1BACH_A", 32), Group("1BACH_B", 31),
        Group("2BACH_A", 30), Group("2BACH_B", 29),
    )

    # Asignaturas (algunas con max_per_day hard):
    subjects = (
        Subject("MATH",  RoomType.NORMAL, max_per_day=1),
        Subject("LANG",  RoomType.NORMAL, max_per_day=1),
        Subject("ENG",   RoomType.NORMAL, max_per_day=1),
        Subject("HIST",  RoomType.NORMAL, max_per_day=1),
        Subject("PE",    RoomType.GYM,    max_per_day=1),
        Subject("TECH",  RoomType.IT,     max_per_day=1),
        Subject("MUSIC", RoomType.MUSIC,  max_per_day=None),
        Subject("ART",   RoomType.OTHER,  max_per_day=None),

        # Ciencias (LAB)
        Subject("SCI",   RoomType.LAB,    max_per_day=1),  # ESO general
        Subject("PHYS",  RoomType.LAB,    max_per_day=1),  # Bach
        Subject("CHEM",  RoomType.LAB,    max_per_day=1),
        Subject("BIO",   RoomType.LAB,    max_per_day=1),

        # Otras
        Subject("PHIL",  RoomType.NORMAL, max_per_day=1),
        Subject("ECON",  RoomType.NORMAL, max_per_day=1),
        Subject("TUTOR", RoomType.NORMAL, max_per_day=None),
    )

    # Aulas (muchas normales + varias especiales)
    rooms = []

    # 14 aulas normales cap 35
    for i in range(101, 115):
        rooms.append(Room(id=f"N{i}", type=RoomType.NORMAL, capacity=35))

    # 4 LAB cap 34 (algunos bloqueos puntuales)
    rooms.extend([
        Room("L201", RoomType.LAB, capacity=34, unavailable=mk_unavail([("thu", 3)])),
        Room("L202", RoomType.LAB, capacity=34, unavailable=mk_unavail([("tue", 2)])),
        Room("L203", RoomType.LAB, capacity=34, unavailable=mk_unavail([("fri", 2)])),
        Room("L204", RoomType.LAB, capacity=34, unavailable=frozenset()),
    ])

    # 2 gimnasios
    rooms.extend([
        Room("G01", RoomType.GYM, capacity=80, unavailable=mk_unavail([("tue", 5)])),
        Room("G02", RoomType.GYM, capacity=80, unavailable=mk_unavail([("wed", 6)])),
    ])

    # 4 aulas IT
    rooms.extend([
        Room("IT1", RoomType.IT, capacity=34, unavailable=mk_unavail([("wed", 7)])),
        Room("IT2", RoomType.IT, capacity=34, unavailable=mk_unavail([("mon", 7)])),
        Room("IT3", RoomType.IT, capacity=34, unavailable=frozenset()),
        Room("IT4", RoomType.IT, capacity=34, unavailable=frozenset()),
    ])

    # Música y Arte
    rooms.extend([
        Room("M01", RoomType.MUSIC, capacity=34, unavailable=mk_unavail([("mon", 4)])),
        Room("A01", RoomType.OTHER, capacity=34, unavailable=mk_unavail([("tue", 1)])),
        Room("A02", RoomType.OTHER, capacity=34, unavailable=frozenset()),
    ])

    rooms = tuple(rooms)

    # Profesores (muchos, por pools amplios)
    # Unavailable moderado: 2-3 huecos por semana para cada profe.
    teachers = []

    def add_teachers(prefix: str, n: int, can_teach: set[str], unavail_patterns: List[List[Tuple[str,int]]], max_week: int):
        for i in range(1, n + 1):
            pat = unavail_patterns[(i - 1) % len(unavail_patterns)]
            teachers.append(
                Teacher(
                    id=f"{prefix}{i}",
                    can_teach=frozenset(can_teach),
                    unavailable=mk_unavail(pat),
                    max_periods_per_week=max_week,
                )
            )

    # Patrones repetibles
    P = [
        [("mon", 1), ("wed", 2), ("thu", 7)],
        [("tue", 2), ("thu", 1), ("fri", 6)],
        [("mon", 6), ("wed", 1), ("fri", 3)],
        [("tue", 6), ("wed", 5), ("thu", 2)],
        [("mon", 3), ("tue", 4), ("fri", 5)],
        [("wed", 7), ("thu", 5), ("fri", 1)],
    ]

    # Núcleo ESO+Bach
    add_teachers("T_MATH_", 5, {"MATH"}, P, max_week=22)
    add_teachers("T_LANG_", 4, {"LANG"}, P, max_week=22)
    add_teachers("T_ENG_",  4, {"ENG"},  P, max_week=20)
    add_teachers("T_HIST_", 4, {"HIST"}, P, max_week=20)
    add_teachers("T_PE_",   3, {"PE"},   P, max_week=18)
    add_teachers("T_TECH_", 4, {"TECH"}, P, max_week=18)
    add_teachers("T_MUS_",  2, {"MUSIC"},P, max_week=14)
    add_teachers("T_ART_",  2, {"ART"},  P, max_week=14)

    # Ciencias
    add_teachers("T_SCI_",  4, {"SCI"},  P, max_week=18)   # ESO general
    add_teachers("T_PHY_",  3, {"PHYS"}, P, max_week=16)   # Bach
    add_teachers("T_CHE_",  3, {"CHEM"}, P, max_week=16)
    add_teachers("T_BIO_",  3, {"BIO"},  P, max_week=16)

    # Otras
    add_teachers("T_PHIL_", 3, {"PHIL"}, P, max_week=18)
    add_teachers("T_ECON_", 2, {"ECON"}, P, max_week=16)
    add_teachers("T_TUT_",  3, {"TUTOR"},P, max_week=12)

    teachers = tuple(teachers)

    # Helper: pool por asignatura (todos los que la pueden enseñar)
    teachers_by_subject: Dict[str, Tuple[str, ...]] = defaultdict(tuple)
    for t in teachers:
        for s in t.can_teach:
            teachers_by_subject[s] = tuple(list(teachers_by_subject[s]) + [t.id])

    # Requirements
    # Slots lectivos por semana = 35 - 2 bloqueados = 33
    # Vamos a pedir ~30-31 por grupo para que sea “instituto real” y deje algo de aire.
    #
    # Preferencias:
    # - preferred_periods = {2,3,4,5,6}
    # - forbidden_periods = {1,7} (pero soft: forbidden_periods_hard=False)
    preferred = frozenset({2,3,4,5,6})
    forbidden_soft = frozenset({1,7})

    def cr(gid: str, sub: str, n: int, max_consec: int = 2) -> CourseRequirement:
        return CourseRequirement(
            group_id=gid,
            subject_id=sub,
            periods_per_week=n,
            max_consecutive=max_consec,
            teacher_policy=TeacherPolicy.CHOOSE,
            teacher_pool=teachers_by_subject[sub],  # pool grande
            preferred_periods=preferred,
            forbidden_periods=forbidden_soft,
        )

    requirements: List[CourseRequirement] = []

    # ESO (1-4): SCI en lugar de PHYS/CHEM/BIO separados
    def add_eso(gid: str):
        # Total: 30
        requirements.extend([
            cr(gid, "MATH", 5),
            cr(gid, "LANG", 4),
            cr(gid, "ENG",  3),
            cr(gid, "HIST", 3),
            cr(gid, "SCI",  3),
            cr(gid, "TECH", 2),
            cr(gid, "PE",   2),
            cr(gid, "ART",  2),
            cr(gid, "MUSIC",1, max_consec=1),
            cr(gid, "PHIL", 2),
            cr(gid, "TUTOR",1, max_consec=1),
            # “Horas libres” (2) para que no vaya al 100%:
            # En tu modelo no existe “FREE”, así que simplemente no las pedimos.
        ])

    # BACH: más carga de ciencias específicas y economía
    def add_bach(gid: str):
        # Total: 31
        requirements.extend([
            cr(gid, "MATH", 5),
            cr(gid, "LANG", 3),
            cr(gid, "ENG",  3),
            cr(gid, "HIST", 2),
            cr(gid, "PHIL", 2),
            cr(gid, "ECON", 3),
            cr(gid, "PHYS", 3),
            cr(gid, "CHEM", 3),
            cr(gid, "BIO",  2),
            cr(gid, "TECH", 2),
            cr(gid, "PE",   2),
            cr(gid, "TUTOR",1, max_consec=1),
        ])

    for g in groups:
        if "BACH" in g.id:
            add_bach(g.id)
        else:
            add_eso(g.id)

    # Config (IMPORTANTE: forbidden soft para evitar infeasible por “6ª/7ª hora”)
    config = SolveConfig(
        max_seconds=330,
        random_seed=42,
        forbidden_periods_hard=False,  # <- clave para factibilidad en instancias grandes
        weights=ObjectiveWeights(
            teacher_gaps=1000,
            teacher_late=120,               # penaliza últimas horas
            subject_same_day_excess=10,
            preferred_period_penalty=1,
            forbidden_period_penalty=80,    # “evítalo” pero si hace falta, que lo use
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


# -----------------------------
# Main
# -----------------------------

def main():
    problem = build_institute_problem()

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

    # OJO: esto imprime MUCHO.
    # Puedes limitar a X grupos para no inundar la consola.
    print_group_timetables(problem, sol, limit_groups=6)  # pon None para imprimir los 12
    print_teacher_summary(problem, sol)
    print_objective(sol)


if __name__ == "__main__":
    main()

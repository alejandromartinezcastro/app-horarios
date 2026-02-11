# solver/validate.py
# Validaciones “antes de solver” para evitar instancias imposibles o datos rotos.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from core.schema import (
    Calendar,
    CourseRequirement,
    Slot,
    TeacherPolicy,
    TimetableProblem,
)


# ------------------ API pública ------------------

class ValidationError(ValueError):
    """Error de validación con múltiples mensajes."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    errors: List[str]
    warnings: List[str]


def validate_problem(problem: TimetableProblem, *, raise_on_error: bool = True) -> ValidationReport:
    """
    Valida el TimetableProblem.
    - Si raise_on_error=True y hay errores -> lanza ValidationError.
    - Si no, devuelve ValidationReport con errores y warnings.
    """
    errors: List[str] = []
    warnings: List[str] = []

    _validate_calendar(problem.calendar, errors, warnings)
    _validate_uniqueness(problem, errors)
    _validate_entities(problem, errors, warnings)
    _validate_requirements(problem, errors, warnings)
    _validate_capacity_sanity(problem, errors, warnings)

    report = ValidationReport(ok=(len(errors) == 0), errors=errors, warnings=warnings)
    if raise_on_error and errors:
        raise ValidationError(errors)
    return report


# ------------------ Helpers ------------------

def _validate_calendar(cal: Calendar, errors: List[str], warnings: List[str]) -> None:
    if not cal.days:
        errors.append("Calendar.days está vacío.")
        return

    if cal.periods_per_day <= 0:
        errors.append(f"Calendar.periods_per_day debe ser > 0 (actual: {cal.periods_per_day}).")

    for s in cal.blocked_slots:
        if s.day not in cal.days:
            errors.append(f"blocked_slot {s} usa un day '{s.day}' que no está en Calendar.days.")
        if s.period < 1 or s.period > cal.periods_per_day:
            errors.append(f"blocked_slot {s} usa period {s.period} fuera de 1..{cal.periods_per_day}.")

    if cal.periods_per_day > 12:
        warnings.append(
            f"Calendar.periods_per_day={cal.periods_per_day} es alto; revisa si realmente son periodos lectivos."
        )

    if len(cal.teaching_slots()) == 0:
        errors.append("No hay slots lectivos disponibles: todos los slots están bloqueados.")


def _validate_uniqueness(problem: TimetableProblem, errors: List[str]) -> None:
    def dupes(ids: List[str]) -> Set[str]:
        seen: Set[str] = set()
        d: Set[str] = set()
        for x in ids:
            if x in seen:
                d.add(x)
            seen.add(x)
        return d

    g_dupes = dupes([g.id for g in problem.groups])
    s_dupes = dupes([s.id for s in problem.subjects])
    t_dupes = dupes([t.id for t in problem.teachers])
    r_dupes = dupes([r.id for r in problem.rooms])

    if g_dupes:
        errors.append(f"IDs de grupos duplicados: {sorted(g_dupes)}")
    if s_dupes:
        errors.append(f"IDs de asignaturas duplicados: {sorted(s_dupes)}")
    if t_dupes:
        errors.append(f"IDs de profesores duplicados: {sorted(t_dupes)}")
    if r_dupes:
        errors.append(f"IDs de aulas duplicados: {sorted(r_dupes)}")


def _validate_entities(problem: TimetableProblem, errors: List[str], warnings: List[str]) -> None:
    cal = problem.calendar
    groups = problem.index_groups()
    subjects = problem.index_subjects()
    teachers = problem.index_teachers()

    # Groups
    for g in problem.groups:
        if not g.id.strip():
            errors.append("Existe un Group con id vacío.")
        if g.size <= 0:
            errors.append(f"Group '{g.id}' tiene size <= 0 (actual: {g.size}).")

    # Subjects
    for sub in problem.subjects:
        if not sub.id.strip():
            errors.append("Existe un Subject con id vacío.")
        if sub.max_per_day is not None and sub.max_per_day <= 0:
            errors.append(f"Subject '{sub.id}': max_per_day debe ser > 0 o None.")
        if sub.max_per_day is not None and sub.max_per_day > cal.periods_per_day:
            warnings.append(
                f"Subject '{sub.id}': max_per_day={sub.max_per_day} > periods_per_day={cal.periods_per_day}."
            )

    # Teachers
    for t in problem.teachers:
        if not t.id.strip():
            errors.append("Existe un Teacher con id vacío.")
        for sub_id in t.can_teach:
            if sub_id not in subjects:
                errors.append(f"Teacher '{t.id}' can_teach incluye subject_id desconocido '{sub_id}'.")
        for s in t.unavailable:
            if s.day not in cal.days:
                errors.append(f"Teacher '{t.id}' tiene unavailable {s} con day fuera de Calendar.days.")
            if s.period < 1 or s.period > cal.periods_per_day:
                errors.append(
                    f"Teacher '{t.id}' tiene unavailable {s} con period fuera de 1..{cal.periods_per_day}."
                )

        _validate_min_max_pair(
            f"Teacher '{t.id}'",
            "min_periods_per_day", t.min_periods_per_day,
            "max_periods_per_day", t.max_periods_per_day,
            errors
        )
        _validate_min_max_pair(
            f"Teacher '{t.id}'",
            "min_periods_per_week", t.min_periods_per_week,
            "max_periods_per_week", t.max_periods_per_week,
            errors
        )

        if t.max_periods_per_day is not None and t.max_periods_per_day > cal.periods_per_day:
            warnings.append(
                f"Teacher '{t.id}': max_periods_per_day={t.max_periods_per_day} > periods_per_day={cal.periods_per_day}."
            )

    # Rooms
    for r in problem.rooms:
        if not r.id.strip():
            errors.append("Existe un Room con id vacío.")
        if r.capacity <= 0:
            errors.append(f"Room '{r.id}' tiene capacity <= 0 (actual: {r.capacity}).")
        for s in r.unavailable:
            if s.day not in cal.days:
                errors.append(f"Room '{r.id}' tiene unavailable {s} con day fuera de Calendar.days.")
            if s.period < 1 or s.period > cal.periods_per_day:
                errors.append(
                    f"Room '{r.id}' tiene unavailable {s} con period fuera de 1..{cal.periods_per_day}."
                )


def _validate_min_max_pair(
    ctx: str,
    min_name: str, min_val: Optional[int],
    max_name: str, max_val: Optional[int],
    errors: List[str]
) -> None:
    if min_val is not None and min_val < 0:
        errors.append(f"{ctx}: {min_name} no puede ser negativo (actual: {min_val}).")
    if max_val is not None and max_val < 0:
        errors.append(f"{ctx}: {max_name} no puede ser negativo (actual: {max_val}).")
    if min_val is not None and max_val is not None and min_val > max_val:
        errors.append(f"{ctx}: {min_name} ({min_val}) > {max_name} ({max_val}).")


def _validate_requirements(problem: TimetableProblem, errors: List[str], warnings: List[str]) -> None:
    cal = problem.calendar
    groups = problem.index_groups()
    subjects = problem.index_subjects()
    teachers = problem.index_teachers()

    seen_keys: Set[Tuple[str, str]] = set()
    for req in problem.requirements:
        key = (req.group_id, req.subject_id)
        if key in seen_keys:
            errors.append(
                f"CourseRequirement duplicado para group='{req.group_id}', subject='{req.subject_id}'. "
                "Combínalos en uno (sumando periods_per_week) o usa un id extra si realmente son distintos."
            )
        seen_keys.add(key)

    for req in problem.requirements:
        if req.group_id not in groups:
            errors.append(f"Requirement referencia group_id desconocido '{req.group_id}'.")
            continue
        if req.subject_id not in subjects:
            errors.append(f"Requirement referencia subject_id desconocido '{req.subject_id}'.")
            continue

        if req.periods_per_week <= 0:
            errors.append(
                f"Requirement (group={req.group_id}, subject={req.subject_id}): "
                f"periods_per_week debe ser > 0 (actual: {req.periods_per_week})."
            )

        if req.max_consecutive is not None:
            if req.max_consecutive <= 0:
                errors.append(
                    f"Requirement (group={req.group_id}, subject={req.subject_id}): "
                    f"max_consecutive debe ser > 0 o None (actual: {req.max_consecutive})."
                )
            if req.max_consecutive > cal.periods_per_day:
                warnings.append(
                    f"Requirement (group={req.group_id}, subject={req.subject_id}): "
                    f"max_consecutive={req.max_consecutive} > periods_per_day={cal.periods_per_day}."
                )

        _validate_period_set(
            ctx=f"Requirement (group={req.group_id}, subject={req.subject_id}) preferred_periods",
            periods=req.preferred_periods,
            max_period=cal.periods_per_day,
            errors=errors,
            warnings=warnings,
            allow_empty=False,
        )
        _validate_period_set(
            ctx=f"Requirement (group={req.group_id}, subject={req.subject_id}) forbidden_periods",
            periods=req.forbidden_periods,
            max_period=cal.periods_per_day,
            errors=errors,
            warnings=warnings,
            allow_empty=True,
        )

        if req.teacher_policy == TeacherPolicy.FIXED:
            if not req.teacher_id:
                errors.append(
                    f"Requirement (group={req.group_id}, subject={req.subject_id}): "
                    "teacher_policy=FIXED pero teacher_id es None/vacío."
                )
            elif req.teacher_id not in teachers:
                errors.append(
                    f"Requirement (group={req.group_id}, subject={req.subject_id}): "
                    f"teacher_id '{req.teacher_id}' no existe."
                )
            else:
                t = teachers[req.teacher_id]
                if req.subject_id not in t.can_teach:
                    errors.append(
                        f"Requirement (group={req.group_id}, subject={req.subject_id}): "
                        f"Teacher '{t.id}' no puede enseñar '{req.subject_id}' (no está en can_teach)."
                    )

        elif req.teacher_policy == TeacherPolicy.CHOOSE:
            pool = list(req.teacher_pool) if req.teacher_pool else [
                t.id for t in problem.teachers if req.subject_id in t.can_teach
            ]
            if not pool:
                errors.append(
                    f"Requirement (group={req.group_id}, subject={req.subject_id}): "
                    "teacher_policy=CHOOSE pero el pool de profesores queda vacío."
                )
            else:
                for tid in pool:
                    if tid not in teachers:
                        errors.append(
                            f"Requirement (group={req.group_id}, subject={req.subject_id}): "
                            f"teacher_pool contiene teacher_id desconocido '{tid}'."
                        )
                        continue
                    if req.subject_id not in teachers[tid].can_teach:
                        errors.append(
                            f"Requirement (group={req.group_id}, subject={req.subject_id}): "
                            f"teacher_pool incluye '{tid}' que no puede enseñar '{req.subject_id}'."
                        )
        else:
            errors.append(
                f"Requirement (group={req.group_id}, subject={req.subject_id}): teacher_policy desconocida {req.teacher_policy}."
            )

        sub = subjects[req.subject_id]
        g = groups[req.group_id]
        rooms_ok = [
            r for r in problem.rooms
            if (r.type == sub.room_type_required and r.capacity >= g.size)
        ]
        if not rooms_ok:
            errors.append(
                f"Requirement (group={req.group_id}, subject={req.subject_id}): "
                f"no hay Room compatible (type={sub.room_type_required}, capacity>={g.size})."
            )

        possible_slots = _possible_slots_for_requirement(problem, req)
        if req.periods_per_week > len(possible_slots):
            errors.append(
                f"Requirement (group={req.group_id}, subject={req.subject_id}): "
                f"pide {req.periods_per_week} sesiones/semana pero solo hay {len(possible_slots)} slots posibles "
                f"según bloqueos/forbidden/availability."
            )


def _validate_period_set(
    *,
    ctx: str,
    periods: Optional[Set[int]],
    max_period: int,
    errors: List[str],
    warnings: List[str],
    allow_empty: bool,
) -> None:
    if periods is None:
        return
    if not periods and not allow_empty:
        warnings.append(f"{ctx}: conjunto vacío (¿seguro que quieres esto?).")
    bad = [p for p in periods if p < 1 or p > max_period]
    if bad:
        errors.append(f"{ctx}: contiene periodos fuera de 1..{max_period}: {sorted(bad)}.")


def _possible_slots_for_requirement(problem: TimetableProblem, req: CourseRequirement) -> List[Slot]:
    cal = problem.calendar
    slots = list(cal.teaching_slots())

    if problem.config.forbidden_periods_hard and req.forbidden_periods:
        forb = set(req.forbidden_periods)
        slots = [s for s in slots if s.period not in forb]

    if req.teacher_policy == TeacherPolicy.FIXED and req.teacher_id:
        t = problem.index_teachers().get(req.teacher_id)
        if t:
            slots = [s for s in slots if t.is_available(s)]
        return slots

    if req.teacher_policy == TeacherPolicy.CHOOSE:
        teachers = problem.index_teachers()
        pool = list(req.teacher_pool) if req.teacher_pool else [
            t.id for t in problem.teachers if req.subject_id in t.can_teach
        ]
        allowed: List[Slot] = []
        for s in slots:
            if any(teachers.get(tid) and teachers[tid].is_available(s) for tid in pool):
                allowed.append(s)
        return allowed

    return slots


def _validate_capacity_sanity(problem: TimetableProblem, errors: List[str], warnings: List[str]) -> None:
    cal = problem.calendar
    teaching_slots = cal.teaching_slots()
    slots_per_week = len(teaching_slots)

    load_by_group: Dict[str, int] = {}
    for req in problem.requirements:
        load_by_group[req.group_id] = load_by_group.get(req.group_id, 0) + req.periods_per_week

    for g_id, load in load_by_group.items():
        if load > slots_per_week:
            errors.append(
                f"Grupo '{g_id}' requiere {load} sesiones/semana pero solo hay {slots_per_week} slots lectivos."
            )
        elif load == slots_per_week:
            warnings.append(
                f"Grupo '{g_id}' llena el 100% de slots lectivos ({load}/{slots_per_week}). "
                "Esto suele hacer el problema más duro."
            )

    teachers = problem.index_teachers()
    fixed_load: Dict[str, int] = {}
    for req in problem.requirements:
        if req.teacher_policy == TeacherPolicy.FIXED and req.teacher_id:
            fixed_load[req.teacher_id] = fixed_load.get(req.teacher_id, 0) + req.periods_per_week

    for t_id, load in fixed_load.items():
        t = teachers.get(t_id)
        if not t:
            continue
        available = [s for s in teaching_slots if t.is_available(s)]
        if load > len(available):
            errors.append(
                f"Teacher '{t_id}' tiene carga fija {load} pero solo {len(available)} slots disponibles."
            )
        if t.max_periods_per_week is not None and load > t.max_periods_per_week:
            errors.append(
                f"Teacher '{t_id}': carga fija {load} > max_periods_per_week {t.max_periods_per_week}."
            )
        if t.min_periods_per_week is not None and load < t.min_periods_per_week:
            warnings.append(
                f"Teacher '{t_id}': carga fija {load} < min_periods_per_week {t.min_periods_per_week} "
                "(si ese mínimo es hard, esto será imposible)."
            )

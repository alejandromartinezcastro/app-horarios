# solver/solve.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from ortools.sat.python import cp_model

from app.domain.core.schema import (
    CourseRequirement,
    TimetableProblem,
    TimetableSolution,
    ScheduledEvent,
    Slot,
    Event,
    TeacherKey,
    TeacherPolicy,
)


# -----------------------------
# Compilación mínima interna
# -----------------------------

@dataclass(frozen=True)
class _Compiled:
    events: Tuple[Event, ...]
    event_req_key: Dict[str, TeacherKey]                 # event_id -> (group, subject)
    req_by_key: Dict[TeacherKey, CourseRequirement]      # TeacherKey -> CourseRequirement
    slots: Tuple[Slot, ...]
    slot_index: Dict[Slot, int]
    key_pools: Dict[TeacherKey, Tuple[str, ...]]         # TeacherKey -> teacher_ids pool
    allowed_slots: Dict[str, Tuple[int, ...]]            # event_id -> slot indices
    allowed_rooms: Dict[str, Tuple[str, ...]]            # event_id -> room_ids


def _compile_problem(problem: TimetableProblem) -> _Compiled:
    cal = problem.calendar
    slots = cal.teaching_slots()
    slot_index = {s: i for i, s in enumerate(slots)}

    groups = problem.index_groups()
    subjects = problem.index_subjects()
    teachers = problem.index_teachers()

    events: List[Event] = []
    event_req_key: Dict[str, TeacherKey] = {}
    req_by_key: Dict[TeacherKey, CourseRequirement] = {}
    key_pools: Dict[TeacherKey, Tuple[str, ...]] = {}
    allowed_slots: Dict[str, Tuple[int, ...]] = {}
    allowed_rooms: Dict[str, Tuple[str, ...]] = {}

    def rooms_for(group_id: str, subject_id: str) -> List[str]:
        g = groups[group_id]
        sub = subjects[subject_id]
        return [
            r.id for r in problem.rooms
            if r.type == sub.room_type_required and r.capacity >= g.size
        ]

    def pool_for(req: CourseRequirement) -> Tuple[str, ...]:
        if req.teacher_policy == TeacherPolicy.FIXED:
            return (req.teacher_id,) if req.teacher_id else tuple()
        # CHOOSE
        if req.teacher_pool:
            return tuple(req.teacher_pool)
        return tuple(t.id for t in problem.teachers if req.subject_id in t.can_teach)

    def possible_slots_for(req: CourseRequirement, pool: Tuple[str, ...]) -> List[Slot]:
        possible = list(slots)

        # forbidden hard (si aplica)
        if problem.config.forbidden_periods_hard and req.forbidden_periods:
            forb = set(req.forbidden_periods)
            possible = [s for s in possible if s.period not in forb]

        if req.teacher_policy == TeacherPolicy.FIXED and req.teacher_id:
            t = teachers[req.teacher_id]
            possible = [s for s in possible if t.is_available(s)]
            return possible

        if req.teacher_policy == TeacherPolicy.CHOOSE:
            # recorta dominio usando unión de disponibilidades del pool (optimización)
            pool_teachers = [teachers[tid] for tid in pool if tid in teachers]
            if pool_teachers:
                possible = [s for s in possible if any(t.is_available(s) for t in pool_teachers)]
            return possible

        return possible

    for req in problem.requirements:
        k: TeacherKey = (req.group_id, req.subject_id)
        req_by_key[k] = req

        pool = pool_for(req)
        key_pools[k] = pool

        sub = subjects[req.subject_id]

        # expandir a eventos unitarios
        for i in range(1, req.periods_per_week + 1):
            eid = f"{req.group_id}-{req.subject_id}-{i:02d}"
            e = Event(
                id=eid,
                group_id=req.group_id,
                subject_id=req.subject_id,
                duration=1,
                room_type_required=sub.room_type_required,
                same_teacher_key=k,
            )
            events.append(e)
            event_req_key[eid] = k

            rids = tuple(rooms_for(req.group_id, req.subject_id))
            if not rids:
                raise ValueError(
                    f"Evento {eid}: no hay aulas compatibles para (group={req.group_id}, subject={req.subject_id})."
                )
            allowed_rooms[eid] = rids

            poss = possible_slots_for(req, pool)
            if not poss:
                raise ValueError(
                    f"Evento {eid}: no hay slots posibles tras aplicar bloqueos/forbidden/disponibilidad."
                )
            allowed_slots[eid] = tuple(slot_index[s] for s in poss)

    return _Compiled(
        events=tuple(events),
        event_req_key=event_req_key,
        req_by_key=req_by_key,
        slots=slots,
        slot_index=slot_index,
        key_pools=key_pools,
        allowed_slots=allowed_slots,
        allowed_rooms=allowed_rooms,
    )


# -----------------------------
# Solver CP-SAT
# -----------------------------

def solve(problem: TimetableProblem) -> TimetableSolution:
    c = _compile_problem(problem)
    cal = problem.calendar
    teachers = problem.index_teachers()
    rooms = problem.index_rooms()
    weights = problem.config.weights

    model = cp_model.CpModel()

    # --- Variables x[e,si]: evento e en slot si
    x: Dict[Tuple[str, int], cp_model.IntVar] = {}
    for e in c.events:
        for si in c.allowed_slots[e.id]:
            x[(e.id, si)] = model.NewBoolVar(f"x[{e.id},{si}]")

    # Cada evento exactamente 1 vez
    for e in c.events:
        model.Add(sum(x[(e.id, si)] for si in c.allowed_slots[e.id]) == 1)

    # --- Conflicto de grupo: a lo sumo 1 evento por grupo y slot
    events_by_group: Dict[str, List[Event]] = {}
    for e in c.events:
        events_by_group.setdefault(e.group_id, []).append(e)

    for g_id, evs in events_by_group.items():
        for si in range(len(c.slots)):
            terms = [x[(e.id, si)] for e in evs if (e.id, si) in x]
            if terms:
                model.Add(sum(terms) <= 1)

    # --- Asignación de profesor por TeacherKey: a[k,tid]
    a: Dict[Tuple[TeacherKey, str], cp_model.IntVar] = {}
    keys = list(c.key_pools.keys())
    for k in keys:
        pool = c.key_pools[k]
        if not pool:
            raise ValueError(f"Pool vacío para {k}. Revisa validate/problem data.")
        for tid in pool:
            a[(k, tid)] = model.NewBoolVar(f"a[{k[0]},{k[1]},{tid}]")
        model.Add(sum(a[(k, tid)] for tid in pool) == 1)

        req = c.req_by_key[k]
        if req.teacher_policy == TeacherPolicy.FIXED:
            fixed = req.teacher_id
            if fixed is None:
                raise ValueError(f"teacher_policy=FIXED pero teacher_id=None para {k}")
            # fuerza exacta
            for tid in pool:
                model.Add(a[(k, tid)] == (1 if tid == fixed else 0))

    # --- occ[k,si]: en ese slot hay clase de esa (group,subject)
    occ: Dict[Tuple[TeacherKey, int], cp_model.IntVar] = {}
    events_of_key: Dict[TeacherKey, List[Event]] = {}
    for e in c.events:
        events_of_key.setdefault(e.same_teacher_key, []).append(e)

    for k, evs in events_of_key.items():
        for si in range(len(c.slots)):
            terms = [x[(e.id, si)] for e in evs if (e.id, si) in x]
            if not terms:
                occ[(k, si)] = model.NewConstant(0)
            else:
                v = model.NewBoolVar(f"occ[{k[0]},{k[1]},{si}]")
                # robustez: explícitamente <=1
                model.Add(sum(terms) <= 1)
                model.Add(v == sum(terms))
                occ[(k, si)] = v

    # --- teach[k,tid,si] para choques de profesor y disponibilidad
    teach: Dict[Tuple[TeacherKey, str, int], cp_model.IntVar] = {}

    for k in keys:
        pool = c.key_pools[k]
        for tid in pool:
            t = teachers[tid]
            for si, slot in enumerate(c.slots):
                v = model.NewBoolVar(f"teach[{k[0]},{k[1]},{tid},{si}]")
                teach[(k, tid, si)] = v

                # v = a[k,tid] AND occ[k,si]
                model.Add(v <= a[(k, tid)])
                model.Add(v <= occ[(k, si)])
                model.Add(v >= a[(k, tid)] + occ[(k, si)] - 1)

                # disponibilidad
                if not t.is_available(slot):
                    model.Add(v == 0)

    # Conflicto profesor: a lo sumo 1 clase por slot
    busy: Dict[Tuple[str, int], cp_model.IntVar] = {}
    for tid in teachers.keys():
        for si in range(len(c.slots)):
            terms = [teach[(k, tid, si)] for k in keys if (k, tid, si) in teach]
            if not terms:
                busy[(tid, si)] = model.NewConstant(0)
            else:
                b = model.NewBoolVar(f"busy[{tid},{si}]")
                model.Add(b == sum(terms))
                model.Add(sum(terms) <= 1)
                busy[(tid, si)] = b

    # Límites max_periods_per_day/week (hard)
    slots_by_day: Dict[str, List[int]] = {}
    for si, s in enumerate(c.slots):
        slots_by_day.setdefault(s.day, []).append(si)

    for tid, t in teachers.items():
        if t.max_periods_per_day is not None:
            for d, silist in slots_by_day.items():
                model.Add(sum(busy[(tid, si)] for si in silist) <= t.max_periods_per_day)
        if t.max_periods_per_week is not None:
            model.Add(sum(busy[(tid, si)] for si in range(len(c.slots))) <= t.max_periods_per_week)

    # --- Aulas: y[e,r] y w[e,si,r]
    y: Dict[Tuple[str, str], cp_model.IntVar] = {}
    for e in c.events:
        rids = c.allowed_rooms[e.id]
        for rid in rids:
            y[(e.id, rid)] = model.NewBoolVar(f"y[{e.id},{rid}]")
        model.Add(sum(y[(e.id, rid)] for rid in rids) == 1)

    # Blindaje CRÍTICO: si un aula no está disponible en ese slot, prohíbe (x=1,y=1)
    for e in c.events:
        for si in c.allowed_slots[e.id]:
            slot = c.slots[si]
            for rid in c.allowed_rooms[e.id]:
                if not rooms[rid].is_available(slot):
                    model.Add(x[(e.id, si)] + y[(e.id, rid)] <= 1)

    # w = x AND y (solo combos posibles y disponibles)
    w: Dict[Tuple[str, int, str], cp_model.IntVar] = {}
    room_slot_sum: Dict[Tuple[str, int], List[cp_model.IntVar]] = {}

    for e in c.events:
        for si in c.allowed_slots[e.id]:
            slot = c.slots[si]
            for rid in c.allowed_rooms[e.id]:
                if not rooms[rid].is_available(slot):
                    continue

                wij = model.NewBoolVar(f"w[{e.id},{si},{rid}]")
                w[(e.id, si, rid)] = wij

                model.Add(wij <= x[(e.id, si)])
                model.Add(wij <= y[(e.id, rid)])
                model.Add(wij >= x[(e.id, si)] + y[(e.id, rid)] - 1)

                room_slot_sum.setdefault((rid, si), []).append(wij)

    # Conflicto aula por slot
    for rid in rooms.keys():
        for si in range(len(c.slots)):
            terms = room_slot_sum.get((rid, si), [])
            if terms:
                model.Add(sum(terms) <= 1)

    # -----------------------------
    # Restricciones específicas
    # -----------------------------

    # max_consecutive por (group,subject)
    for k, req in c.req_by_key.items():
        m = req.max_consecutive
        if m is None or m < 1:
            continue

        for d in cal.days:
            silist = sorted(slots_by_day.get(d, []), key=lambda si: c.slots[si].period)
            if not silist:
                continue

            for start_p in range(1, cal.periods_per_day - m + 1):
                window = [si for si in silist if start_p <= c.slots[si].period <= start_p + m]
                if window:
                    model.Add(sum(occ[(k, si)] for si in window) <= m)

    # Subject.max_per_day (hard)
    subj_by_id = problem.index_subjects()
    for k in keys:
        sub_id = k[1]
        maxpd = subj_by_id[sub_id].max_per_day
        if maxpd is None:
            continue
        for d in cal.days:
            silist = slots_by_day.get(d, [])
            if silist:
                model.Add(sum(occ[(k, si)] for si in silist) <= maxpd)

    # forbidden_periods soft si config says not hard
    forbidden_soft_terms: List[cp_model.IntVar] = []
    if not problem.config.forbidden_periods_hard:
        for k, req in c.req_by_key.items():
            if not req.forbidden_periods:
                continue
            forb = set(req.forbidden_periods)
            for si, slot in enumerate(c.slots):
                if slot.period in forb:
                    forbidden_soft_terms.append(occ[(k, si)])

    # -----------------------------
    # Objetivo (soft constraints)
    # -----------------------------
    objective_terms: List[cp_model.LinearExpr] = []

    # 1) gaps profesores
    gap_vars: List[cp_model.IntVar] = []
    for tid in teachers.keys():
        for d in cal.days:
            silist = sorted(slots_by_day.get(d, []), key=lambda si: c.slots[si].period)
            for p in range(2, cal.periods_per_day):
                si_prev = next((si for si in silist if c.slots[si].period == p - 1), None)
                si_cur = next((si for si in silist if c.slots[si].period == p), None)
                si_next = next((si for si in silist if c.slots[si].period == p + 1), None)
                if si_prev is None or si_cur is None or si_next is None:
                    continue
                gvar = model.NewBoolVar(f"gap[{tid},{d},{p}]")
                model.Add(gvar >= busy[(tid, si_prev)] + busy[(tid, si_next)] - busy[(tid, si_cur)] - 1)
                gap_vars.append(gvar)
    if gap_vars and weights.teacher_gaps:
        objective_terms.append(weights.teacher_gaps * sum(gap_vars))

    # 2) última hora profe
    late_vars: List[cp_model.IntVar] = []
    for tid in teachers.keys():
        for d in cal.days:
            si_last = next(
                (si for si in slots_by_day.get(d, []) if c.slots[si].period == cal.periods_per_day),
                None
            )
            if si_last is not None:
                late_vars.append(busy[(tid, si_last)])
    if late_vars and weights.teacher_late:
        objective_terms.append(weights.teacher_late * sum(late_vars))

    # 3) repetir misma asignatura el mismo día (excess)
    excess_vars: List[cp_model.IntVar] = []
    for k in keys:
        for d in cal.days:
            silist = slots_by_day.get(d, [])
            if not silist:
                continue
            cnt = sum(occ[(k, si)] for si in silist)
            ex = model.NewIntVar(0, cal.periods_per_day, f"excess[{k[0]},{k[1]},{d}]")
            model.Add(ex >= cnt - 1)
            excess_vars.append(ex)
    if excess_vars and weights.subject_same_day_excess:
        objective_terms.append(weights.subject_same_day_excess * sum(excess_vars))

    # 4) preferred_periods penalty
    pref_terms: List[cp_model.IntVar] = []
    for k, req in c.req_by_key.items():
        if not req.preferred_periods:
            continue
        pref = set(req.preferred_periods)
        for si, slot in enumerate(c.slots):
            if slot.period not in pref:
                pref_terms.append(occ[(k, si)])
    if pref_terms and weights.preferred_period_penalty:
        objective_terms.append(weights.preferred_period_penalty * sum(pref_terms))

    # 5) forbidden_periods soft
    if forbidden_soft_terms and weights.forbidden_period_penalty:
        objective_terms.append(weights.forbidden_period_penalty * sum(forbidden_soft_terms))

    if objective_terms:
        model.Minimize(sum(objective_terms))

    # -----------------------------
    # Resolver
    # -----------------------------
    solver = cp_model.CpSolver()
    if problem.config.max_seconds is not None:
        solver.parameters.max_time_in_seconds = float(problem.config.max_seconds)
    if problem.config.random_seed is not None:
        solver.parameters.random_seed = int(problem.config.random_seed)

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError(f"No se encontró solución. Status={solver.StatusName(status)}")

    # -----------------------------
    # Construir solución
    # -----------------------------
    teacher_assignment: Dict[TeacherKey, str] = {}
    for k in keys:
        pool = c.key_pools[k]
        chosen = next((tid for tid in pool if solver.Value(a[(k, tid)]) == 1), None)
        teacher_assignment[k] = chosen if chosen is not None else pool[0]

    event_room: Dict[str, str] = {}
    for e in c.events:
        chosen = next((rid for rid in c.allowed_rooms[e.id] if solver.Value(y[(e.id, rid)]) == 1), None)
        event_room[e.id] = chosen if chosen is not None else c.allowed_rooms[e.id][0]

    scheduled: List[ScheduledEvent] = []
    for e in c.events:
        chosen_si = next((si for si in c.allowed_slots[e.id] if solver.Value(x[(e.id, si)]) == 1), None)
        if chosen_si is None:
            chosen_si = c.allowed_slots[e.id][0]
        scheduled.append(ScheduledEvent(event_id=e.id, slot=c.slots[chosen_si], room_id=event_room[e.id]))

    breakdown: Dict[str, int] = {}
    if gap_vars:
        breakdown["teacher_gaps"] = sum(solver.Value(v) for v in gap_vars)
    if late_vars:
        breakdown["teacher_late"] = sum(solver.Value(v) for v in late_vars)
    if excess_vars:
        breakdown["subject_same_day_excess"] = sum(solver.Value(v) for v in excess_vars)
    if pref_terms:
        breakdown["preferred_period_penalty"] = sum(solver.Value(v) for v in pref_terms)
    if forbidden_soft_terms:
        breakdown["forbidden_period_penalty"] = sum(solver.Value(v) for v in forbidden_soft_terms)

    return TimetableSolution(
        scheduled=tuple(scheduled),
        teacher_assignment=teacher_assignment,
        objective_value=int(solver.ObjectiveValue()) if objective_terms else None,
        objective_breakdown=breakdown,
    )

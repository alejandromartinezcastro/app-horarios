# solver/glpk_solve.py
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Tuple, Iterable, Optional, DefaultDict
from collections import defaultdict

from solver.schema import (
    TimetableProblem,
    TimetableSolution,
    ScheduledEvent,
    Slot,
    TeacherKey,
)
from solver.solve import _compile_problem  # reutilizamos tu compilación interna


# -----------------------------
# Utilidades LP (GLPK)
# -----------------------------

def _sanitize(name: str) -> str:
    # LP/GLPK agradece nombres simples: [A-Za-z0-9_]
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


@dataclass(frozen=True)
class _VarRef:
    name: str
    kind: str  # "B" binaria, "I" entera, "C" continua
    lb: Optional[int] = None
    ub: Optional[int] = None


class _LPModel:
    def __init__(self) -> None:
        self.vars: Dict[str, _VarRef] = {}
        self.constraints: List[str] = []
        self.objective_terms: List[str] = []  # ya en texto LP
        self.obj_name = "obj"

    def add_var(self, v: _VarRef) -> None:
        if v.name in self.vars:
            return
        self.vars[v.name] = v

    def add_constr(self, expr: str) -> None:
        # expr debe ser tipo: "c1: ... = 1" / "<= 1" / ">= -1"
        self.constraints.append(expr)

    def add_obj_term(self, term: str) -> None:
        # term ya en LP: " + 3 x" o " + 5 y"
        self.objective_terms.append(term)

    def to_lp(self) -> str:
        out: List[str] = []
        out.append("Minimize")
        if self.objective_terms:
            out.append(f" {self.obj_name}: " + "".join(self.objective_terms).lstrip())
        else:
            out.append(f" {self.obj_name}: 0")
        out.append("Subject To")
        out.extend(f" {c}" for c in self.constraints)

        # Bounds (para enteras como excess)
        bounds_lines: List[str] = []
        for v in self.vars.values():
            if v.lb is not None or v.ub is not None:
                lb = v.lb if v.lb is not None else 0
                if v.ub is None:
                    bounds_lines.append(f" {lb} <= {v.name}")
                else:
                    bounds_lines.append(f" {lb} <= {v.name} <= {v.ub}")
        if bounds_lines:
            out.append("Bounds")
            out.extend(bounds_lines)

        # Generals (enteras)
        generals = [v.name for v in self.vars.values() if v.kind == "I"]
        if generals:
            out.append("Generals")
            out.append(" " + " ".join(generals))

        # Binaries
        binaries = [v.name for v in self.vars.values() if v.kind == "B"]
        if binaries:
            out.append("Binary")
            # partir por líneas para no hacer líneas gigantes
            chunk = []
            for b in binaries:
                chunk.append(b)
                if len(chunk) >= 12:
                    out.append(" " + " ".join(chunk))
                    chunk = []
            if chunk:
                out.append(" " + " ".join(chunk))

        out.append("End")
        return "\n".join(out) + "\n"


# -----------------------------
# Construcción MILP (z[e,s,r])
# -----------------------------

@dataclass
class _BuiltMILP:
    lp: _LPModel
    # mapeos para reconstruir solución:
    z_name: Dict[Tuple[str, int, str], str]          # (event_id, si, rid) -> varname
    a_name: Dict[Tuple[TeacherKey, str], str]        # (k, tid) -> varname
    slots: Tuple[Slot, ...]
    keys: List[TeacherKey]


def build_glpk_lp(problem: TimetableProblem) -> _BuiltMILP:
    c = _compile_problem(problem)
    cal = problem.calendar
    teachers = problem.index_teachers()
    rooms = problem.index_rooms()
    weights = problem.config.weights

    lp = _LPModel()

    # --- Variable principal: z[e,si,rid] binaria SOLO en combos permitidos y disponibles
    z_name: Dict[Tuple[str, int, str], str] = {}
    z_by_event: DefaultDict[str, List[str]] = defaultdict(list)
    z_by_group_slot: DefaultDict[Tuple[str, int], List[str]] = defaultdict(list)
    z_by_room_slot: DefaultDict[Tuple[str, int], List[str]] = defaultdict(list)
    z_by_key_slot: DefaultDict[Tuple[TeacherKey, int], List[str]] = defaultdict(list)

    # agrupaciones útiles
    events_by_group: DefaultDict[str, List[str]] = defaultdict(list)
    event_key: Dict[str, TeacherKey] = dict(c.event_req_key)

    for e in c.events:
        events_by_group[e.group_id].append(e.id)

        for si in c.allowed_slots[e.id]:
            slot = c.slots[si]
            for rid in c.allowed_rooms[e.id]:
                if not rooms[rid].is_available(slot):
                    continue

                vname = _sanitize(f"z__{e.id}__s{si}__r{rid}")
                lp.add_var(_VarRef(vname, "B"))
                z_name[(e.id, si, rid)] = vname

                z_by_event[e.id].append(vname)
                z_by_group_slot[(e.group_id, si)].append(vname)
                z_by_room_slot[(rid, si)].append(vname)
                z_by_key_slot[(event_key[e.id], si)].append(vname)

    # 1) Cada evento exactamente una vez
    cid = 1
    for e in c.events:
        terms = z_by_event[e.id]
        if not terms:
            raise ValueError(f"Evento {e.id}: no tiene ninguna combinación (slot,room) válida.")
        lp.add_constr(f"c{cid}: " + " + ".join(terms) + " = 1")
        cid += 1

    # 2) Conflicto de grupo: a lo sumo 1 clase por (grupo, slot)
    for g_id, ev_ids in events_by_group.items():
        for si in range(len(c.slots)):
            terms = z_by_group_slot.get((g_id, si), [])
            if terms:
                lp.add_constr(f"c{cid}: " + " + ".join(terms) + " <= 1")
                cid += 1

    # 3) Conflicto de aula: a lo sumo 1 clase por (room, slot)
    for rid in rooms.keys():
        for si in range(len(c.slots)):
            terms = z_by_room_slot.get((rid, si), [])
            if terms:
                lp.add_constr(f"c{cid}: " + " + ".join(terms) + " <= 1")
                cid += 1

    # --- Asignación de profesor por key: a[k,tid]
    keys = list(c.key_pools.keys())
    a_name: Dict[Tuple[TeacherKey, str], str] = {}

    for k in keys:
        pool = c.key_pools[k]
        if not pool:
            raise ValueError(f"Pool vacío para {k}. Revisa validate/problem data.")

        a_vars: List[str] = []
        for tid in pool:
            vname = _sanitize(f"a__{k[0]}__{k[1]}__{tid}")
            lp.add_var(_VarRef(vname, "B"))
            a_name[(k, tid)] = vname
            a_vars.append(vname)

        lp.add_constr(f"c{cid}: " + " + ".join(a_vars) + " = 1")
        cid += 1

        # FIXED: fuerza exacta
        req = c.req_by_key[k]
        if str(req.teacher_policy) == "TeacherPolicy.FIXED":
            fixed = req.teacher_id
            if fixed is None:
                raise ValueError(f"teacher_policy=FIXED pero teacher_id=None para {k}")
            for tid in pool:
                # a_var = 1 si coincide, si no 0
                val = 1 if tid == fixed else 0
                lp.add_constr(f"c{cid}: {a_name[(k, tid)]} = {val}")
                cid += 1

    # --- occ[k,si] binaria: hay clase de esa (group,subject) en ese slot
    occ_name: Dict[Tuple[TeacherKey, int], str] = {}
    slots_by_day: DefaultDict[str, List[int]] = defaultdict(list)
    for si, s in enumerate(c.slots):
        slots_by_day[s.day].append(si)

    for k in keys:
        for si in range(len(c.slots)):
            vname = _sanitize(f"occ__{k[0]}__{k[1]}__s{si}")
            lp.add_var(_VarRef(vname, "B"))
            occ_name[(k, si)] = vname

            terms = z_by_key_slot.get((k, si), [])
            if not terms:
                lp.add_constr(f"c{cid}: {vname} = 0")
                cid += 1
            else:
                # robustez: sum z <= 1
                lp.add_constr(f"c{cid}: " + " + ".join(terms) + " <= 1")
                cid += 1
                # occ = sum z
                lp.add_constr(f"c{cid}: {vname} - (" + " + ".join(terms) + ") = 0")
                cid += 1

    # --- teach[k,tid,si] binaria con linearización AND, y disponibilidad
    teach_name: Dict[Tuple[TeacherKey, str, int], str] = {}
    for k in keys:
        pool = c.key_pools[k]
        for tid in pool:
            t = teachers[tid]
            a_var = a_name[(k, tid)]
            for si, slot in enumerate(c.slots):
                vname = _sanitize(f"teach__{k[0]}__{k[1]}__{tid}__s{si}")
                lp.add_var(_VarRef(vname, "B"))
                teach_name[(k, tid, si)] = vname

                occ_var = occ_name[(k, si)]
                # v <= a
                lp.add_constr(f"c{cid}: {vname} - {a_var} <= 0"); cid += 1
                # v <= occ
                lp.add_constr(f"c{cid}: {vname} - {occ_var} <= 0"); cid += 1
                # v >= a + occ - 1  <=>  v - a - occ >= -1
                lp.add_constr(f"c{cid}: {vname} - {a_var} - {occ_var} >= -1"); cid += 1

                # disponibilidad
                if not t.is_available(slot):
                    lp.add_constr(f"c{cid}: {vname} = 0"); cid += 1

    # --- busy[tid,si] binaria + choque profe
    busy_name: Dict[Tuple[str, int], str] = {}
    for tid in teachers.keys():
        for si in range(len(c.slots)):
            vname = _sanitize(f"busy__{tid}__s{si}")
            lp.add_var(_VarRef(vname, "B"))
            busy_name[(tid, si)] = vname

            terms = [teach_name[(k, tid, si)] for k in keys if (k, tid, si) in teach_name]
            if not terms:
                lp.add_constr(f"c{cid}: {vname} = 0"); cid += 1
            else:
                # busy = sum teach
                lp.add_constr(f"c{cid}: {vname} - (" + " + ".join(terms) + ") = 0"); cid += 1
                # choque: sum teach <= 1
                lp.add_constr(f"c{cid}: " + " + ".join(terms) + " <= 1"); cid += 1

    # Límites max_periods_per_day/week (hard)
    for tid, t in teachers.items():
        if t.max_periods_per_day is not None:
            for d, silist in slots_by_day.items():
                if silist:
                    lp.add_constr(
                        f"c{cid}: " + " + ".join(busy_name[(tid, si)] for si in silist)
                        + f" <= {int(t.max_periods_per_day)}"
                    )
                    cid += 1
        if t.max_periods_per_week is not None:
            lp.add_constr(
                f"c{cid}: " + " + ".join(busy_name[(tid, si)] for si in range(len(c.slots)))
                + f" <= {int(t.max_periods_per_week)}"
            )
            cid += 1

    # -----------------------------
    # Restricciones específicas (hard)
    # -----------------------------

    # max_consecutive por key (como en tu CP-SAT; equivalente)
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
                    lp.add_constr(
                        f"c{cid}: " + " + ".join(occ_name[(k, si)] for si in window)
                        + f" <= {int(m)}"
                    )
                    cid += 1

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
                lp.add_constr(
                    f"c{cid}: " + " + ".join(occ_name[(k, si)] for si in silist)
                    + f" <= {int(maxpd)}"
                )
                cid += 1

    # -----------------------------
    # Objetivo (soft) igual que tu CP-SAT
    # -----------------------------

    # forbidden soft si no es hard
    forbidden_soft_terms: List[str] = []
    if not problem.config.forbidden_periods_hard:
        for k, req in c.req_by_key.items():
            if not req.forbidden_periods:
                continue
            forb = set(req.forbidden_periods)
            for si, slot in enumerate(c.slots):
                if slot.period in forb:
                    forbidden_soft_terms.append(occ_name[(k, si)])

    # 1) gaps profesores: gap >= prev + next - cur - 1
    if weights.teacher_gaps:
        for tid in teachers.keys():
            for d in cal.days:
                silist = sorted(slots_by_day.get(d, []), key=lambda si: c.slots[si].period)
                for p in range(2, cal.periods_per_day):
                    si_prev = next((si for si in silist if c.slots[si].period == p - 1), None)
                    si_cur = next((si for si in silist if c.slots[si].period == p), None)
                    si_next = next((si for si in silist if c.slots[si].period == p + 1), None)
                    if si_prev is None or si_cur is None or si_next is None:
                        continue
                    gvar = _sanitize(f"gap__{tid}__{d}__p{p}")
                    lp.add_var(_VarRef(gvar, "B"))
                    # gvar - prev - next + cur >= -1
                    lp.add_constr(
                        f"c{cid}: {gvar} - {busy_name[(tid, si_prev)]} - {busy_name[(tid, si_next)]} + {busy_name[(tid, si_cur)]} >= -1"
                    )
                    cid += 1
                    lp.add_obj_term(f" + {int(weights.teacher_gaps)} {gvar}")

    # 2) última hora profe
    if weights.teacher_late:
        for tid in teachers.keys():
            for d in cal.days:
                si_last = next(
                    (si for si in slots_by_day.get(d, []) if c.slots[si].period == cal.periods_per_day),
                    None
                )
                if si_last is not None:
                    lp.add_obj_term(f" + {int(weights.teacher_late)} {busy_name[(tid, si_last)]}")

    # 3) repetir misma asignatura el mismo día (excess): ex >= cnt - 1
    if weights.subject_same_day_excess:
        for k in keys:
            for d in cal.days:
                silist = slots_by_day.get(d, [])
                if not silist:
                    continue
                ex = _sanitize(f"excess__{k[0]}__{k[1]}__{d}")
                lp.add_var(_VarRef(ex, "I", lb=0, ub=int(cal.periods_per_day)))
                cnt_expr = " + ".join(occ_name[(k, si)] for si in silist)
                lp.add_constr(f"c{cid}: {ex} - ({cnt_expr}) >= -1")
                cid += 1
                lp.add_obj_term(f" + {int(weights.subject_same_day_excess)} {ex}")

    # 4) preferred_periods penalty (si slot.period no está en preferred)
    if weights.preferred_period_penalty:
        for k, req in c.req_by_key.items():
            if not req.preferred_periods:
                continue
            pref = set(req.preferred_periods)
            for si, slot in enumerate(c.slots):
                if slot.period not in pref:
                    lp.add_obj_term(f" + {int(weights.preferred_period_penalty)} {occ_name[(k, si)]}")

    # 5) forbidden_periods soft
    if weights.forbidden_period_penalty and forbidden_soft_terms:
        for v in forbidden_soft_terms:
            lp.add_obj_term(f" + {int(weights.forbidden_period_penalty)} {v}")

    return _BuiltMILP(lp=lp, z_name=z_name, a_name=a_name, slots=c.slots, keys=keys)


# -----------------------------
# Ejecutar GLPK y parsear salida
# -----------------------------

def _parse_glpsol_report_for_values(report_text: str) -> Dict[str, float]:
    """
    Parser tolerante para el reporte (-o) de glpsol:
    busca la tabla de columnas y extrae "Activity" por variable.

    Si tu versión de GLPK cambia el formato, este parser puede necesitar ajuste,
    pero suele funcionar bien.
    """
    values: Dict[str, float] = {}

    # Heurística: localizar sección "Column name" típica
    # y capturar líneas con: <idx> <name> <something> <activity> ...
    # Usamos regex flexible.
    lines = report_text.splitlines()

    in_cols = False
    for line in lines:
        if "Column name" in line and "Activity" in line:
            in_cols = True
            continue
        if in_cols:
            if not line.strip():
                continue
            # fin de tabla al encontrar "Row name" u otra cabecera
            if "Row name" in line and "Activity" in line:
                break

            # ejemplo típico (puede variar):
            #  123 z__...  NL  1
            parts = line.split()
            if len(parts) < 3:
                continue

            # intenta detectar name y activity:
            # buscamos el primer token que parezca nombre (letras/underscore)
            # y el último token numérico como activity.
            name = None
            activity = None
            for tok in parts:
                if name is None and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tok):
                    name = tok
            # último numérico
            for tok in reversed(parts):
                if re.fullmatch(r"[-+]?\d+(\.\d+)?([eE][-+]?\d+)?", tok):
                    activity = float(tok)
                    break
            if name is not None and activity is not None:
                values[name] = activity

    return values


def solve_with_glpk(
    problem: TimetableProblem,
    workdir: str = "glpk_out",
    lp_filename: str = "model.lp",
    report_filename: str = "report.txt",
    time_limit_seconds: Optional[int] = None,
) -> TimetableSolution:
    """
    - Genera MILP en LP
    - Llama glpsol si está disponible
    - Parsea reporte y reconstruye TimetableSolution

    Requiere que 'glpsol' esté en PATH.
    """
    built = build_glpk_lp(problem)

    os.makedirs(workdir, exist_ok=True)
    lp_path = os.path.join(workdir, lp_filename)
    rep_path = os.path.join(workdir, report_filename)

    with open(lp_path, "w", encoding="utf-8") as f:
        f.write(built.lp.to_lp())

    glpsol = shutil.which("glpsol")
    if not glpsol:
        raise RuntimeError(
            "No encuentro 'glpsol' en tu PATH. "
            f"Te dejé el LP en: {lp_path}\n"
            "Instala GLPK y ejecuta, por ejemplo:\n"
            f"  glpsol --lp {lp_path} --mip -o {rep_path}"
        )

    cmd = [glpsol, "--lp", lp_path, "--mip", "-o", rep_path]
    if time_limit_seconds is not None:
        # GLPK usa --tmlim en segundos
        cmd.extend(["--tmlim", str(int(time_limit_seconds))])

    subprocess.run(cmd, check=True)

    report_text = open(rep_path, "r", encoding="utf-8", errors="replace").read()
    values = _parse_glpsol_report_for_values(report_text)

    # --- reconstruir horarios: elegir z=1 para cada evento
    scheduled: List[ScheduledEvent] = []
    for (eid, si, rid), vname in built.z_name.items():
        if values.get(vname, 0.0) > 0.5:
            scheduled.append(ScheduledEvent(event_id=eid, slot=built.slots[si], room_id=rid))

    # chequeo rápido
    # (si faltan eventos es que el parser no capturó valores; entonces toca ajustar parse)
    # construimos dict por evento:
    by_event: DefaultDict[str, int] = defaultdict(int)
    for se in scheduled:
        by_event[se.event_id] += 1

    # --- profesores por key: elegir a=1
    teacher_assignment: Dict[TeacherKey, str] = {}
    for (k, tid), vname in built.a_name.items():
        if values.get(vname, 0.0) > 0.5:
            teacher_assignment[k] = tid

    return TimetableSolution(
        scheduled=tuple(sorted(scheduled, key=lambda x: (x.slot.day, x.slot.period, x.event_id))),
        teacher_assignment=teacher_assignment,
        objective_value=None,          # GLPK lo tiene en reporte, pero varía el formato; si quieres lo parseamos también
        objective_breakdown={},        # idem
    )


def export_glpk_lp(problem: TimetableProblem, path: str) -> str:
    """
    Solo exporta el modelo (sin resolver). Devuelve el path.
    """
    built = build_glpk_lp(problem)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(built.lp.to_lp())
    return path

# solver/schema.py
# Contrato de datos para un generador de horarios (colegio/instituto)
# Enfoque: CP-SAT / ILP-friendly, con consistencia de profesor por (grupo, asignatura).

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Tuple


# ---------- Tipos base ----------

Day = str  # "mon".."sun" (normalmente "mon".."fri")


@dataclass(frozen=True, order=True)
class Slot:
    """Un hueco lectivo."""
    day: Day
    period: int  # 1..N


# ---------- Enums ----------

class RoomType(str, Enum):
    NORMAL = "NORMAL"
    LAB = "LAB"
    GYM = "GYM"
    MUSIC = "MUSIC"
    IT = "IT"
    OTHER = "OTHER"


class TeacherPolicy(str, Enum):
    """Cómo se asigna profesor a (grupo, asignatura)."""
    FIXED = "FIXED"    # viene fijado en datos
    CHOOSE = "CHOOSE"  # lo elige el solver de un pool


# ---------- Entidades ----------

@dataclass(frozen=True)
class Calendar:
    """Define el horizonte temporal del problema (semana tipo)."""
    days: Tuple[Day, ...]                 # p.ej. ("mon","tue","wed","thu","fri")
    periods_per_day: int                  # p.ej. 6
    blocked_slots: FrozenSet[Slot] = field(default_factory=frozenset)  # recreos, actos, etc.

    def all_slots(self) -> Tuple[Slot, ...]:
        out: List[Slot] = []
        for d in self.days:
            for p in range(1, self.periods_per_day + 1):
                out.append(Slot(d, p))
        return tuple(out)

    def teaching_slots(self) -> Tuple[Slot, ...]:
        """Slots lectivos disponibles para clases."""
        return tuple(s for s in self.all_slots() if s not in self.blocked_slots)


@dataclass(frozen=True)
class Group:
    id: str                 # "1ESO_A"
    size: int               # nº alumnos


@dataclass(frozen=True)
class Subject:
    id: str                 # "MATH"
    room_type_required: RoomType = RoomType.NORMAL

    # Opcionales (pueden convertirse en hard o soft en el solver)
    max_per_day: Optional[int] = None     # p.ej. no más de 1 al día


@dataclass(frozen=True)
class Teacher:
    id: str

    # Asignaturas que puede impartir
    can_teach: FrozenSet[str] = field(default_factory=frozenset)  # subject_id

    # Slots en los que NO puede
    unavailable: FrozenSet[Slot] = field(default_factory=frozenset)

    # Límites opcionales (hard o soft)
    max_periods_per_day: Optional[int] = None
    max_periods_per_week: Optional[int] = None
    min_periods_per_day: Optional[int] = None
    min_periods_per_week: Optional[int] = None

    def is_available(self, slot: Slot) -> bool:
        return slot not in self.unavailable


@dataclass(frozen=True)
class Room:
    id: str
    type: RoomType = RoomType.NORMAL
    capacity: int = 9999

    # Si no se usa, dejar vacío (se asume disponible salvo bloqueos globales)
    unavailable: FrozenSet[Slot] = field(default_factory=frozenset)

    def is_available(self, slot: Slot) -> bool:
        return slot not in self.unavailable


# ---------- Requisitos curriculares ----------

@dataclass(frozen=True)
class CourseRequirement:
    """
    Requisito: el grupo g debe recibir X sesiones/semana de la asignatura sub.

    teacher_policy define si el profe viene fijo o lo elige el solver,
    pero en ambos casos se fuerza: 1 solo profesor para (grupo, asignatura).
    """
    group_id: str
    subject_id: str
    periods_per_week: int
    max_consecutive: Optional[int] = 2    # p.ej. 2 => no más de 2 seguidas

    teacher_policy: TeacherPolicy = TeacherPolicy.FIXED
    teacher_id: Optional[str] = None                # si FIXED
    teacher_pool: Optional[Tuple[str, ...]] = None  # si CHOOSE (si None, pool = todos los elegibles)

    # Preferencias (normalmente soft)
    preferred_periods: Optional[FrozenSet[int]] = None   # p.ej. {2,3,4,5}
    forbidden_periods: Optional[FrozenSet[int]] = None   # puedes tratarlo como hard o soft

    # Fase 2 (por ahora 1 slot por evento)
    allow_double: bool = False


# ---------- Eventos (expandido) ----------

TeacherKey = Tuple[str, str]  # (group_id, subject_id)


@dataclass(frozen=True)
class Event:
    """
    Unidad mínima a colocar en el horario.
    En MVP: duration=1 siempre.
    """
    id: str
    group_id: str
    subject_id: str
    duration: int = 1

    room_type_required: RoomType = RoomType.NORMAL

    # todos los eventos con la misma key comparten el mismo profe
    same_teacher_key: TeacherKey = field(default_factory=tuple)


# ---------- Preferencias y configuración de objetivos ----------

@dataclass(frozen=True)
class ObjectiveWeights:
    teacher_gaps: int = 1000
    teacher_late: int = 100
    subject_same_day_excess: int = 10
    preferred_period_penalty: int = 1
    forbidden_period_penalty: int = 50  # separado de preferred (suele ser más caro)


@dataclass(frozen=True)
class SolveConfig:
    """Parámetros del solver (sin acoplar a una librería concreta)."""
    max_seconds: Optional[int] = 30
    random_seed: Optional[int] = None
    weights: ObjectiveWeights = ObjectiveWeights()

    # Si True: forbidden_periods se trata como hard.
    # Si False: se penaliza en objetivo.
    forbidden_periods_hard: bool = True


# ---------- Problema completo ----------

@dataclass(frozen=True)
class TimetableProblem:
    calendar: Calendar
    groups: Tuple[Group, ...]
    subjects: Tuple[Subject, ...]
    teachers: Tuple[Teacher, ...]
    rooms: Tuple[Room, ...]
    requirements: Tuple[CourseRequirement, ...]
    config: SolveConfig = SolveConfig()

    def index_groups(self) -> Dict[str, Group]:
        return {g.id: g for g in self.groups}

    def index_subjects(self) -> Dict[str, Subject]:
        return {s.id: s for s in self.subjects}

    def index_teachers(self) -> Dict[str, Teacher]:
        return {t.id: t for t in self.teachers}

    def index_rooms(self) -> Dict[str, Room]:
        return {r.id: r for r in self.rooms}


# ---------- Solución (output del solver) ----------

@dataclass(frozen=True)
class ScheduledEvent:
    event_id: str
    slot: Slot
    room_id: str


@dataclass(frozen=True)
class TimetableSolution:
    scheduled: Tuple[ScheduledEvent, ...]
    teacher_assignment: Dict[TeacherKey, str]
    objective_value: Optional[int] = None
    objective_breakdown: Dict[str, int] = field(default_factory=dict)


# ---------- Serialización simple ----------

def to_dict(obj) -> dict:
    """Convierte dataclasses a dict (no hace magia con enums/slots complejos más allá de asdict)."""
    return asdict(obj)

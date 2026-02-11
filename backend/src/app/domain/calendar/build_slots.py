from app.domain.core.schema import Calendar, Slot



def build_slots(calendar: Calendar) -> tuple[Slot, ...]:
    return calendar.teaching_slots()

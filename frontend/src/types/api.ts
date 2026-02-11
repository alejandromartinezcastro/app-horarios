export type SlotDto = {
  day: string;
  period: number;
};

export type ScheduledEventDto = {
  event_id: string;
  slot: SlotDto;
  room_id: string;
};

export type TeacherAssignmentDto = {
  group_id: string;
  subject_id: string;
  teacher_id: string;
};

export type SolveResponse = {
  scheduled: ScheduledEventDto[];
  teacher_assignment: TeacherAssignmentDto[];
  objective_value?: number | null;
  objective_breakdown: Record<string, number>;
};

export type ProjectSummary = {
  id: string;
  name: string;
};

export type ProjectDetail = ProjectSummary & {
  problem: Record<string, unknown>;
};

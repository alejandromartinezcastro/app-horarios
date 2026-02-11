import { apiRequest } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import type { ProjectDetail, ProjectSummary, SolveResponse } from '@/types/api';

export const api = {
  listProjects: () => apiRequest<ProjectSummary[]>(endpoints.projects),
  getProject: (id: string) => apiRequest<ProjectDetail>(`${endpoints.projects}/${id}`),
  createProject: (payload: { name: string; problem: Record<string, unknown> }) =>
    apiRequest<ProjectDetail>(endpoints.projects, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  solve: (problem: Record<string, unknown>) =>
    apiRequest<SolveResponse>(endpoints.solve, {
      method: 'POST',
      body: JSON.stringify({ problem }),
    }),
};

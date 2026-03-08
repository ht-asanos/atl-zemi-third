import { apiClient, ApiError } from './client'
import type { CreateGoalRequest, GoalResponse } from '@/types/goal'

export async function createGoal(
  token: string,
  data: CreateGoalRequest
): Promise<GoalResponse> {
  return apiClient<GoalResponse>('/goals', {
    method: 'POST',
    body: JSON.stringify(data),
  }, token)
}

export async function getMyGoal(
  token: string
): Promise<GoalResponse | null> {
  try {
    return await apiClient<GoalResponse>('/goals/me', {}, token)
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

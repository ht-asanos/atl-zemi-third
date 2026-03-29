import { apiClient } from './client'
import type {
  AdaptationResponse,
  CreateMealLogRequest,
  CreateFeedbackRequest,
  CreateWorkoutLogRequest,
  FeedbackEventDetailResponse,
  FeedbackTagResponse,
  MealLogResponse,
  WorkoutLogResponse,
} from '@/types/log'

export async function createMealLog(
  token: string,
  data: CreateMealLogRequest
): Promise<MealLogResponse> {
  return apiClient<MealLogResponse>('/logs/meal', {
    method: 'POST',
    body: JSON.stringify(data),
  }, token)
}

export async function getMealLogs(
  token: string,
  logDate: string
): Promise<{ logs: MealLogResponse[] }> {
  return apiClient<{ logs: MealLogResponse[] }>(
    `/logs/meal?log_date=${logDate}`,
    {},
    token
  )
}

export async function createWorkoutLog(
  token: string,
  data: CreateWorkoutLogRequest
): Promise<WorkoutLogResponse> {
  return apiClient<WorkoutLogResponse>('/logs/workout', {
    method: 'POST',
    body: JSON.stringify(data),
  }, token)
}

export async function getWorkoutLogs(
  token: string,
  logDate: string
): Promise<{ logs: WorkoutLogResponse[] }> {
  return apiClient<{ logs: WorkoutLogResponse[] }>(
    `/logs/workout?log_date=${logDate}`,
    {},
    token
  )
}

export async function submitFeedback(
  token: string,
  data: CreateFeedbackRequest
): Promise<AdaptationResponse> {
  return apiClient<AdaptationResponse>('/feedback', {
    method: 'POST',
    body: JSON.stringify(data),
  }, token)
}

export async function getFeedbackTags(
  token: string,
  planId: string
): Promise<{ tags: FeedbackTagResponse[] }> {
  return apiClient<{ tags: FeedbackTagResponse[] }>(
    `/feedback/${planId}`,
    {},
    token
  )
}

export async function getFeedbackHistory(
  token: string,
  limit = 20
): Promise<FeedbackEventDetailResponse[]> {
  return apiClient<FeedbackEventDetailResponse[]>(
    `/feedback/history?limit=${limit}`,
    {},
    token
  )
}

export async function getFeedbackHistoryDetail(
  token: string,
  eventId: string
): Promise<FeedbackEventDetailResponse> {
  return apiClient<FeedbackEventDetailResponse>(
    `/feedback/history/${eventId}`,
    {},
    token
  )
}

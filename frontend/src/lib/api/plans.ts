import { apiClient } from './client'
import type { DailyPlanResponse, PatchMealRequest, ShoppingListResponse, WeeklyPlanRequest, WeeklyPlanResponse } from '@/types/plan'

export async function createWeeklyPlan(
  token: string,
  data: WeeklyPlanRequest
): Promise<WeeklyPlanResponse> {
  return apiClient<WeeklyPlanResponse>('/plans/weekly', {
    method: 'POST',
    body: JSON.stringify(data),
  }, token)
}

export async function getWeeklyPlans(
  token: string,
  startDate: string
): Promise<WeeklyPlanResponse> {
  return apiClient<WeeklyPlanResponse>(
    `/plans/weekly?start_date=${startDate}`,
    {},
    token
  )
}

export async function getShoppingList(
  token: string,
  startDate: string
): Promise<ShoppingListResponse> {
  return apiClient<ShoppingListResponse>(
    `/plans/weekly/shopping-list?start_date=${startDate}`,
    {},
    token
  )
}

export async function patchRecipe(
  token: string,
  planId: string
): Promise<DailyPlanResponse> {
  return apiClient<DailyPlanResponse>(`/plans/${planId}/recipe`, {
    method: 'PATCH',
  }, token)
}

export async function patchMeal(
  token: string,
  planId: string,
  data: PatchMealRequest
): Promise<DailyPlanResponse> {
  return apiClient<DailyPlanResponse>(`/plans/${planId}/meal`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }, token)
}

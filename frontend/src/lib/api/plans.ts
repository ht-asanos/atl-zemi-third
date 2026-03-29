import { apiClient } from './client'
import type {
  DailyPlanResponse,
  PatchMealRequest,
  PatchRecipeRequest,
  SetShoppingListCheckRequest,
  ShoppingListChecksResponse,
  ShoppingListResponse,
  TrainingEquipment,
  TrainingSkillTreeResponse,
  WeeklyPlanRequest,
  WeeklyPlanResponse,
} from '@/types/plan'

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

export async function getShoppingListChecks(
  token: string,
  startDate: string
): Promise<ShoppingListChecksResponse> {
  return apiClient<ShoppingListChecksResponse>(
    `/plans/weekly/shopping-list/checks?start_date=${startDate}`,
    {},
    token
  )
}

export async function setShoppingListCheck(
  token: string,
  data: SetShoppingListCheckRequest
): Promise<void> {
  await apiClient<void>(
    '/plans/weekly/shopping-list/checks',
    {
      method: 'POST',
      body: JSON.stringify(data),
    },
    token
  )
}

export async function patchRecipe(
  token: string,
  planId: string,
  data?: PatchRecipeRequest
): Promise<DailyPlanResponse> {
  return apiClient<DailyPlanResponse>(`/plans/${planId}/recipe`, {
    method: 'PATCH',
    body: data ? JSON.stringify(data) : undefined,
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

export async function getTrainingSkillTree(
  token: string,
  startDate: string,
  availableEquipment: TrainingEquipment[] = ['none']
): Promise<TrainingSkillTreeResponse> {
  const params = new URLSearchParams({ start_date: startDate })
  for (const equipment of availableEquipment) {
    params.append('available_equipment', equipment)
  }
  return apiClient<TrainingSkillTreeResponse>(
    `/plans/training-skill-tree?${params.toString()}`,
    {},
    token
  )
}

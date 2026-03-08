import { apiClient } from './client'
import type { FoodItem } from '@/types/food'

export async function getStapleFoods(token: string): Promise<FoodItem[]> {
  return apiClient<FoodItem[]>('/foods/staples', {}, token)
}

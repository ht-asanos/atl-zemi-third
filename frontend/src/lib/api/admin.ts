import type {
  MextFoodSearchResponse,
  ReviewListResponse,
  ReviewUpdateRequest,
} from '@/types/admin'
import { apiClient } from './client'

export async function getReviewIngredients(
  token: string,
  page: number = 1,
  perPage: number = 20
): Promise<ReviewListResponse> {
  return apiClient<ReviewListResponse>(
    `/admin/review/ingredients?page=${page}&per_page=${perPage}`,
    {},
    token
  )
}

export async function searchMextFoods(
  token: string,
  q: string
): Promise<MextFoodSearchResponse> {
  return apiClient<MextFoodSearchResponse>(
    `/admin/mext-foods/search?q=${encodeURIComponent(q)}`,
    {},
    token
  )
}

export async function updateIngredientMatch(
  token: string,
  id: string,
  body: ReviewUpdateRequest
): Promise<{ ok: boolean; recipe_id: string }> {
  return apiClient<{ ok: boolean; recipe_id: string }>(
    `/admin/review/ingredients/${id}`,
    { method: 'PATCH', body: JSON.stringify(body) },
    token
  )
}

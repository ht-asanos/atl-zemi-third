import { apiClient } from './client'

export interface FavoriteResponse {
  recipe_id: string
  created_at: string
}

export async function getFavorites(token: string): Promise<FavoriteResponse[]> {
  return apiClient<FavoriteResponse[]>('/recipes/favorites', {}, token)
}

export async function addFavorite(token: string, recipeId: string): Promise<FavoriteResponse> {
  return apiClient<FavoriteResponse>(`/recipes/${recipeId}/favorite`, {
    method: 'POST',
  }, token)
}

export async function removeFavorite(token: string, recipeId: string): Promise<void> {
  await apiClient<void>(`/recipes/${recipeId}/favorite`, { method: 'DELETE' }, token)
}

export interface RefreshResult {
  fetched: number
  upserted: number
  errors: number
}

export interface BackfillResult {
  processed: number
  matched: number
  errors: number
}

export async function refreshRecipes(token: string): Promise<RefreshResult> {
  return apiClient<RefreshResult>('/recipes/refresh', {
    method: 'POST',
  }, token)
}

export async function backfillRecipes(token: string): Promise<BackfillResult> {
  return apiClient<BackfillResult>('/recipes/backfill', {
    method: 'POST',
  }, token)
}

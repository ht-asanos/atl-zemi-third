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

// --- YouTube Admin Types ---

export interface RecipeDraftIngredient {
  ingredient_name: string
  amount_text: string | null
}

export interface RecipeDraftStep {
  step_no: number
  text: string
  est_minutes: number | null
}

export interface RecipeDraft {
  title: string
  servings: number
  cooking_minutes: number | null
  ingredients: RecipeDraftIngredient[]
  steps: RecipeDraftStep[]
  tags: string[]
}

export interface YoutubeExtractResponse {
  video_id: string
  video_title: string
  transcript_quality: Record<string, unknown>
  recipe_draft: RecipeDraft
}

export interface YoutubeRegisterResponse {
  recipe_id: string
  title: string
  nutrition_status: string
}

export interface YoutubeRecipeItem {
  id: string
  title: string
  youtube_video_id: string | null
  nutrition_status: string | null
  steps_status: string | null
  created_at: string | null
}

export interface YoutubeRecipeListResponse {
  items: YoutubeRecipeItem[]
  total: number
  page: number
  per_page: number
}

export interface BatchAdaptVideoResult {
  video_id: string
  video_title: string
  status: string
  recipe_id: string | null
  recipe_title: string | null
  error: string | null
}

export interface BatchAdaptResponse {
  channel_handle: string
  source_query: string
  target_staple: string
  videos_found: number
  videos_processed: number
  succeeded: number
  failed: number
  skipped: number
  results: BatchAdaptVideoResult[]
}

// --- YouTube Admin API Functions ---

export async function extractYoutubeRecipe(
  token: string,
  url: string,
  stapleName?: string
): Promise<YoutubeExtractResponse> {
  return apiClient<YoutubeExtractResponse>('/admin/youtube/extract', {
    method: 'POST',
    body: JSON.stringify({ url, staple_name: stapleName || null }),
  }, token)
}

export async function registerYoutubeRecipe(
  token: string,
  videoId: string,
  recipeData: RecipeDraft
): Promise<YoutubeRegisterResponse> {
  return apiClient<YoutubeRegisterResponse>('/admin/youtube/register', {
    method: 'POST',
    body: JSON.stringify({ video_id: videoId, recipe_data: recipeData }),
  }, token)
}

export async function listYoutubeRecipes(
  token: string,
  page: number = 1,
  perPage: number = 20
): Promise<YoutubeRecipeListResponse> {
  return apiClient<YoutubeRecipeListResponse>(
    `/admin/youtube/recipes?page=${page}&per_page=${perPage}`,
    {},
    token
  )
}

export async function batchAdaptYoutubeRecipes(
  token: string,
  body: {
    channel_handle: string
    source_query: string
    target_staple: string
    max_results: number
  }
): Promise<BatchAdaptResponse> {
  return apiClient<BatchAdaptResponse>(
    '/admin/youtube/batch-adapt',
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    token
  )
}

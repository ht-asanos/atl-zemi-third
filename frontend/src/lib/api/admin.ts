import type {
  MextFoodSearchResponse,
  AdminTrainingProgressionGraphResponse,
  ReviewListResponse,
  ReviewUpdateRequest,
  TrainingProgressionApplyPresetsResponse,
  TrainingProgressionIngestResponse,
  TrainingProgressionReviewActionRequest,
  TrainingProgressionReviewListResponse,
  TrainingProgressionSourceListResponse,
} from '@/types/admin'
import type { Exercise } from '@/types/plan'
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

export async function listTrainingProgressionSources(
  token: string,
  limit: number = 50
): Promise<TrainingProgressionSourceListResponse> {
  return apiClient<TrainingProgressionSourceListResponse>(
    `/admin/training-progressions/sources?limit=${limit}`,
    {},
    token
  )
}

export async function ingestTrainingProgressions(
  token: string,
  body: {
    channel_handle: string
    title_keyword: string
    max_results: number
  }
): Promise<TrainingProgressionIngestResponse> {
  return apiClient<TrainingProgressionIngestResponse>(
    '/admin/training-progressions/ingest',
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    token
  )
}

export async function listTrainingProgressionReview(
  token: string,
  status: string = 'pending',
  limit: number = 100
): Promise<TrainingProgressionReviewListResponse> {
  return apiClient<TrainingProgressionReviewListResponse>(
    `/admin/training-progressions/review?status=${encodeURIComponent(status)}&limit=${limit}`,
    {},
    token
  )
}

export async function reviewTrainingProgression(
  token: string,
  edgeId: string,
  body: TrainingProgressionReviewActionRequest
): Promise<{ status: string }> {
  return apiClient<{ status: string }>(
    `/admin/training-progressions/review/${edgeId}`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    token
  )
}

export async function applyTrainingProgressionPresets(
  token: string
): Promise<TrainingProgressionApplyPresetsResponse> {
  return apiClient<TrainingProgressionApplyPresetsResponse>(
    '/admin/training-progressions/apply-presets',
    { method: 'POST' },
    token
  )
}

export async function listTrainingProgressionCatalog(
  token: string
): Promise<Exercise[]> {
  return apiClient<Exercise[]>(
    '/admin/training-progressions/catalog',
    {},
    token
  )
}

export async function getTrainingProgressionGraph(
  token: string,
  status: string = 'approved',
  goalType: string = 'all',
  limit: number = 200
): Promise<AdminTrainingProgressionGraphResponse> {
  return apiClient<AdminTrainingProgressionGraphResponse>(
    `/admin/training-progressions/graph?status=${encodeURIComponent(status)}&goal_type=${encodeURIComponent(goalType)}&limit=${limit}`,
    {},
    token
  )
}

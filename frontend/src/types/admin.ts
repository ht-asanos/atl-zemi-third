export interface ReviewIngredientItem {
  id: string
  recipe_id: string
  recipe_title: string
  ingredient_name: string
  amount_text: string | null
  current_mext_food_id: string | null
  current_mext_food_name: string | null
  match_confidence: number | null
  manual_review_needed: boolean
  is_nutrition_calculated: boolean
}

export interface ReviewListResponse {
  items: ReviewIngredientItem[]
  total: number
  page: number
  per_page: number
}

export interface ReviewUpdateRequest {
  mext_food_id: string | null
  approved: boolean
}

export interface MextFoodSearchItem {
  id: string
  mext_food_id: string
  name: string
  category_name: string
  kcal_per_100g: number
  protein_g_per_100g: number
}

export interface MextFoodSearchResponse {
  items: MextFoodSearchItem[]
}

export interface TrainingProgressionPresetReview {
  from_exercise_id: string
  from_reps: number
  to_exercise_id: string
  to_reps: number
  goal_scope: string[]
  review_note?: string | null
  add_aliases: string[]
}

export interface TrainingProgressionSourceItem {
  id: string
  platform: string
  channel_handle: string
  channel_id?: string | null
  video_id: string
  video_title: string
  video_url: string
  published_at?: string | null
  title_query?: string | null
  transcript_language?: string | null
  transcript_quality_json: Record<string, unknown>
  ingest_status: string
  raw_extraction_json?: unknown
  created_at: string
}

export interface TrainingProgressionSourceDiagnostics {
  quality_score?: number | null
  naturalization_applied?: boolean
  naturalization_reason?: string | null
  naturalizer_model?: string | null
  transcript_changed?: boolean
  transcript_original_preview?: string
  transcript_naturalized_preview?: string
  extractor_model?: string | null
  extraction_count?: number
  empty_reason_hint?: string | null
}

export interface TrainingProgressionSourceExtractionPayload {
  diagnostics?: TrainingProgressionSourceDiagnostics
  edges?: Array<Record<string, unknown>>
  error?: string
}

export interface TrainingProgressionEdgeItem {
  id: string
  source_id: string
  from_label_raw: string
  from_exercise_id?: string | null
  from_reps: number
  to_label_raw: string
  to_exercise_id?: string | null
  to_reps: number
  relation_type: string
  goal_scope: string[]
  evidence_text?: string | null
  confidence: number
  review_status: string
  review_note?: string | null
  reviewed_by?: string | null
  reviewed_at?: string | null
  created_at: string
}

export interface TrainingProgressionReviewItem {
  edge: TrainingProgressionEdgeItem
  source: TrainingProgressionSourceItem
  preset_review?: TrainingProgressionPresetReview | null
}

export interface TrainingProgressionReviewListResponse {
  items: TrainingProgressionReviewItem[]
  total: number
}

export interface TrainingProgressionSourceListResponse {
  items: TrainingProgressionSourceItem[]
  total: number
}

export interface TrainingProgressionIngestVideoResult {
  video_id: string
  video_title: string
  status: string
  source_id?: string | null
  edges_created: number
  error?: string | null
}

export interface TrainingProgressionIngestResponse {
  channel_handle: string
  title_keyword: string
  videos_found: number
  videos_scanned: number
  videos_title_matched: number
  videos_processed: number
  transcripts_fetched: number
  transcripts_naturalized: number
  videos_with_edges: number
  edges_created: number
  results: TrainingProgressionIngestVideoResult[]
}

export interface TrainingProgressionReviewActionRequest {
  review_status: 'approved' | 'rejected'
  from_exercise_id?: string | null
  from_reps?: number | null
  to_exercise_id?: string | null
  to_reps?: number | null
  goal_scope?: string[] | null
  review_note?: string | null
  add_aliases: string[]
}

export interface TrainingProgressionApplyPresetsResponse {
  reviewed: number
  skipped: number
}

export interface AdminTrainingProgressionGraphNode {
  exercise_id: string
  name_ja: string
  required_equipment: string[]
  review_count: number
}

export interface AdminTrainingProgressionGraphEdge {
  edge_id: string
  from_exercise_id: string
  to_exercise_id: string
  from_reps_required: number
  to_reps_target: number
  review_status: string
  video_id: string
  video_title: string
  review_note?: string | null
}

export interface AdminTrainingProgressionGraphTrack {
  track_id: string
  title: string
  nodes: AdminTrainingProgressionGraphNode[]
  edges: AdminTrainingProgressionGraphEdge[]
}

export interface AdminTrainingProgressionUnmappedEdge {
  edge_id: string
  from_label_raw: string
  to_label_raw: string
  from_reps: number
  to_reps: number
  review_status: string
  video_id: string
  video_title: string
}

export interface AdminTrainingProgressionGraphSummary {
  status: string
  goal_type: string
  edge_count: number
  track_count: number
  unmapped_edge_count: number
}

export interface AdminTrainingProgressionGraphResponse {
  summary: AdminTrainingProgressionGraphSummary
  tracks: AdminTrainingProgressionGraphTrack[]
  unmapped_edges: AdminTrainingProgressionUnmappedEdge[]
}

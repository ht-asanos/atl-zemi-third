from pydantic import BaseModel


class YoutubeExtractRequest(BaseModel):
    url: str
    staple_name: str | None = None


class RecipeDraftIngredient(BaseModel):
    ingredient_name: str
    amount_text: str | None = None


class RecipeDraftStep(BaseModel):
    step_no: int
    text: str
    est_minutes: int | None = None


class RecipeDraft(BaseModel):
    title: str
    servings: int = 2
    cooking_minutes: int | None = None
    ingredients: list[RecipeDraftIngredient]
    steps: list[RecipeDraftStep]
    tags: list[str] = []


class YoutubeExtractResponse(BaseModel):
    video_id: str
    video_title: str
    transcript_quality: dict
    recipe_draft: RecipeDraft


class YoutubeRegisterRequest(BaseModel):
    video_id: str
    recipe_data: RecipeDraft


class YoutubeRegisterResponse(BaseModel):
    recipe_id: str
    title: str
    nutrition_status: str


class YoutubeRecipeItem(BaseModel):
    id: str
    title: str
    youtube_video_id: str | None
    nutrition_status: str | None
    steps_status: str | None
    created_at: str | None


class YoutubeRecipeListResponse(BaseModel):
    items: list[YoutubeRecipeItem]
    total: int
    page: int
    per_page: int


class BatchAdaptRequest(BaseModel):
    channel_handle: str
    source_query: str
    target_staple: str
    max_results: int = 5


class BatchAdaptVideoResult(BaseModel):
    video_id: str
    video_title: str
    # success / skipped_existing / filtered_source_mismatch / filtered_non_meal /
    # filtered_accompaniment / no_transcript / extraction_failed /
    # adaptation_failed / registration_failed
    status: str
    recipe_id: str | None = None
    recipe_title: str | None = None
    error: str | None = None


class BatchAdaptResponse(BaseModel):
    channel_handle: str
    source_query: str
    target_staple: str
    videos_found: int
    videos_processed: int
    succeeded: int
    failed: int
    skipped: int
    results: list[BatchAdaptVideoResult]

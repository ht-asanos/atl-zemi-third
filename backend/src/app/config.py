from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Bouldering App Backend"
    debug: bool = False
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    cors_origins: str = "http://localhost:3000"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    rakuten_app_id: str = ""
    rakuten_access_key: str = ""
    supabase_service_role_key: str = ""
    # Optional comma-separated issuer base URLs for token validation.
    # Example: "http://127.0.0.1:54321,http://localhost:54321"
    supabase_token_issuers: str = ""
    google_api_key: str = ""
    youtube_api_key: str = ""  # YOUTUBE_API_KEY 環境変数
    youtube_recipe_channels: str = "@Kurashiru,@ryuji825,@sanpiryoron"  # カンマ区切り
    youtube_transcript_verify_ssl: bool = False
    admin_user_ids: str = ""  # カンマ区切り UUID
    mext_http_verify_ssl: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

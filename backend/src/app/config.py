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
    google_api_key: str = ""
    admin_user_ids: str = ""  # カンマ区切り UUID

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

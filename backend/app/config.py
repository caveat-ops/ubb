from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://ubb:ubb@db:5432/ubb"
    cors_origin: str = "*"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b-32k"
    linkedin_email: str = ""
    linkedin_password: str = ""
    linkedin_url: str = ""
    url_target: str = ""
    url_about: str = ""
    playwright_headless: bool = True
    jwt_secret: str = "super-secret-change-me"
    jwt_algorithm: str = "HS256"
    log_level: str = "info"

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()

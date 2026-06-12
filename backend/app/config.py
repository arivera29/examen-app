from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Examen App API"
    debug: bool = False
    database_url: str = "postgresql://examen:examen123@localhost:5432/examen_db"
    secret_key: str = "change-me-in-production-use-env-var"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    refresh_token_expire_days: int = 7
    mfa_issuer: str = "ExamenApp"
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 5
    max_video_upload_size_mb: int = 128
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@examen-app.local"
    email_provider: str = "smtp"
    mailtrap_api_token: str = ""
    mailtrap_api_url: str = "https://send.api.mailtrap.io/api/send"
    mailtrap_from_email: str = "hello@demomailtrap.com"
    mailtrap_from_name: str = "Examen App"
    mailtrap_category: str = "Examen App"
    frontend_url: str = "http://localhost:4200"
    cors_origins: str = "http://localhost:4200"
    cors_allow_ngrok: bool = True
    proctoring_fraud_threshold: float = 0.7

    class Config:
        env_file = ".env"


settings = Settings()

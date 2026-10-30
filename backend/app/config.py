from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

class Settings(BaseSettings):
    database_url: str = "sqlite:///./devstride.db"
    secret_key: str = "local-development-key-change-before-deploy-000000000000"
    frontend_url: str = "http://localhost:5173"
    environment: str = "development"
    cookie_secure: bool = False
    session_days: int = 14
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @model_validator(mode="after")
    def production_safety(self):
        if self.environment.lower() == "production":
            if len(self.secret_key) < 32 or "change-before-deploy" in self.secret_key or "local-development" in self.secret_key:
                raise ValueError("Set a strong SECRET_KEY before production startup")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
            if not self.frontend_url.startswith("https://"):
                raise ValueError("FRONTEND_URL must use HTTPS in production")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        origins = [self.frontend_url.rstrip("/")]
        if self.environment.lower() != "production":
            origins.extend(["http://localhost:5173", "http://127.0.0.1:5173"])
        return list(dict.fromkeys(origins))

settings = Settings()

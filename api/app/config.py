from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/agent_console"
    claude_cli_path: str = "claude"
    workspace_path: str = "/workspace"
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_prefix": "AC_", "env_file": ".env"}


settings = Settings()

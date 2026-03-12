from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/agent_console"
    redis_url: str = "redis://redis:6379/0"
    claude_cli_path: str = "claude"
    workspace_path: str = "/workspace"
    cors_origins: list[str] = ["http://localhost:3000"]

    oauth_client_id: str = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
    oauth_authorize_url: str = "https://claude.ai/oauth/authorize"
    oauth_token_url: str = "https://platform.claude.com/v1/oauth/token"
    oauth_redirect_uri: str = "https://platform.claude.com/oauth/code/callback"
    oauth_scopes: str = "org:create_api_key user:profile user:inference user:sessions:claude_code user:mcp_servers"

    voyage_api_key: str = ""

    # Circuit breaker settings
    cb_failure_threshold: int = 5
    cb_recovery_timeout: float = 30.0
    cb_failure_window: float = 60.0

    # Budget settings
    budget_session_limit_usd: float = 2.0

    # Clone settings
    clone_timeout_seconds: int = 300

    # MCP → API вызовы
    api_base_url: str = "http://localhost:8000"

    model_config = {"env_prefix": "AC_", "env_file": ".env"}


settings = Settings()

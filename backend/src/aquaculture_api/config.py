import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str
    jwt_secret: str
    edge_secret: str
    database_url: str
    seed: bool
    deepseek_api_key: str
    deepseek_base_url: str

    @classmethod
    def from_environment(cls) -> "Settings":
        environment = os.getenv("APP_ENV", "demonstration")
        jwt_secret = os.getenv("JWT_SECRET", "demo-only-jwt-secret-not-for-production")
        edge_secret = os.getenv("EDGE_SECRET", "demo-only-edge-secret-not-for-production")
        if environment != "demonstration" and (
            jwt_secret.startswith("demo-only-") or edge_secret.startswith("demo-only-")
        ):
            raise RuntimeError("Non-demonstration environments require injected secrets")
        return cls(
            app_env=environment,
            jwt_secret=jwt_secret,
            edge_secret=edge_secret,
            database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///./aquaculture.db"),
            seed=os.getenv("SEED_DATA", "false").lower() in ("true", "1", "yes"),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )

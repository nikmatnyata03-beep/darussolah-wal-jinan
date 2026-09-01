"""Environment-backed configuration for the foundation website API."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    database_url: str
    tenant_slug: str
    allowed_origins: tuple[str, ...]
    supabase_url: str = ""
    jwks_url: str = ""
    jwt_secret: str = ""
    registration_max_bytes: int = 32 * 1024

    @classmethod
    def from_env(cls, *, require_runtime: bool = True) -> "Settings":
        database_url = os.getenv("DARUSSOLAH_DATABASE_URL", "").strip()
        if require_runtime and not database_url:
            raise RuntimeError("missing required environment variable: DARUSSOLAH_DATABASE_URL")
        origins = tuple(
            value.strip()
            for value in os.getenv("DARUSSOLAH_ALLOWED_ORIGINS", "").split(",")
            if value.strip()
        )
        max_bytes = int(os.getenv("DARUSSOLAH_REGISTRATION_MAX_BYTES", str(32 * 1024)))
        if max_bytes <= 0:
            raise RuntimeError("DARUSSOLAH_REGISTRATION_MAX_BYTES must be positive")
        supabase_url = os.getenv("DARUSSOLAH_SUPABASE_URL", "").strip().rstrip("/")
        jwks_url = os.getenv("DARUSSOLAH_JWKS_URL", "").strip()
        if not jwks_url and supabase_url:
            jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
        return cls(
            environment=os.getenv("DARUSSOLAH_ENVIRONMENT", "development").strip(),
            database_url=database_url,
            tenant_slug=os.getenv("DARUSSOLAH_TENANT_SLUG", "yayasan-darussolah-wal-jinan").strip(),
            allowed_origins=origins,
            supabase_url=supabase_url,
            jwks_url=jwks_url,
            jwt_secret=os.getenv("DARUSSOLAH_JWT_SECRET", "").strip(),
            registration_max_bytes=max_bytes,
        )

    def validate_runtime(self) -> None:
        missing = []
        if not self.database_url:
            missing.append("DARUSSOLAH_DATABASE_URL")
        if not self.tenant_slug:
            missing.append("DARUSSOLAH_TENANT_SLUG")
        if self.environment == "production" and not self.allowed_origins:
            missing.append("DARUSSOLAH_ALLOWED_ORIGINS")
        if self.environment == "production" and not (self.jwt_secret or self.jwks_url):
            missing.append("DARUSSOLAH_JWKS_URL or DARUSSOLAH_JWT_SECRET")
        if missing:
            raise RuntimeError(f"missing production configuration: {', '.join(missing)}")
        if self.registration_max_bytes <= 0:
            raise RuntimeError("DARUSSOLAH_REGISTRATION_MAX_BYTES must be positive")

"""Central config — reads st.secrets (Cloud) then os.environ (.env local)."""
import os
import streamlit as st


def _get(key: str, default: str = "") -> str:
    try:
        val = st.secrets.get(key)
        if val is not None:
            return str(val)
    except Exception:
        pass
    return os.environ.get(key, default)


class _Config:
    @property
    def DB_USER(self) -> str:
        return _get("DB_USER", "postgres")
    @property
    def DB_PASSWORD(self) -> str:
        return _get("DB_PASSWORD", "")
    @property
    def DB_HOST(self) -> str:
        return _get("DB_HOST", "localhost")
    @property
    def DB_PORT(self) -> int:
        try:
            return int(_get("DB_PORT", "5432"))
        except (ValueError, TypeError):
            return 5432
    @property
    def DB_NAME(self) -> str:
        return _get("DB_NAME", "postgres")
    @property
    def OPENAI_API_KEY(self) -> str:
        return _get("OPENAI_API_KEY")
    @property
    def CORE_API_KEY(self) -> str:
        return _get("CORE_API_KEY")
    @property
    def SECRET_KEY(self) -> str:
        return _get("SECRET_KEY", "dev-secret")
    @property
    def APP_NAME(self) -> str:
        return _get("APP_NAME", "ResearchAI")


cfg = _Config()
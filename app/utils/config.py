from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    llm_provider: str
    vector_db_path: Path
    knowledge_base_path: Path
    chunk_size: int
    chunk_overlap: int
    use_reranker: bool
    collection_name: str
    embedding_model: str
    supported_extensions: tuple[str, ...]
    top_k: int
    bm25_weight: float
    vector_weight: float
    database_path: Path
    max_history_messages: int
    lms_api_url: str
    lms_data_path: Path


def _load_yaml_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


@lru_cache
def get_settings(config_path: Path | None = None) -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    yaml_config = _load_yaml_config(config_path or DEFAULT_CONFIG_PATH)

    kb_config = yaml_config.get("knowledge_base", {})
    indexing_config = yaml_config.get("indexing", {})
    vector_config = yaml_config.get("vector_store", {})
    embeddings_config = yaml_config.get("embeddings", {})
    retrieval_config = yaml_config.get("retrieval", {})
    database_config = yaml_config.get("database", {})
    lms_config = yaml_config.get("lms", {})

    knowledge_base_path = _resolve_path(
        os.getenv("KNOWLEDGE_BASE_PATH", kb_config.get("path", "./knowledge_base"))
    )
    vector_db_path = _resolve_path(
        os.getenv("VECTOR_DB_PATH", vector_config.get("path", "./vector_store"))
    )

    supported_extensions = tuple(
        kb_config.get("supported_extensions", [".odt"])
    )

    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        vector_db_path=vector_db_path,
        knowledge_base_path=knowledge_base_path,
        chunk_size=int(os.getenv("CHUNK_SIZE", indexing_config.get("chunk_size", 1200))),
        chunk_overlap=int(
            os.getenv("CHUNK_OVERLAP", indexing_config.get("chunk_overlap", 200))
        ),
        use_reranker=os.getenv("USE_RERANKER", "false").lower() == "true",
        collection_name=indexing_config.get("collection_name", "course_knowledge"),
        embedding_model=embeddings_config.get("model", "text-embedding-3-small"),
        supported_extensions=supported_extensions,
        top_k=int(os.getenv("TOP_K", retrieval_config.get("top_k", 5))),
        bm25_weight=float(
            os.getenv("BM25_WEIGHT", retrieval_config.get("bm25_weight", 0.5))
        ),
        vector_weight=float(
            os.getenv("VECTOR_WEIGHT", retrieval_config.get("vector_weight", 0.5))
        ),
        database_path=_resolve_path(
            os.getenv("DATABASE_PATH", database_config.get("path", "./data/app.db"))
        ),
        max_history_messages=int(
            os.getenv(
                "MAX_HISTORY_MESSAGES",
                database_config.get("max_history_messages", 10),
            )
        ),
        lms_api_url=os.getenv("LMS_API_URL", lms_config.get("api_url", "http://127.0.0.1:8000")),
        lms_data_path=_resolve_path(
            os.getenv("LMS_DATA_PATH", lms_config.get("data_path", "./data"))
        ),
    )

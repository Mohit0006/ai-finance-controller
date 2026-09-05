from functools import lru_cache
import logging
from typing import Optional
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

_model_instance: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    global _model_instance
    if _model_instance is None:
        logger.info(f"Loading embedding model '{MODEL_NAME}'...")
        _model_instance = SentenceTransformer(MODEL_NAME)
    return _model_instance


def check_embedding_model_status() -> bool:
    try:
        model = get_embedding_model()
        return model is not None
    except Exception as e:
        logger.error(f"Embedding model check failed: {e}")
        return False


def generate_embeddings(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    if not texts:
        return []
    
    model = get_embedding_model()
    # Normalize embeddings to enable exact cosine distance calculations
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False
    )
    
    result = embeddings.tolist()
    # Validate dimension on first element if exists
    if result and len(result[0]) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSION}, got {len(result[0])}"
        )
    return result


def generate_single_embedding(text: str) -> list[float]:
    embeddings = generate_embeddings([text])
    return embeddings[0] if embeddings else [0.0] * EMBEDDING_DIMENSION

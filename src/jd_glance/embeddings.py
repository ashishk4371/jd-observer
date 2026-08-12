import logging
import os
from typing import Optional, List

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

_model = None
_load_failed = False


def _get_model():
    """Lazily load the local embedding model once. Returns None (and stays None)
    if fastembed isn't installed or the model can't be downloaded/loaded, so
    callers can fall back to TF-IDF-only semantic similarity."""
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    try:
        from fastembed import TextEmbedding
        # Same JD_GLANCE_DATA_DIR as db.py, so the downloaded ONNX model
        # survives container restarts instead of re-downloading each time.
        data_dir = os.environ.get("JD_GLANCE_DATA_DIR")
        cache_dir = os.path.join(data_dir, "fastembed_cache") if data_dir else None
        _model = TextEmbedding(model_name=EMBEDDING_MODEL, cache_dir=cache_dir)
    except Exception as e:
        logger.warning(f"Local embedding model unavailable, falling back to TF-IDF only: {e}")
        _load_failed = True
    return _model


def embed_text(text: str) -> Optional[List[float]]:
    """Embed a single piece of text into a 384-dim vector, or None if unavailable."""
    model = _get_model()
    if model is None or not text.strip():
        return None
    try:
        vec = next(model.embed([text[:8000]]))
        return vec.tolist()
    except Exception as e:
        logger.warning(f"Embedding generation failed: {e}")
        return None


def deserialize_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def cosine_similarity_score(vec_a: bytes, vec_b: bytes) -> float:
    """Compare two stored (already-normalized) embedding blobs, 0-100 scale."""
    a = deserialize_vector(vec_a)
    b = deserialize_vector(vec_b)
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    cosine = float(np.dot(a, b) / denom)
    return max(0.0, min(100.0, (cosine + 1.0) / 2.0 * 100.0))

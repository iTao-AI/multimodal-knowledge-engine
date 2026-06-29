"""Evaluation-only vector projection adapters."""

from mke.adapters.vector.exact_cosine import ExactCosineProjection
from mke.adapters.vector.sqlite_vec import SqliteVecProjection

__all__ = ["ExactCosineProjection", "SqliteVecProjection"]

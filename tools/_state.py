"""
Shared in-process dataset registry.

Tools that operate on dataframes need a way to pass them around without
serializing them through LLM (which would be wasteful and lossy).
We give each loaded CSV a short `dataset_id` and keep the actual DataFrame
in this module-level registry. Tools take/return `dataset_id` strings.

This is intentionally simple — for an MVP it's perfect. For multi-process
runs, swap this for Redis or a feather-cache on disk.
"""

from __future__ import annotations

import uuid
from typing import Optional

import pandas as pd


_DATASETS: dict[str, pd.DataFrame] = {}
_SOURCES: dict[str, str] = {}  # dataset_id -> original file path


def register(df: pd.DataFrame, source: str) -> str:
    """Register a DataFrame and return a short id."""
    dataset_id = f"ds_{uuid.uuid4().hex[:8]}"
    _DATASETS[dataset_id] = df
    _SOURCES[dataset_id] = source
    return dataset_id


def get(dataset_id: str) -> pd.DataFrame:
    if dataset_id not in _DATASETS:
        raise KeyError(
            f"Unknown dataset_id '{dataset_id}'. "
            f"Known ids: {list(_DATASETS) or '(none)'}"
        )
    return _DATASETS[dataset_id]


def source_of(dataset_id: str) -> Optional[str]:
    return _SOURCES.get(dataset_id)


def all_datasets() -> dict[str, str]:
    """Every registered dataset_id mapped to its original source path."""
    return dict(_SOURCES)


def reset() -> None:
    """Clear the registry. Useful between independent runs / tests."""
    _DATASETS.clear()
    _SOURCES.clear()

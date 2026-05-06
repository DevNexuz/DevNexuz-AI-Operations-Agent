"""
CSV tools — loading and profiling tabular data.

These two are usually the first tools called by the agent, so their
output shape is designed to feed the planner/executor's downstream
reasoning (column names, dtypes, basic stats).
"""

from pathlib import Path
from typing import Optional

import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from tools import _state


# -- load_csv -----------------------------------------------------------------

class LoadCsvArgs(BaseModel):
    file_path: str = Field(description="Path to the CSV file to load.")
    delimiter: Optional[str] = Field(
        default=None,
        description="Optional column delimiter. If omitted, pandas auto-detects.",
    )


@tool("load_csv", args_schema=LoadCsvArgs)
def load_csv(file_path: str, delimiter: Optional[str] = None) -> dict:
    """Load a CSV file from disk and register it for downstream tools.

    Returns a dict with the dataset_id (used by other tools), the shape,
    and the column names. Does NOT return the full dataframe — that
    stays in the in-process registry.
    """
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    if not path.is_file():
        return {"error": f"Path is not a file: {file_path}"}

    try:
        df = pd.read_csv(path, sep=delimiter) if delimiter else pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Failed to read CSV: {type(exc).__name__}: {exc}"}

    if df.empty:
        return {"error": "CSV loaded but contains zero rows."}

    dataset_id = _state.register(df, source=str(path))
    return {
        "dataset_id": dataset_id,
        "rows": len(df),
        "columns": list(df.columns),
        "source": str(path),
    }


# -- profile_dataset ----------------------------------------------------------

class ProfileArgs(BaseModel):
    dataset_id: str = Field(description="ID returned by load_csv.")


@tool("profile_dataset", args_schema=ProfileArgs)
def profile_dataset(dataset_id: str) -> dict:
    """Produce a quick statistical profile of a loaded dataset.

    Includes dtypes, missing values, basic numeric stats, and value
    counts for the top categorical columns. Designed to give the LLM
    enough context to decide what to analyze next.
    """
    try:
        df = _state.get(dataset_id)
    except KeyError as exc:
        return {"error": str(exc)}

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    datetime_cols = df.select_dtypes(include="datetime").columns.tolist()

    profile = {
        "shape": {"rows": len(df), "columns": len(df.columns)},
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "missing_values": {
            c: int(df[c].isna().sum()) for c in df.columns if df[c].isna().any()
        },
        "numeric_summary": {},
        "categorical_summary": {},
        "datetime_columns": datetime_cols,
    }

    if numeric_cols:
        # Round to 2 decimals to keep prompt context lean.
        profile["numeric_summary"] = (
            df[numeric_cols].describe().round(2).to_dict()
        )

    for col in categorical_cols[:5]:  # cap to top 5 to avoid prompt bloat
        profile["categorical_summary"][col] = {
            "unique": int(df[col].nunique()),
            "top_values": df[col].value_counts().head(5).to_dict(),
        }

    return profile

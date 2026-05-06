"""
Analysis tools — slice, dice, find patterns, draw charts.

Every tool returns JSON-serializable data so it can be logged into
memory and re-fed to the LLM in subsequent steps.
"""

from pathlib import Path
from typing import Literal, Optional

import matplotlib

matplotlib.use("Agg")  # headless-safe before importing pyplot
import matplotlib.pyplot as plt
import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from tools import _state


OUTPUTS_DIR = Path("outputs")
CHARTS_DIR = OUTPUTS_DIR / "charts"


# -- aggregate_by -------------------------------------------------------------

class AggregateArgs(BaseModel):
    dataset_id: str = Field(description="ID returned by load_csv.")
    group_by: str = Field(description="Column name to group by.")
    metric: str = Field(description="Numeric column to aggregate.")
    agg: Literal["sum", "mean", "median", "count", "min", "max"] = Field(
        default="sum", description="Aggregation function to apply."
    )


@tool("aggregate_by", args_schema=AggregateArgs)
def aggregate_by(
    dataset_id: str, group_by: str, metric: str, agg: str = "sum"
) -> dict:
    """Group a dataset by a column and aggregate a numeric metric.

    Useful for questions like "total sales by region" or "average
    salary by department". Returns a dict with the resulting series
    sorted descending by value.
    """
    try:
        df = _state.get(dataset_id)
    except KeyError as exc:
        return {"error": str(exc)}

    if group_by not in df.columns:
        return {"error": f"Column '{group_by}' not in dataset."}
    if metric not in df.columns:
        return {"error": f"Column '{metric}' not in dataset."}
    if not pd.api.types.is_numeric_dtype(df[metric]):
        return {"error": f"Column '{metric}' is not numeric."}

    series = df.groupby(group_by)[metric].agg(agg).sort_values(ascending=False)
    return {
        "group_by": group_by,
        "metric": metric,
        "agg": agg,
        "result": {str(k): float(v) for k, v in series.items()},
    }


# -- top_n --------------------------------------------------------------------

class TopNArgs(BaseModel):
    dataset_id: str = Field(description="ID returned by load_csv.")
    sort_by: str = Field(description="Column to sort by.")
    n: int = Field(default=5, description="How many rows to return.")
    ascending: bool = Field(default=False, description="Sort ascending?")


@tool("top_n", args_schema=TopNArgs)
def top_n(dataset_id: str, sort_by: str, n: int = 5, ascending: bool = False) -> dict:
    """Return the top-N rows of a dataset sorted by a given column.

    Use this for questions like "top 5 products by revenue" or
    "the 3 employees with lowest performance score".
    """
    try:
        df = _state.get(dataset_id)
    except KeyError as exc:
        return {"error": str(exc)}

    if sort_by not in df.columns:
        return {"error": f"Column '{sort_by}' not in dataset."}

    n = max(1, min(int(n), 50))  # clamp to sane range
    head = df.sort_values(sort_by, ascending=ascending).head(n)
    return {
        "sort_by": sort_by,
        "n": n,
        "ascending": ascending,
        "rows": head.to_dict(orient="records"),
    }


# -- detect_anomalies ---------------------------------------------------------

class AnomalyArgs(BaseModel):
    dataset_id: str = Field(description="ID returned by load_csv.")
    column: str = Field(description="Numeric column to scan for anomalies.")
    z_threshold: float = Field(
        default=3.0,
        description="Absolute z-score above which a value is flagged.",
    )


@tool("detect_anomalies", args_schema=AnomalyArgs)
def detect_anomalies(
    dataset_id: str, column: str, z_threshold: float = 3.0
) -> dict:
    """Detect statistical outliers in a numeric column using z-score.

    Anomalies are values where |z| > threshold. Good first-pass tool
    for spotting unusually high/low data points worth investigating.
    """
    try:
        df = _state.get(dataset_id)
    except KeyError as exc:
        return {"error": str(exc)}

    if column not in df.columns:
        return {"error": f"Column '{column}' not in dataset."}
    if not pd.api.types.is_numeric_dtype(df[column]):
        return {"error": f"Column '{column}' is not numeric."}

    series = df[column].dropna()
    if series.std(ddof=0) == 0:
        return {
            "column": column,
            "anomalies": [],
            "note": "Standard deviation is zero; no anomalies possible.",
        }

    z = (series - series.mean()) / series.std(ddof=0)
    mask = z.abs() > z_threshold
    flagged = df.loc[series.index[mask]].copy()
    flagged["_zscore"] = z[mask].round(2).values

    return {
        "column": column,
        "z_threshold": z_threshold,
        "count": int(mask.sum()),
        "anomalies": flagged.head(20).to_dict(orient="records"),
    }


# -- generate_chart -----------------------------------------------------------

class ChartArgs(BaseModel):
    dataset_id: str = Field(description="ID returned by load_csv.")
    chart_type: Literal["bar", "line", "hist"] = Field(
        description="Type of chart to generate."
    )
    x: Optional[str] = Field(
        default=None,
        description="X-axis column (required for bar/line, ignored for hist).",
    )
    y: str = Field(description="Y-axis (or value) column.")
    title: str = Field(description="Chart title.")
    filename: Optional[str] = Field(
        default=None,
        description="Output filename (without dir). Auto-generated if omitted.",
    )


@tool("generate_chart", args_schema=ChartArgs)
def generate_chart(
    dataset_id: str,
    chart_type: str,
    y: str,
    title: str,
    x: Optional[str] = None,
    filename: Optional[str] = None,
) -> dict:
    """Generate a PNG chart from the dataset and save it under outputs/charts/.

    Supports bar, line, and histogram. Returns the path to the saved
    image so the report tool can embed it.
    """
    try:
        df = _state.get(dataset_id)
    except KeyError as exc:
        return {"error": str(exc)}

    if y not in df.columns:
        return {"error": f"Column '{y}' not in dataset."}
    if chart_type in {"bar", "line"} and (not x or x not in df.columns):
        return {"error": f"chart_type '{chart_type}' requires a valid 'x' column."}

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    if not filename:
        safe_title = "".join(c if c.isalnum() else "_" for c in title).strip("_").lower()
        filename = f"{safe_title or 'chart'}.png"
    out_path = CHARTS_DIR / filename

    fig, ax = plt.subplots(figsize=(8, 4.5))
    try:
        if chart_type == "bar":
            grouped = df.groupby(x)[y].sum().sort_values(ascending=False).head(15)
            grouped.plot(kind="bar", ax=ax, color="#4C72B0")
        elif chart_type == "line":
            df_sorted = df.sort_values(x)
            ax.plot(df_sorted[x], df_sorted[y], color="#4C72B0")
        elif chart_type == "hist":
            df[y].dropna().plot(kind="hist", bins=30, ax=ax, color="#4C72B0")

        ax.set_title(title)
        if x:
            ax.set_xlabel(x)
        ax.set_ylabel(y)
        fig.tight_layout()
        fig.savefig(out_path, dpi=120)
    finally:
        plt.close(fig)

    return {
        "chart_path": str(out_path),
        "chart_type": chart_type,
        "title": title,
    }

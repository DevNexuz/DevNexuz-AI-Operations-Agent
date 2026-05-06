"""
tests/test_tools.py — Unit tests for the agent's tool layer.

These tests are PURE — no LLM involved. They call tools directly
with known inputs and assert on the output shape and content.

Run with:
    pytest tests/test_tools.py -v
"""

import pytest
import pandas as pd

from tools import _state
from tools.csv_tools import load_csv, profile_dataset
from tools.analysis_tools import aggregate_by, top_n, detect_anomalies


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_state():
    """Reset the dataset registry before every test.

    Without this, a dataset_id from test A could leak into test B
    and cause false positives or confusing KeyErrors.
    """
    _state.reset()
    yield
    _state.reset()


@pytest.fixture
def sales_dataset_id():
    """Load data/sales.csv and return its dataset_id.

    Depends on the sample data existing — run `python main.py --demo`
    once to generate it, or `python data/generate_samples.py`.
    """
    result = load_csv.invoke({"file_path": "data/sales.csv"})
    assert "error" not in result, f"Could not load sales.csv: {result}"
    return result["dataset_id"]


@pytest.fixture
def small_dataset_id():
    """Register a tiny hand-crafted DataFrame for fast, deterministic tests."""
    df = pd.DataFrame({
        "region": ["North", "South", "North", "East", "South"],
        "revenue": [100.0, 200.0, 150.0, 50.0, 300.0],
        "units":   [10,    20,    15,    5,     30   ],
    })
    return _state.register(df, source="fixture")


# ---------------------------------------------------------------------------
# load_csv
# ---------------------------------------------------------------------------

class TestLoadCsv:

    def test_valid_file_returns_dataset_id_and_shape(self):
        """Happy path: loads a real CSV and returns expected keys."""
        result = load_csv.invoke({"file_path": "data/sales.csv"})

        assert "error" not in result
        assert "dataset_id" in result
        assert result["dataset_id"].startswith("ds_")
        assert result["rows"] > 0
        assert isinstance(result["columns"], list)
        assert len(result["columns"]) > 0

    def test_missing_file_returns_error(self):
        """Non-existent path must return an error dict, not raise an exception."""
        result = load_csv.invoke({"file_path": "data/does_not_exist.csv"})

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_loaded_dataframe_is_accessible_by_id(self):
        """The registered dataset_id must be retrievable from _state."""
        result = load_csv.invoke({"file_path": "data/sales.csv"})
        dataset_id = result["dataset_id"]

        df = _state.get(dataset_id)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == result["rows"]


# ---------------------------------------------------------------------------
# profile_dataset
# ---------------------------------------------------------------------------

class TestProfileDataset:

    def test_profile_returns_required_keys(self, sales_dataset_id):
        """Profile output must always contain shape, dtypes, and summaries."""
        result = profile_dataset.invoke({"dataset_id": sales_dataset_id})

        assert "error" not in result
        assert "shape" in result
        assert "dtypes" in result
        assert "numeric_summary" in result
        assert "categorical_summary" in result

    def test_profile_shape_matches_csv(self, sales_dataset_id):
        """Shape in profile must match the actual DataFrame dimensions."""
        result = profile_dataset.invoke({"dataset_id": sales_dataset_id})

        assert result["shape"]["rows"] == 1200
        assert result["shape"]["columns"] == 8

    def test_profile_unknown_id_returns_error(self):
        """Asking for a non-existent dataset_id must return an error dict."""
        result = profile_dataset.invoke({"dataset_id": "ds_nonexistent"})

        assert "error" in result


# ---------------------------------------------------------------------------
# aggregate_by
# ---------------------------------------------------------------------------

class TestAggregateBy:

    def test_sum_by_region_returns_all_regions(self, small_dataset_id):
        """Aggregation must include every unique value of the group_by column."""
        result = aggregate_by.invoke({
            "dataset_id": small_dataset_id,
            "group_by": "region",
            "metric": "revenue",
            "agg": "sum",
        })

        assert "error" not in result
        assert set(result["result"].keys()) == {"North", "South", "East"}

    def test_sum_values_are_correct(self, small_dataset_id):
        """North = 100+150=250, South = 200+300=500, East = 50."""
        result = aggregate_by.invoke({
            "dataset_id": small_dataset_id,
            "group_by": "region",
            "metric": "revenue",
            "agg": "sum",
        })

        assert result["result"]["North"] == pytest.approx(250.0)
        assert result["result"]["South"] == pytest.approx(500.0)
        assert result["result"]["East"]  == pytest.approx(50.0)

    def test_nonexistent_column_returns_error(self, small_dataset_id):
        """Referencing a column that does not exist must return an error dict."""
        result = aggregate_by.invoke({
            "dataset_id": small_dataset_id,
            "group_by": "region",
            "metric": "nonexistent_col",
            "agg": "sum",
        })

        assert "error" in result


# ---------------------------------------------------------------------------
# top_n
# ---------------------------------------------------------------------------

class TestTopN:

    def test_returns_correct_number_of_rows(self, small_dataset_id):
        """top_n must return exactly n rows (or fewer if dataset is smaller)."""
        result = top_n.invoke({
            "dataset_id": small_dataset_id,
            "sort_by": "revenue",
            "n": 3,
            "ascending": False,
        })

        assert "error" not in result
        assert len(result["rows"]) == 3

    def test_descending_order_first_row_is_max(self, small_dataset_id):
        """First row must have the highest revenue when ascending=False."""
        result = top_n.invoke({
            "dataset_id": small_dataset_id,
            "sort_by": "revenue",
            "n": 1,
            "ascending": False,
        })

        assert result["rows"][0]["revenue"] == pytest.approx(300.0)

    def test_nonexistent_sort_column_returns_error(self, small_dataset_id):
        result = top_n.invoke({
            "dataset_id": small_dataset_id,
            "sort_by": "ghost_column",
            "n": 3,
        })

        assert "error" in result


# ---------------------------------------------------------------------------
# detect_anomalies
# ---------------------------------------------------------------------------

class TestDetectAnomalies:

    def test_no_anomalies_in_tight_data(self):
        """Uniform data should produce zero anomalies."""
        df = pd.DataFrame({"value": [10.0, 10.0, 10.0, 10.0, 10.0]})
        ds_id = _state.register(df, source="fixture")

        result = detect_anomalies.invoke({
            "dataset_id": ds_id,
            "column": "value",
            "z_threshold": 3.0,
        })

        # Either count==0 or the zero-std note is present
        assert result.get("count", 0) == 0 or "note" in result

    def test_clear_outlier_is_flagged(self):
        """A value miles outside a normal distribution must always be flagged.

        We build 100 points from N(0, 1) plus one value at 50 — guaranteed
        z >> 3 regardless of ddof or random seed, because 50 / ~1 = ~50 sigma.
        """
        import numpy as np
        rng = np.random.default_rng(42)
        normal_values = rng.normal(loc=0.0, scale=1.0, size=100).tolist()
        df = pd.DataFrame({"value": normal_values + [50.0]})
        ds_id = _state.register(df, source="fixture")

        result = detect_anomalies.invoke({
            "dataset_id": ds_id,
            "column": "value",
            "z_threshold": 3.0,
        })

        assert "error" not in result
        assert result["count"] >= 1

    def test_non_numeric_column_returns_error(self, small_dataset_id):
        result = detect_anomalies.invoke({
            "dataset_id": small_dataset_id,
            "column": "region",
            "z_threshold": 3.0,
        })

        assert "error" in result

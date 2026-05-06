"""
Synthetic dataset generator.

Run once to populate data/ with three realistic-looking CSVs that the
agent can analyze out-of-the-box. Each dataset has DELIBERATE quirks
(outliers, imbalances) so the agent has something interesting to find.

Usage:
    python data/generate_samples.py
"""

from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path(__file__).parent
SEED = 42


def generate_sales(rows: int = 1200) -> pd.DataFrame:
    """Sales records with regional imbalance + a few suspiciously huge orders."""
    rng = np.random.default_rng(SEED)
    regions = ["North", "South", "East", "West", "Central"]
    products = ["Laptop", "Phone", "Tablet", "Monitor", "Headphones", "Keyboard"]
    channels = ["Online", "Retail", "Partner"]

    dates = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    df = pd.DataFrame({
        "order_id": [f"ORD-{i:05d}" for i in range(1, rows + 1)],
        "date": rng.choice(dates, size=rows),
        # Regions are not uniform — North dominates on purpose.
        "region": rng.choice(regions, size=rows, p=[0.35, 0.15, 0.20, 0.15, 0.15]),
        "product": rng.choice(products, size=rows),
        "channel": rng.choice(channels, size=rows, p=[0.55, 0.30, 0.15]),
        "units": rng.integers(1, 12, size=rows),
        "unit_price": rng.normal(450, 180, size=rows).round(2).clip(min=20),
    })
    df["revenue"] = (df["units"] * df["unit_price"]).round(2)

    # Plant 6 obvious outliers — the agent should flag these.
    outlier_idx = rng.choice(df.index, size=6, replace=False)
    df.loc[outlier_idx, "revenue"] = rng.uniform(40_000, 80_000, size=6).round(2)

    return df.sort_values("date").reset_index(drop=True)


def generate_employees(rows: int = 250) -> pd.DataFrame:
    """HR dataset with a salary anomaly in one department."""
    rng = np.random.default_rng(SEED + 1)
    departments = ["Engineering", "Sales", "Marketing", "HR", "Finance", "Support"]
    levels = ["Junior", "Mid", "Senior", "Lead"]
    level_multiplier = {"Junior": 1.0, "Mid": 1.5, "Senior": 2.2, "Lead": 3.0}

    dept = rng.choice(departments, size=rows)
    level = rng.choice(levels, size=rows, p=[0.30, 0.40, 0.22, 0.08])
    base_salary = rng.normal(45_000, 6_000, size=rows)
    salary = np.array([
        base * level_multiplier[lvl] for base, lvl in zip(base_salary, level)
    ]).round(0)

    df = pd.DataFrame({
        "employee_id": [f"EMP-{i:04d}" for i in range(1, rows + 1)],
        "department": dept,
        "level": level,
        "years_at_company": rng.integers(0, 15, size=rows),
        "performance_score": rng.normal(3.5, 0.7, size=rows).round(2).clip(1, 5),
        "salary": salary,
    })

    # Plant a couple of suspicious salaries (way above level norm).
    suspicious_idx = rng.choice(df.index, size=3, replace=False)
    df.loc[suspicious_idx, "salary"] = rng.uniform(180_000, 250_000, size=3).round(0)

    return df


def generate_tickets(rows: int = 800) -> pd.DataFrame:
    """Support tickets with category imbalance and one team that's drowning."""
    rng = np.random.default_rng(SEED + 2)
    categories = ["Bug", "Feature Request", "Question", "Billing", "Outage"]
    priorities = ["Low", "Medium", "High", "Critical"]
    teams = ["Platform", "Mobile", "Web", "Data", "Billing"]
    statuses = ["Open", "In Progress", "Resolved", "Closed"]

    df = pd.DataFrame({
        "ticket_id": [f"TCK-{i:05d}" for i in range(1, rows + 1)],
        "created_at": pd.date_range("2024-06-01", periods=rows, freq="3h"),
        "category": rng.choice(categories, size=rows, p=[0.40, 0.15, 0.25, 0.10, 0.10]),
        "priority": rng.choice(priorities, size=rows, p=[0.35, 0.40, 0.20, 0.05]),
        # Platform team is overloaded on purpose.
        "assigned_team": rng.choice(teams, size=rows, p=[0.45, 0.15, 0.15, 0.15, 0.10]),
        "status": rng.choice(statuses, size=rows, p=[0.20, 0.25, 0.40, 0.15]),
        "resolution_hours": rng.gamma(shape=2.0, scale=8.0, size=rows).round(1),
        "customer_satisfaction": rng.choice(
            [1, 2, 3, 4, 5, None],
            size=rows,
            p=[0.05, 0.10, 0.20, 0.30, 0.25, 0.10],
        ),
    })
    return df


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    datasets = {
        "sales.csv": generate_sales(),
        "employees.csv": generate_employees(),
        "tickets.csv": generate_tickets(),
    }

    for name, df in datasets.items():
        path = DATA_DIR / name
        df.to_csv(path, index=False)
        print(f"[OK] Wrote {path} ({len(df)} rows, {len(df.columns)} cols)")


if __name__ == "__main__":
    main()

"""
Synthetic dataset generator.

Run once to populate data/ with three realistic-looking CSVs that the
agent can analyze out-of-the-box. Each dataset has DELIBERATE quirks
(outliers, imbalances) so the agent has something interesting to find.

Also generates three LATAM variants with Spanish column names and
region-specific context, simulating a bilingual enterprise where HQ
data lives in English and LATAM subsidiaries report in Spanish.

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


def generate_latam_ventas(rows: int = 1000) -> pd.DataFrame:
    """Ventas LATAM — Colombia tiene una caída brusca en Q3 (crisis de mercado).
    México domina en volumen pero Argentina lidera en precio unitario promedio.
    """
    rng = np.random.default_rng(SEED + 10)
    paises = ["México", "Colombia", "Argentina", "Chile", "Perú"]
    productos = ["Laptop", "Teléfono", "Tableta", "Monitor", "Audífonos", "Teclado"]
    canales = ["En línea", "Tienda", "Distribuidor"]

    fechas = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    pais_col = rng.choice(paises, size=rows, p=[0.35, 0.20, 0.20, 0.15, 0.10])
    fecha_col = rng.choice(fechas, size=rows)

    df = pd.DataFrame({
        "id_orden": [f"LAT-{i:05d}" for i in range(1, rows + 1)],
        "fecha": fecha_col,
        "pais": pais_col,
        # Argentina tiene precio unitario más alto (mercado premium).
        "producto": rng.choice(productos, size=rows),
        "canal": rng.choice(canales, size=rows, p=[0.50, 0.35, 0.15]),
        "unidades": rng.integers(1, 15, size=rows),
        "precio_unitario": np.where(
            pais_col == "Argentina",
            rng.normal(620, 200, size=rows).round(2).clip(min=30),
            rng.normal(420, 150, size=rows).round(2).clip(min=30),
        ),
    })
    df["ingresos"] = (df["unidades"] * df["precio_unitario"]).round(2)

    # Colombia Q3 crash: reducir ingresos un 70% en julio-septiembre.
    mask_colombia_q3 = (
        (df["pais"] == "Colombia") &
        (df["fecha"].dt.month.isin([7, 8, 9]))
    )
    df.loc[mask_colombia_q3, "ingresos"] = (
        df.loc[mask_colombia_q3, "ingresos"] * 0.30
    ).round(2)

    # 5 órdenes gigantes plantadas — el agente debe detectarlas.
    outlier_idx = rng.choice(df.index, size=5, replace=False)
    df.loc[outlier_idx, "ingresos"] = rng.uniform(50_000, 90_000, size=5).round(2)

    return df.sort_values("fecha").reset_index(drop=True)


def generate_latam_empleados(rows: int = 220) -> pd.DataFrame:
    """RRHH LATAM — alta rotación en Ventas (años_en_empresa muy bajos)
    y salarios anómalos en Finanzas que el agente debe identificar.
    """
    rng = np.random.default_rng(SEED + 11)
    departamentos = ["Ingeniería", "Ventas", "Marketing", "RRHH", "Finanzas", "Soporte"]
    niveles = ["Junior", "Intermedio", "Senior", "Líder"]
    multiplicador = {"Junior": 1.0, "Intermedio": 1.5, "Senior": 2.1, "Líder": 2.9}
    paises = ["México", "Colombia", "Argentina", "Chile", "Perú"]

    dept = rng.choice(departamentos, size=rows)
    nivel = rng.choice(niveles, size=rows, p=[0.32, 0.38, 0.22, 0.08])
    salario_base = rng.normal(18_000, 4_000, size=rows)  # MXN mensual aprox.
    salario = np.array([
        base * multiplicador[n] for base, n in zip(salario_base, nivel)
    ]).round(0)

    # Ventas tiene alta rotación: sesgar años_en_empresa hacia 0-2.
    años = np.where(
        dept == "Ventas",
        rng.integers(0, 3, size=rows),
        rng.integers(0, 12, size=rows),
    )

    df = pd.DataFrame({
        "id_empleado": [f"LAT-EMP-{i:04d}" for i in range(1, rows + 1)],
        "pais": rng.choice(paises, size=rows, p=[0.35, 0.20, 0.20, 0.15, 0.10]),
        "departamento": dept,
        "nivel": nivel,
        "años_en_empresa": años,
        "puntaje_desempeño": rng.normal(3.4, 0.8, size=rows).round(2).clip(1, 5),
        "salario_mensual": salario,
    })

    # Salarios anómalos en Finanzas — muy por encima del nivel.
    finanzas_idx = df[df["departamento"] == "Finanzas"].sample(3, random_state=SEED).index
    df.loc[finanzas_idx, "salario_mensual"] = rng.uniform(95_000, 140_000, size=3).round(0)

    return df


def generate_latam_tickets(rows: int = 700) -> pd.DataFrame:
    """Soporte LATAM — equipo Móvil saturado y alta proporción de tickets
    Críticos sin resolver, lo que arrastra la satisfacción a la baja.
    """
    rng = np.random.default_rng(SEED + 12)
    categorias = ["Error", "Solicitud de función", "Consulta", "Facturación", "Interrupción"]
    prioridades = ["Baja", "Media", "Alta", "Crítica"]
    equipos = ["Plataforma", "Móvil", "Web", "Datos", "Facturación"]
    estados = ["Abierto", "En progreso", "Resuelto", "Cerrado"]
    paises = ["México", "Colombia", "Argentina", "Chile", "Perú"]

    equipo_col = rng.choice(equipos, size=rows, p=[0.20, 0.42, 0.18, 0.12, 0.08])

    # Móvil recibe más tickets Críticos y los resuelve más lento.
    prioridad_col = np.where(
        equipo_col == "Móvil",
        rng.choice(prioridades, size=rows, p=[0.10, 0.25, 0.30, 0.35]),
        rng.choice(prioridades, size=rows, p=[0.38, 0.38, 0.18, 0.06]),
    )
    horas = np.where(
        equipo_col == "Móvil",
        rng.gamma(shape=3.0, scale=14.0, size=rows).round(1),
        rng.gamma(shape=2.0, scale=7.0, size=rows).round(1),
    )

    df = pd.DataFrame({
        "id_ticket": [f"LAT-TCK-{i:05d}" for i in range(1, rows + 1)],
        "creado_en": pd.date_range("2024-06-01", periods=rows, freq="3h30min"),
        "pais": rng.choice(paises, size=rows, p=[0.35, 0.20, 0.20, 0.15, 0.10]),
        "categoria": rng.choice(categorias, size=rows, p=[0.38, 0.15, 0.27, 0.10, 0.10]),
        "prioridad": prioridad_col,
        "equipo_asignado": equipo_col,
        "estado": rng.choice(estados, size=rows, p=[0.22, 0.28, 0.35, 0.15]),
        "horas_resolucion": horas,
        "satisfaccion_cliente": rng.choice(
            [1, 2, 3, 4, 5, None],
            size=rows,
            p=[0.12, 0.18, 0.22, 0.26, 0.14, 0.08],
        ),
    })
    return df


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    datasets = {
        # HQ datasets (English)
        "sales.csv": generate_sales(),
        "employees.csv": generate_employees(),
        "tickets.csv": generate_tickets(),
        # LATAM datasets (Spanish)
        "latam_ventas.csv": generate_latam_ventas(),
        "latam_empleados.csv": generate_latam_empleados(),
        "latam_tickets.csv": generate_latam_tickets(),
    }

    for name, df in datasets.items():
        path = DATA_DIR / name
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"[OK] Wrote {path} ({len(df)} rows, {len(df.columns)} cols)")


if __name__ == "__main__":
    main()

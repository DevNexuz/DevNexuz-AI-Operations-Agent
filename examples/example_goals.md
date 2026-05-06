# 📚 Example Goals

Copy any of these into the `--goal` argument to see the agent in action.

```bash
python main.py --goal "<paste any goal here>"
```

The `data/` folder contains two sets of datasets:
- **HQ (English):** `sales.csv`, `employees.csv`, `tickets.csv`
- **LATAM (Spanish):** `latam_ventas.csv`, `latam_empleados.csv`, `latam_tickets.csv`

Both sets work the same way — the agent reads whatever columns your CSV has.

---

## 🌐 HQ Datasets (English)

🛒 **Sales analysis (data/sales.csv)**
Analyze data/sales.csv and identify the top 3 performing regions, plus any unusually large orders. Generate a report with charts.

Look at data/sales.csv. Which product generates the most revenue, and through which channel? Build a Markdown report.

Using data/sales.csv, find the top 5 products by revenue, detect anomalies in revenue, and write a brief executive report.

---

👥 **HR insights (data/employees.csv)**
Analyze data/employees.csv. Find any salary anomalies and break down average salary by department. Produce a report.

From data/employees.csv, identify the 5 highest-performing employees and report on average performance per department.

---

🎫 **Support operations (data/tickets.csv)**
Analyze data/tickets.csv: which team is overloaded, which categories dominate, and what is the average resolution time? Write a report.

Using data/tickets.csv, summarize ticket volume by category and detect any anomalies in resolution time.

---

## 🌎 Datasets LATAM (Español)

🛒 **Análisis de ventas (data/latam_ventas.csv)**
Analiza data/latam_ventas.csv e identifica los 3 países con mayor ingreso. ¿Hay algún trimestre con caída inusual en algún mercado? Genera un reporte con gráfica.

Usando data/latam_ventas.csv, encuentra las 5 órdenes con mayores ingresos, detecta anomalías y genera un reporte ejecutivo en español.

¿Qué producto genera más ingresos en data/latam_ventas.csv y a través de qué canal? Compara el desempeño por país y escribe un reporte en Markdown.

---

👥 **Recursos Humanos (data/latam_empleados.csv)**
Analiza data/latam_empleados.csv. Detecta anomalías salariales y calcula el salario promedio por departamento. Genera un reporte.

Usando data/latam_empleados.csv, identifica qué departamento tiene mayor rotación (años_en_empresa más bajos) y cuáles empleados tienen los salarios más atípicos.

---

🎫 **Operaciones de soporte (data/latam_tickets.csv)**
Analiza data/latam_tickets.csv: ¿qué equipo está sobrecargado, qué categorías dominan y cuál es el tiempo promedio de resolución? Escribe un reporte.

Usando data/latam_tickets.csv, resume el volumen de tickets por país y detecta anomalías en el tiempo de resolución. Genera un reporte en español.

---

## 💡 Tips para escribir tus propios goals

Nombra el archivo explícitamente (ej. `data/latam_ventas.csv`) — el agente no adivina rutas.

Sé específico con el entregable ("un reporte Markdown con gráfica" funciona mejor que "dame insights").

Puedes combinar varios pedidos en un solo goal — el planner lo maneja.

Mantén el goal en 2-3 oraciones máximo — goals más largos tienden a diluir el foco.

Puedes escribir tu goal en español o inglés indistintamente.

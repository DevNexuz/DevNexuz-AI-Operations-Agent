# 📚 Example Goals

Copy any of these into the `--goal` argument to see the agent in action.

```bash
python main.py --goal "<paste any goal here>"
```

---

🛒 **Sales analysis (data/sales.csv)**
Analyze data/sales.csv and identify the top 3 performing regions, plus any unusually large orders. Generate a report with charts.

Look at data/sales.csv. Which product generates the most revenue, and through which channel? Build a Markdown report.

Using data/sales.csv, find the top 5 products by revenue, detect anomalies in revenue, and write a brief executive report.

---

� **HR insights (data/employees.csv)**
Analyze data/employees.csv. Find any salary anomalies and break down average salary by department. Produce a report.

From data/employees.csv, identify the 5 highest-performing employees and report on average performance per department.

---

🎫 **Support operations (data/tickets.csv)**
Analyze data/tickets.csv: which team is overloaded, which categories dominate, and what is the average resolution time? Write a report.

Using data/tickets.csv, summarize ticket volume by category and detect any anomalies in resolution time.

---

� **Tips for writing your own goals**
Name the file explicitly (e.g. data/sales.csv) — the agent doesn't guess paths.

Be specific about the deliverable ("a Markdown report with charts" works better than "give me insights").

Combine multiple asks in one goal — the planner handles it.

Keep it under ~3 sentences — longer goals tend to dilute focus.

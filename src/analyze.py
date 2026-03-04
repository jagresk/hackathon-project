# src/analyze.py

import pandas as pd
from anomaly_detection import run_full_analysis

baselines, anomalies = run_full_analysis(
    "data/training_data.csv",
    "data/actual_data.csv"
)

print(f"\n{'='*60}")
print(f"  PREDICTIVE MAINTENANCE — ANOMALY REPORT")
print(f"{'='*60}")
print(f"  Anomalies detected: {len(anomalies)}")
print(f"{'='*60}\n")

for i, a in enumerate(anomalies, 1):
    print(f"[{i}] {a['type']} — {a['severity']}")
    print(f"    Sensor  : {a['sensor']}")
    print(f"    Rows    : {a['row_start']} – {a['row_end']}")
    print(f"    Finding : {a['description']}")
    print(f"    Action  : {a['action']}")
    print()

print(f"{'='*60}\n")
# dashboard.py
import sys
sys.path.insert(0, "/Users/jebdon/predictive-maintenance-hackathon")
import streamlit as st
import pandas as pd
from src.anomaly_detection import run_full_analysis

baselines, anomalies = run_full_analysis(
    "data/training_data.csv",
    "data/actual_data.csv"
)

st.title("Predictive Maintenance Dashboard")
st.write(f"**Anomalies detected:** {len(anomalies)}")
st.divider()

for a in anomalies:
    color = "🔴" if a["severity"] == "HIGH" else "🟡" if a["severity"] == "MEDIUM" else "🔵"
    st.subheader(f"{color} {a['type']} — {a['sensor']}")
    st.write(f"**Rows:** {a['row_start']} – {a['row_end']}")
    st.write(f"**Finding:** {a['description']}")
    st.write(f"**Action:** {a['action']}")
    st.divider()
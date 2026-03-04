import streamlit as st
import pandas as pd
import numpy as np

st.title("Predictive Maintenance Dashboard")

# simulate sensor readings
data = pd.DataFrame({
    "temperature": np.random.normal(70,2,100),
    "vibration": np.random.normal(0.3,0.05,100),
    "pressure": np.random.normal(30,1,100)
})

st.subheader("Sensor Data")
st.line_chart(data)

# health indicator
health = np.random.randint(70,100)

st.subheader("Machine Health")
st.metric("Health Score", f"{health}%")

if health < 80:
    st.error("⚠ Maintenance Recommended")
else:
    st.success("Machine Operating Normally")
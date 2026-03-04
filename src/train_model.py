import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier

# Generate simulated sensor data
n = 1000
df = pd.DataFrame({
    "temperature": np.random.normal(70, 3, n),
    "vibration": np.random.normal(0.3, 0.05, n),
    "pressure": np.random.normal(30, 2, n)
})

# Create a fake failure label
df["failure"] = ((df["temperature"] > 75) | (df["vibration"] > 0.4)).astype(int)

X = df.drop("failure", axis=1)
y = df["failure"]

model = RandomForestClassifier()
model.fit(X, y)

print("Model trained successfully")
# src/anomaly_detection.py

import pandas as pd
import numpy as np

CURRENT_COLS = [f"Current_J{i}" for i in range(6)]
TEMP_COLS    = ["Temperature_T0"] + [f"Temperature_J{i}" for i in range(1, 6)]
SPEED_COLS   = [f"Speed_J{i}" for i in range(6)]
FAULT_COLS   = ["Robot_ProtectiveStop", "grip_lost"]
TOOL_COL     = ["Tool_current"]
ALL_SENSOR_COLS = CURRENT_COLS + TEMP_COLS + SPEED_COLS + TOOL_COL


def compute_baselines(training_df):
    baselines = {}
    for col in ALL_SENSOR_COLS:
        s = training_df[col].dropna()
        baselines[col] = {
            "mean": s.mean(),
            "std":  s.std(),
            "min":  s.min(),
            "max":  s.max(),
            "upper_3s": s.mean() + 3 * s.std(),
            "lower_3s": s.mean() - 3 * s.std(),
        }
    for col in FAULT_COLS:
        flag = training_df[col].astype(str).str.lower() == "true"
        baselines[col] = {
            "rate": flag.mean(),
            "total": int(flag.sum()),
        }
    return baselines


def detect_anomalies(actual_df, baselines, window=500):
    anomalies = []
    df = actual_df.copy()

    # ── 1. ELECTRICAL OVERLOAD ────────────────────────────────────────────────
    # Require a sustained burst (>=10 consecutive rows) above 3-sigma threshold
    # to avoid single-sample noise
    for col in CURRENT_COLS:
        threshold = baselines[col]["upper_3s"]
        above = (df[col] > threshold).astype(int)
        # Find runs of consecutive hits
        run_start = None
        best_run = 0
        best_start = best_end = None
        for i, v in enumerate(above):
            if v:
                if run_start is None:
                    run_start = i
            else:
                if run_start is not None:
                    run_len = i - run_start
                    if run_len > best_run:
                        best_run = run_len
                        best_start, best_end = run_start, i - 1
                    run_start = None
        if run_start is not None:
            run_len = len(above) - run_start
            if run_len > best_run:
                best_run = run_len
                best_start, best_end = run_start, len(above) - 1

        if best_run >= 10:
            peak = df[col].iloc[best_start:best_end+1].max()
            anomalies.append({
                "type": "Electrical Overload",
                "severity": "HIGH",
                "sensor": col,
                "description": f"{col} sustained {best_run} readings above {threshold:.2f}A (3-sigma), peaking at {peak:.2f}A.",
                "action": f"Inspect motor driver for {col}. Check for mechanical binding or short circuit.",
                "row_start": int(df.index[best_start]),
                "row_end":   int(df.index[best_end]),
            })

    # ── 2. OVERHEATING ────────────────────────────────────────────────────────
    for col in TEMP_COLS:
        threshold = baselines[col]["max"] + 2.0
        hot = df[df[col] > threshold]
        if not hot.empty:
            anomalies.append({
                "type": "Overheating",
                "severity": "HIGH",
                "sensor": col,
                "description": f"{col} reached {hot[col].max():.2f}°C — exceeded {threshold:.2f}°C threshold on {len(hot)} readings.",
                "action": f"Inspect cooling fan and thermal paste on {col} motor housing.",
                "row_start": int(hot.index[0]),
                "row_end":   int(hot.index[-1]),
            })

    # ── 3. REPEATED SAFETY STOPS ──────────────────────────────────────────────
    # Look for a cluster: 10+ stops within a 200-row window (vs baseline ~0.14%)
    stops = (df["Robot_ProtectiveStop"].astype(str).str.lower() == "true")
    baseline_rate = baselines["Robot_ProtectiveStop"]["rate"]
    cluster_window = 200
    for i in range(0, len(df) - cluster_window):
        seg = stops.iloc[i:i+cluster_window]
        if seg.sum() >= 10 and seg.mean() > baseline_rate * 10:
            anomalies.append({
                "type": "Repeated Safety Stops",
                "severity": "HIGH",
                "sensor": "Robot_ProtectiveStop",
                "description": f"{int(seg.sum())} protective stops in rows {i}–{i+cluster_window} ({seg.mean()*100:.1f}% vs {baseline_rate*100:.2f}% baseline).",
                "action": "Inspect work envelope for obstacles. Review path planning and collision zones.",
                "row_start": i,
                "row_end": i + cluster_window,
            })
            break  # Report once for the cluster

    # ── 4. WEAR AND TEAR ─────────────────────────────────────────────────────
    # Compare rolling 500-row mean to global baseline mean.
    # Flag if a sustained window deviates >2 std from baseline mean.
    for col in CURRENT_COLS:
        baseline_mean = baselines[col]["mean"]
        baseline_std  = baselines[col]["std"]
        rolling_mean  = df[col].rolling(500).mean().dropna()
        deviation     = (rolling_mean - baseline_mean).abs()
        sustained     = deviation[deviation > 1.5 * baseline_std]
        if len(sustained) >= 100:
            worst_dev = deviation.max()
            anomalies.append({
                "type": "Wear and Tear",
                "severity": "MEDIUM",
                "sensor": col,
                "description": f"{col} rolling mean deviated up to {worst_dev:.3f}A from baseline ({baseline_mean:.3f}A) across {len(sustained)} readings. Gradual load shift detected.",
                "action": f"Schedule lubrication and bearing inspection for {col}.",
                "row_start": int(sustained.index[0]),
                "row_end":   int(sustained.index[-1]),
            })

    # ── 5. SENSOR FAILURE ─────────────────────────────────────────────────────
    # Only flag if there is a dense cluster (>=20 rows within 10-row gaps of each other)
    # This avoids single scattered readings that appear in training data too
    for j in range(6):
        speed_col   = f"Speed_J{j}"
        current_col = f"Current_J{j}"
        suspect = df[(df[speed_col].abs() > 1.0) & (df[current_col].abs() < 0.05)]
        if suspect.empty:
            continue
        # Find largest dense cluster
        idx = suspect.index.tolist()
        clusters, cur = [], [idx[0]]
        for i in range(1, len(idx)):
            if idx[i] - idx[i-1] <= 10:
                cur.append(idx[i])
            else:
                clusters.append(cur)
                cur = [idx[i]]
        clusters.append(cur)
        best = max(clusters, key=len)
        train_count = baselines.get(f"sensor_fail_baseline_{j}", 0)
        # Only report the cluster if it is substantially larger than training baseline
        if len(best) >= max(20, train_count * 5):
            anomalies.append({
                "type": "Sensor Failure",
                "severity": "MEDIUM",
                "sensor": speed_col,
                "description": f"J{j}: dense cluster of {len(best)} physically inconsistent readings (speed>1.0, current<0.05A) in rows {best[0]}–{best[-1]} (baseline: ~{train_count} scattered).",
                "action": f"Inspect speed encoder on Joint {j}. May require recalibration or replacement.",
                "row_start": int(best[0]),
                "row_end":   int(best[-1]),
            })

    # ── 6. ELECTRICAL NOISE ───────────────────────────────────────────────────
    # Rolling std must exceed 3x baseline std (not 2.5x) to reduce false positives
    for col in CURRENT_COLS:
        baseline_std = baselines[col]["std"]
        rolling_std = df[col].rolling(window=100).std()
        noisy = rolling_std[rolling_std > baseline_std * 3.0].dropna()
        if len(noisy) > 50:
            anomalies.append({
                "type": "Electrical Noise",
                "severity": "MEDIUM",
                "sensor": col,
                "description": f"{col} rolling std reached {noisy.max():.3f} (>{baseline_std*3:.3f}, 3x baseline). Sustained noise on {len(noisy)} readings.",
                "action": "Check wiring connections and shielding. Possible EMI interference.",
                "row_start": int(noisy.index[0]),
                "row_end":   int(noisy.index[-1]),
            })

    # ── 7. CONTROL ISSUES ────────────────────────────────────────────────────
    # Scan in rolling 500-row windows to find the specific region of oscillation.
    # Training temps have near-zero variance so any sustained ACF in actual is anomalous.
    osc_window = 500
    osc_step   = 100
    best_window_start = None
    best_window_acf   = 0.0
    best_window_sensor = None
    for i in range(0, len(df) - osc_window, osc_step):
        for col in TEMP_COLS:
            seg = df[col].iloc[i:i+osc_window]
            seg = seg - seg.mean()
            if seg.std() < 1e-6:
                continue
            acf_vals = [seg.autocorr(lag=lag) for lag in range(5, 20)]
            max_acf = max(acf_vals)
            if max_acf > best_window_acf:
                best_window_acf   = max_acf
                best_window_start = i
                best_window_sensor = col

    if best_window_acf > 0.5:
        row_end = best_window_start + osc_window
        anomalies.append({
            "type": "Control Issues",
            "severity": "HARD",
            "sensor": best_window_sensor,
            "description": f"Periodic temperature oscillation in rows {best_window_start}–{row_end} (max acf={best_window_acf:.3f}). Suggests control loop instability.",
            "action": "Review PID tuning for thermal controllers. Check for mechanical resonance or feedback loop issues.",
            "row_start": best_window_start,
            "row_end": row_end,
        })

    # ── 8. COORDINATION PROBLEMS ──────────────────────────────────────────────
    # Primary: current correlation flip. Fallback: grip_lost rate doubling
    # (grip failures indicate end-effector coordination breakdown)
    joint_pairs = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
    coord_found = False
    for j1, j2 in joint_pairs:
        col_a = f"Current_J{j1}"
        col_b = f"Current_J{j2}"
        base_corr = baselines.get(f"corr_{col_a}_{col_b}")
        if base_corr is None:
            continue
        actual_corr = df[col_a].corr(df[col_b])
        if base_corr > 0.3 and actual_corr < -0.2:
            anomalies.append({
                "type": "Coordination Problems",
                "severity": "HARD",
                "sensor": f"{col_a}/{col_b}",
                "description": f"J{j1}–J{j2} correlation flipped: baseline {base_corr:.2f} → actual {actual_corr:.2f}. Joints working against each other.",
                "action": f"Inspect mechanical coupling between Joint {j1} and Joint {j2}. Check for backlash or binding.",
                "row_start": 0,
                "row_end": len(df) - 1,
            })
            coord_found = True

    if not coord_found:
        # Fallback: find the 2000-row window with the highest grip failure density
        baseline_grip_rate = baselines["grip_lost"]["rate"]
        actual_grip = (df["grip_lost"].astype(str).str.lower() == "true").astype(int)
        grip_window = 2000
        rolling_grip = actual_grip.rolling(grip_window).sum()
        baseline_expected = baseline_grip_rate * grip_window
        max_grip_count = rolling_grip.max()
        if max_grip_count >= max(3, baseline_expected * 3):
            end_idx = int(rolling_grip.idxmax())
            start_idx = max(0, end_idx - grip_window)
            window_rate = max_grip_count / grip_window
            anomalies.append({
                "type": "Coordination Problems",
                "severity": "HARD",
                "sensor": "grip_lost",
                "description": f"{int(max_grip_count)} grip failures in rows {start_idx}–{end_idx} ({window_rate*100:.2f}% vs {baseline_grip_rate*100:.3f}% baseline). Elevated failure density indicates coordination breakdown.",
                "action": "Inspect gripper mechanism and path coordination. Check for timing misalignment between arm and gripper.",
                "row_start": start_idx,
                "row_end": end_idx,
            })

    # ── 9. EARLY DEGRADATION ─────────────────────────────────────────────────
    # Compare first segment RMS to rest of run — a spike in segment 0 is the signal
    chunk_size = len(df) // 10
    rms_segments = []
    for i in range(10):
        chunk = df[CURRENT_COLS].iloc[i*chunk_size:(i+1)*chunk_size]
        rms_segments.append(np.sqrt((chunk**2).mean().mean()))

    rest_mean = np.mean(rms_segments[1:])
    rest_std  = np.std(rms_segments[1:])
    # Flag if any segment is >3 std above the rest-of-run mean
    for i, rms in enumerate(rms_segments):
        if rms > rest_mean + 3 * rest_std:
            anomalies.append({
                "type": "Early Degradation",
                "severity": "HARD",
                "sensor": "All Joints (RMS)",
                "description": f"Segment {i} RMS ({rms:.4f}) is {(rms-rest_mean)/rest_std:.1f} std above run baseline ({rest_mean:.4f}). Unusual load spike at start of shift.",
                "action": "Schedule full system diagnostic. Review startup sequence and compare to historical RMS profiles.",
                "row_start": i * chunk_size,
                "row_end": (i + 1) * chunk_size - 1,
            })

    return anomalies


def compute_joint_correlations(training_df, baselines):
    joint_pairs = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
    for j1, j2 in joint_pairs:
        col_a = f"Current_J{j1}"
        col_b = f"Current_J{j2}"
        baselines[f"corr_{col_a}_{col_b}"] = training_df[col_a].corr(training_df[col_b])
    return baselines


def compute_sensor_fail_baselines(training_df, baselines):
    """Store per-joint sensor failure counts from training data."""
    for j in range(6):
        sc = f"Speed_J{j}"
        cc = f"Current_J{j}"
        count = len(training_df[(training_df[sc].abs() > 1.0) & (training_df[cc].abs() < 0.05)])
        baselines[f"sensor_fail_baseline_{j}"] = count
    return baselines


def run_full_analysis(training_path, actual_path):
    train  = pd.read_csv(training_path)
    actual = pd.read_csv(actual_path)

    baselines = compute_baselines(train)
    baselines = compute_joint_correlations(train, baselines)
    baselines = compute_sensor_fail_baselines(train, baselines)
    anomalies = detect_anomalies(actual, baselines)

    return baselines, anomalies
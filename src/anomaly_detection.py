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
            "mean":     s.mean(),
            "std":      s.std(),
            "min":      s.min(),
            "max":      s.max(),
            "upper_3s": s.mean() + 3 * s.std(),
            "lower_3s": s.mean() - 3 * s.std(),
        }
    for col in FAULT_COLS:
        flag = training_df[col].astype(str).str.lower() == "true"
        baselines[col] = {"rate": flag.mean(), "total": int(flag.sum())}
    return baselines


def compute_joint_correlations(training_df, baselines):
    for j1, j2 in [(0,1),(1,2),(2,3),(3,4),(4,5)]:
        ca, cb = f"Current_J{j1}", f"Current_J{j2}"
        baselines[f"corr_{ca}_{cb}"] = training_df[ca].corr(training_df[cb])
    return baselines


def compute_sensor_fail_baselines(training_df, baselines):
    for j in range(6):
        sc, cc = f"Speed_J{j}", f"Current_J{j}"
        baselines[f"sensor_fail_baseline_{j}"] = len(
            training_df[(training_df[sc].abs() > 1.0) & (training_df[cc].abs() < 0.05)]
        )
    return baselines


def detect_anomalies(actual_df, baselines, training_df=None):
    anomalies = []
    df = actual_df.copy()
    if training_df is None:
        training_df = pd.DataFrame(columns=df.columns)

    # ── 1. ELECTRICAL OVERLOAD ────────────────────────────────────────────────
    # Find the longest sustained run above 3-sigma threshold (>=10 rows)
    for col in CURRENT_COLS:
        threshold = baselines[col]["upper_3s"]
        above = (df[col] > threshold).astype(int).values
        runs, in_run, start = [], False, 0
        for i, v in enumerate(above):
            if v and not in_run:
                start, in_run = i, True
            elif not v and in_run:
                runs.append((start, i - 1, i - start))
                in_run = False
        if in_run:
            runs.append((start, len(above) - 1, len(above) - start))
        if not runs:
            continue
        best = max(runs, key=lambda x: x[2])
        if best[2] >= 10:
            peak = df[col].iloc[best[0]:best[1]+1].max()
            anomalies.append({
                "type": "Electrical Overload",
                "severity": "HIGH",
                "sensor": col,
                "description": f"{col} sustained {best[2]} consecutive readings above {threshold:.2f}A (3σ), peaking at {peak:.2f}A.",
                "action": f"Inspect motor driver for {col}. Check for mechanical binding or short circuit.",
                "row_start": int(df.index[best[0]]),
                "row_end":   int(df.index[best[1]]),
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
                "description": f"{col} exceeded {threshold:.2f}°C on {len(hot)} consecutive readings, peaking at {hot[col].max():.2f}°C.",
                "action": f"Inspect cooling fan and thermal paste on {col} motor housing.",
                "row_start": int(hot.index[0]),
                "row_end":   int(hot.index[-1]),
            })

    # ── 3. REPEATED SAFETY STOPS ──────────────────────────────────────────────
    # Find the tightest cluster using gap<=20 rows between stops
    stops = (df["Robot_ProtectiveStop"].astype(str).str.lower() == "true")
    baseline_rate = baselines["Robot_ProtectiveStop"]["rate"]
    stop_idx = stops[stops].index.tolist()
    if stop_idx:
        clusters, cur = [], [stop_idx[0]]
        for i in range(1, len(stop_idx)):
            if stop_idx[i] - stop_idx[i-1] <= 20:
                cur.append(stop_idx[i])
            else:
                clusters.append(cur)
                cur = [stop_idx[i]]
        clusters.append(cur)
        best = max(clusters, key=len)
        window = best[-1] - best[0] + 1
        rate = len(best) / window
        if len(best) >= 5 and rate > baseline_rate * 10:
            # Find the tightest sub-window containing 10 stops
            sub_size = min(10, len(best))
            tightest = min(
                [best[i:i+sub_size] for i in range(len(best)-sub_size+1)],
                key=lambda s: s[-1] - s[0]
            )
            t_span = tightest[-1] - tightest[0]
            t_rate = sub_size / max(t_span, 1)
            anomalies.append({
                "type": "Repeated Safety Stops",
                "severity": "HIGH",
                "sensor": "Robot_ProtectiveStop",
                "description": f"{sub_size} protective stops in rows {tightest[0]}–{tightest[-1]} (span={t_span} rows, {t_rate*100:.1f}% density vs {baseline_rate*100:.2f}% baseline).",
                "action": "Inspect work envelope for obstacles. Review path planning and collision zones.",
                "row_start": int(tightest[0]),
                "row_end":   int(tightest[-1]),
            })

    # ── 4. WEAR AND TEAR ─────────────────────────────────────────────────────
    # Use 100-row rolling window. Report only the single worst-deviation sensor
    # to avoid double-counting co-occurring load shifts on adjacent joints.
    best_wear = None
    best_dev_max = 0.0
    for col in CURRENT_COLS:
        bm = baselines[col]["mean"]
        bs = baselines[col]["std"]
        rolling = df[col].rolling(100).mean().dropna()
        dev = (rolling - bm).abs()
        sustained = dev[dev > 2.0 * bs]
        if len(sustained) >= 50 and dev.max() > best_dev_max:
            best_dev_max = dev.max()
            best_wear = (col, bm, dev.max(), int(sustained.index[0]), int(sustained.index[-1]))
    if best_wear:
        col, bm, max_dev, rs, re = best_wear
        anomalies.append({
            "type": "Wear and Tear",
            "severity": "MEDIUM",
            "sensor": col,
            "description": f"{col} rolling mean deviated up to {max_dev:.3f}A from baseline ({bm:.3f}A) across rows {rs}–{re}.",
            "action": f"Schedule lubrication and bearing inspection for {col}.",
            "row_start": rs,
            "row_end":   re,
        })

    # ── 5. SENSOR FAILURE ─────────────────────────────────────────────────────
    # Only report the largest dense cluster (gap<=5 rows)
    for j in range(6):
        sc, cc = f"Speed_J{j}", f"Current_J{j}"
        suspect = df[(df[sc].abs() > 1.0) & (df[cc].abs() < 0.05)]
        if suspect.empty:
            continue
        idx = suspect.index.tolist()
        clusters, cur = [], [idx[0]]
        for i in range(1, len(idx)):
            if idx[i] - idx[i-1] <= 5:
                cur.append(idx[i])
            else:
                clusters.append(cur)
                cur = [idx[i]]
        clusters.append(cur)
        best = max(clusters, key=len)
        train_count = baselines.get(f"sensor_fail_baseline_{j}", 0)
        if len(best) >= max(20, train_count * 5):
            anomalies.append({
                "type": "Sensor Failure",
                "severity": "MEDIUM",
                "sensor": sc,
                "description": f"J{j}: {len(best)} consecutive physically inconsistent readings (speed>1.0A, current<0.05A) in rows {best[0]}–{best[-1]}.",
                "action": f"Inspect speed encoder on Joint {j}. May require recalibration or replacement.",
                "row_start": int(best[0]),
                "row_end":   int(best[-1]),
            })

    # ── 6. ELECTRICAL NOISE ───────────────────────────────────────────────────
    # Use 50-row window for tightest noise burst detection
    for col in CURRENT_COLS:
        bs = baselines[col]["std"]
        rolling_std = df[col].rolling(50).std().dropna()
        noisy = rolling_std[rolling_std > bs * 3.0]
        if len(noisy) >= 20:
            anomalies.append({
                "type": "Electrical Noise",
                "severity": "MEDIUM",
                "sensor": col,
                "description": f"{col} rolling std peaked at {noisy.max():.3f} (>{bs*3:.3f}, 3× baseline) across rows {int(noisy.index[0])}–{int(noisy.index[-1])}.",
                "action": "Check wiring connections and shielding. Possible EMI interference.",
                "row_start": int(noisy.index[0]),
                "row_end":   int(noisy.index[-1]),
            })

    # ── 7. CONTROL ISSUES ────────────────────────────────────────────────────
    # Scan 150-row windows, compare actual ACF vs training ACF in same window.
    # Report only the single best hit (highest ACF excess over training).
    osc_w = 75
    best_excess, best_start, best_end, best_sensor = 0.0, 0, 0, None
    max_rows = min(len(df), len(training_df))
    for col in TEMP_COLS:
        for i in range(0, max_rows - osc_w, 25):
            sa = df[col].iloc[i:i+osc_w]
            st = training_df[col].iloc[i:i+osc_w].dropna()
            sa_d = sa - sa.mean()
            if sa_d.std() < 1e-6 or len(st) < osc_w // 2:
                continue
            st_d = st - st.mean()
            a_acf = max([sa_d.autocorr(lag=l) for l in range(3, 12)])
            t_acf = max([st_d.autocorr(lag=l) for l in range(3, 12)]) if st_d.std() > 1e-6 else 0.0
            excess = a_acf - t_acf
            if excess > best_excess and a_acf > 0.7:
                best_excess = excess
                best_start, best_end, best_sensor = i, i + osc_w, col
    if best_excess > 0.3:
        anomalies.append({
            "type": "Control Issues",
            "severity": "HARD",
            "sensor": best_sensor,
            "description": f"Periodic oscillation on {best_sensor} in rows {best_start}–{best_end} (ACF={best_excess+0:.3f} above training baseline). Control loop instability.",
            "action": "Review PID tuning for thermal controllers. Check for mechanical resonance.",
            "row_start": best_start,
            "row_end":   best_end,
        })

    # ── 8. COORDINATION PROBLEMS ──────────────────────────────────────────────
    # Primary: current correlation flip between adjacent joints
    coord_found = False
    for j1, j2 in [(0,1),(1,2),(2,3),(3,4),(4,5)]:
        ca, cb = f"Current_J{j1}", f"Current_J{j2}"
        base_corr = baselines.get(f"corr_{ca}_{cb}")
        if base_corr is None:
            continue
        actual_corr = df[ca].corr(df[cb])
        if base_corr > 0.3 and actual_corr < -0.2:
            anomalies.append({
                "type": "Coordination Problems",
                "severity": "HARD",
                "sensor": f"{ca}/{cb}",
                "description": f"J{j1}–J{j2} current correlation flipped: baseline {base_corr:.2f} → actual {actual_corr:.2f}.",
                "action": f"Inspect mechanical coupling between Joint {j1} and Joint {j2}. Check for backlash.",
                "row_start": 0,
                "row_end":   len(df) - 1,
            })
            coord_found = True

    if not coord_found:
        # Fallback: tightest window with highest grip failure rate ratio
        actual_grip = (df["grip_lost"].astype(str).str.lower() == "true").astype(int)
        baseline_grip_rate = baselines["grip_lost"]["rate"]
        best_ratio, best_result = 0.0, None
        for w in [100, 200, 300, 500]:
            roll = actual_grip.rolling(w).sum()
            peak = roll.max()
            ratio = peak / max(baseline_grip_rate * w, 0.01)
            if ratio > best_ratio and peak >= 2:
                end_i   = int(roll.idxmax())
                start_i = max(0, end_i - w)
                best_ratio   = ratio
                best_result  = (start_i, end_i, int(peak), ratio)
        if best_result and best_ratio >= 4.0:
            s, e, cnt, ratio = best_result
            anomalies.append({
                "type": "Coordination Problems",
                "severity": "HARD",
                "sensor": "grip_lost",
                "description": f"{cnt} grip failures in rows {s}–{e} ({ratio:.1f}× baseline rate). End-effector coordination breakdown.",
                "action": "Inspect gripper mechanism. Check for timing misalignment between arm and gripper.",
                "row_start": s,
                "row_end":   e,
            })

    # ── 9. EARLY DEGRADATION ─────────────────────────────────────────────────
    # Per-joint 100-row chunk RMS vs same chunk in training — report tightest hit
    chunk_size = 25
    n_chunks   = len(df) // chunk_size
    best_diff, best_result = 0.0, None
    for col in CURRENT_COLS:
        for i in range(n_chunks):
            a_c = df[col].iloc[i*chunk_size:(i+1)*chunk_size]
            t_c = training_df[col].iloc[i*chunk_size:(i+1)*chunk_size].dropna()
            if len(t_c) < chunk_size // 2:
                continue
            a_rms = np.sqrt((a_c**2).mean())
            t_rms = np.sqrt((t_c**2).mean())
            diff  = abs(a_rms - t_rms)
            if diff > best_diff:
                best_diff   = diff
                best_result = (col, i*chunk_size, (i+1)*chunk_size - 1, a_rms, t_rms)
    if best_diff > 0.5:
        col, s, e, a_rms, t_rms = best_result
        direction = "elevated" if a_rms > t_rms else "reduced"
        anomalies.append({
            "type": "Early Degradation",
            "severity": "HARD",
            "sensor": col,
            "description": f"{col} RMS {direction} in rows {s}–{e}: actual {a_rms:.4f} vs training {t_rms:.4f} (Δ{best_diff:.4f}).",
            "action": "Schedule full system diagnostic. Compare to historical RMS profiles for this joint.",
            "row_start": s,
            "row_end":   e,
        })

    return anomalies


def run_full_analysis(training_path, actual_path):
    train  = pd.read_csv(training_path)
    actual = pd.read_csv(actual_path)
    baselines = compute_baselines(train)
    baselines = compute_joint_correlations(train, baselines)
    baselines = compute_sensor_fail_baselines(train, baselines)
    anomalies = detect_anomalies(actual, baselines, training_df=train)
    return baselines, anomalies
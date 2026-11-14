"""Chapter 3: causal fault-injection experiments and event-level evaluation.

All signals are constructed teaching data. No real BMS decisions are made.
Features never use event labels, scenario names, future samples or test fitting.
"""

from pathlib import Path
from collections import defaultdict, deque
import argparse, csv, hashlib, json, math, platform, pickle, warnings
import numpy as np
import sklearn
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix

ROOT = Path(__file__).resolve().parent
FEATURES = [
    "voltage_residual_v",
    "channel_difference_v",
    "temperature_residual_c",
    "voltage_std_v",
    "temperature_slope_c_min",
]
SIGNALS = [
    "current_a",
    "soc",
    "ambient_c",
    "voltage_a_v",
    "voltage_b_v",
    "temperature_c",
    "expected_temperature_c",
]
KNOWN = ["voltage_bias", "resistance_rise", "cooling_loss"]
SCENARIOS = ["normal", "load_step", *KNOWN, "missing_data"]


def config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def write_json(p, data):
    p.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_csv(p, rows):
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def generate(cfg):
    """Device-specific random streams keep splits independent of loop order."""
    rows, events = [], []
    for split, devices in cfg["split"].items():
        for device in devices:
            did = int(device[1:])
            scenarios = SCENARIOS + (["novel_dual"] if split == "test" else [])
            for sid, scenario in enumerate(scenarios):
                rng = np.random.default_rng(cfg["seed"] + did * 100 + sid)
                session = f"{device}_{scenario}"
                soc = 0.82
                thermal = 0.0
                gain = float(rng.uniform(0.72, 1.20))
                offset = (did - 8.5) * 0.00065
                start = cfg["event_start"]
                end = cfg["event_end"]
                if scenario in KNOWN + ["novel_dual"]:
                    events.append(
                        dict(
                            event_id=session + "_E1",
                            device_id=device,
                            session_id=session,
                            split=split,
                            start_min=start,
                            end_min=end,
                            kind=scenario,
                            target="process_or_sensor_anomaly",
                            amplitude_scale=gain,
                        )
                    )
                for t in range(cfg["minutes"]):
                    current = (
                        0.7
                        + 0.22 * math.sin(t / 15)
                        + (0.85 if 35 <= t < 85 else 0.15 if t >= 85 else 0)
                    )
                    if scenario == "load_step" and 60 <= t < 82:
                        current += 1.3
                    ambient = 24.5 + 0.5 * math.sin(t / 70 + did * 0.1)
                    thermal = 0.92 * thermal + 0.08 * (0.7 * current**2)
                    expected_t = ambient + thermal
                    nominal_v = 3.45 + 0.60 * soc - 0.035 * current
                    va = nominal_v + offset + float(rng.normal(0, 0.006))
                    vb = nominal_v + offset + float(rng.normal(0, 0.005))
                    temp = (
                        expected_t
                        + 0.12 * math.sin(t / 12)
                        + float(rng.normal(0, 0.10))
                    )
                    active = start <= t < end
                    ramp = min(1.0, (t - start + 1) / 18) if active else 0.0
                    if scenario in ["voltage_bias", "novel_dual"]:
                        va += 0.085 * gain * ramp
                    if scenario == "resistance_rise":
                        va -= 0.085 * current * gain * ramp
                        vb -= 0.085 * current * gain * ramp
                    if scenario in ["cooling_loss", "novel_dual"]:
                        temp += 3.0 * gain * ramp
                    # Harmless one-minute impulse: same treatment across methods.
                    if t == 25:
                        va += 0.070
                    missing = (scenario == "missing_data" and 72 <= t < 92) or (
                        device == "D16" and scenario == "cooling_loss" and 60 <= t < 88
                    )
                    label = (
                        scenario
                        if active and scenario in KNOWN + ["novel_dual"]
                        else "normal"
                    )
                    rows.append(
                        dict(
                            device_id=device,
                            session_id=session,
                            split=split,
                            scenario=scenario,
                            minute=t,
                            current_a=current,
                            soc=soc,
                            ambient_c=ambient,
                            voltage_a_v=None if missing else va,
                            voltage_b_v=vb,
                            temperature_c=temp,
                            expected_temperature_c=expected_t,
                            label=label,
                        )
                    )
                    soc -= current / (60 * 5.0)
    return rows, events


def validate(rows, cfg):
    if not rows:
        raise ValueError("empty observations")
    allowed = {d: s for s, ds in cfg["split"].items() for d in ds}
    if len(allowed) != sum(map(len, cfg["split"].values())):
        raise ValueError("device sets overlap")
    prev = {}
    for r in rows:
        if r["device_id"] not in allowed or r["split"] != allowed[r["device_id"]]:
            raise ValueError("invalid device split")
        sid = r["session_id"]
        t = r["minute"]
        if not isinstance(t, int) or t != prev.get(sid, -1) + 1:
            raise ValueError("nonconsecutive or duplicate timestamp")
        prev[sid] = t
        for key in SIGNALS:
            v = r[key]
            if v is not None and (
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not math.isfinite(v)
            ):
                raise ValueError("invalid numeric signal: " + key)
        if r["soc"] is None or not 0 <= r["soc"] <= 1:
            raise ValueError("SOC out of range")
    return True


def features(rows, window=5):
    """One row per observation; invalid samples flush the trailing window."""
    windows = {}
    out = []
    for r in rows:
        q = windows.setdefault(r["session_id"], deque(maxlen=window))
        valid = all(r[k] is not None and math.isfinite(r[k]) for k in SIGNALS)
        if not valid:
            q.clear()
        else:
            vr = r["voltage_a_v"] - (3.45 + 0.60 * r["soc"] - 0.035 * r["current_a"])
            q.append(
                (
                    vr,
                    r["voltage_a_v"] - r["voltage_b_v"],
                    r["temperature_c"] - r["expected_temperature_c"],
                )
            )
        item = {
            k: r[k]
            for k in ["device_id", "session_id", "split", "scenario", "minute", "label"]
        }
        item["valid"] = valid and len(q) == window
        if item["valid"]:
            a = np.array(q)
            v = [
                np.median(a[:, 0]),
                np.median(a[:, 1]),
                np.median(a[:, 2]),
                np.std(a[:, 0]),
                (a[-1, 2] - a[0, 2]) / (window - 1),
            ]
            item.update(dict(zip(FEATURES, map(float, v))))
        else:
            item.update({k: None for k in FEATURES})
        out.append(item)
    return out


def fit_models(feat):
    tr = [r for r in feat if r["split"] == "train" and r["valid"]]
    x = np.array([[r[k] for k in FEATURES] for r in tr])
    y = np.array([r["label"] for r in tr])
    normal = x[np.array([r["scenario"] in ["normal", "load_step", "missing_data"] for r in tr])]
    center = np.median(normal[:, :3], axis=0)
    scale = np.maximum(
        1.4826 * np.median(abs(normal[:, :3] - center), axis=0), [0.003, 0.003, 0.06]
    )
    logistic = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=1.0, class_weight="balanced", solver="lbfgs", max_iter=1500
        ),
    )
    isolation = IsolationForest(
        n_estimators=120,
        max_samples=256,
        contamination="auto",
        random_state=17,
        n_jobs=1,
    )
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter("always")
        logistic.fit(x, y)
        isolation.fit(normal)
    return dict(
        logistic=logistic,
        isolation=isolation,
        center=center,
        scale=scale,
        train_n=len(tr),
        normal_n=len(normal),
        warnings=[str(w.message) for w in ws],
    )


def score_rows(feat, models):
    out = [dict(r) for r in feat]
    valid = [i for i, r in enumerate(feat) if r["valid"]]
    x = np.array([[feat[i][k] for k in FEATURES] for i in valid])
    probs = models["logistic"].predict_proba(x)
    classes = list(models["logistic"].classes_)
    rule = np.max(abs((x[:, :3] - models["center"]) / models["scale"]), axis=1)
    iso = -models["isolation"].score_samples(x)
    for j, i in enumerate(valid):
        pred = classes[int(np.argmax(probs[j]))]
        out[i].update(
            rule_score=float(rule[j]),
            logistic_score=float(1 - probs[j, classes.index("normal")]),
            isolation_score=float(iso[j]),
            class_prediction=pred,
            class_confidence=float(np.max(probs[j])),
        )
    for r in out:
        if not r["valid"]:
            r.update(
                rule_score=None,
                logistic_score=None,
                isolation_score=None,
                class_prediction="unavailable",
                class_confidence=None,
            )
    return out


def alarms(rows, method, threshold, persistence, clear_count=2):
    """Causal persistence, two clear samples to release, invalid data resets."""
    if method not in ["rule", "logistic", "isolation"]:
        raise ValueError("unknown detector")
    if (
        not math.isfinite(threshold)
        or persistence < 1
        or int(persistence) != persistence
        or clear_count < 1
    ):
        raise ValueError("invalid alarm parameters")
    state = {}
    out = []
    for r in rows:
        sid = r["session_id"]
        st = state.setdefault(sid, dict(up=0, down=0, on=False))
        if not r["valid"]:
            st.update(up=0, down=0, on=False)
            onset = False
        else:
            high = r[method + "_score"] >= threshold
            was = st["on"]
            st["up"] = st["up"] + 1 if high else 0
            st["down"] = 0 if high else st["down"] + 1
            if not st["on"] and st["up"] >= persistence:
                st["on"] = True
            if st["on"] and st["down"] >= clear_count:
                st["on"] = False
            onset = st["on"] and not was
        out.append(dict(r, alarm=st["on"], onset=onset))
    return out


def evaluate(rows, events):
    """Only NEW alarm onsets inside [start,end) count as event detections.

    Repeated onsets inside one event are fragmentation, not extra detections.
    False-alarm rate uses valid, non-event exposure. Sample metrics are unadjusted.
    """
    session_ids = {r["session_id"] for r in rows}
    ee = [e for e in events if e["session_id"] in session_ids]
    by = defaultdict(list)
    for r in rows:
        by[r["session_id"]].append(r)
    event_results = []
    false_alarms = 0
    valid_background = 0
    tp = fp = fn = tn = 0
    for sid, rs in by.items():
        es = [e for e in ee if e["session_id"] == sid]
        for r in rs:
            inside = any(e["start_min"] <= r["minute"] < e["end_min"] for e in es)
            if r["valid"] and not inside:
                valid_background += 1
            if r["onset"] and not inside:
                false_alarms += 1
            if r["valid"]:
                if inside and r["alarm"]:
                    tp += 1
                elif inside:
                    fn += 1
                elif r["alarm"]:
                    fp += 1
                else:
                    tn += 1
        for e in es:
            hits = [
                r["minute"]
                for r in rs
                if r["onset"] and e["start_min"] <= r["minute"] < e["end_min"]
            ]
            event_results.append(
                dict(
                    e,
                    detected=bool(hits),
                    delay_min=hits[0] - e["start_min"] if hits else None,
                    onset_count=len(hits),
                    valid_event_minutes=sum(
                        r["valid"] and e["start_min"] <= r["minute"] < e["end_min"]
                        for r in rs
                    ),
                )
            )
    delays = [e["delay_min"] for e in event_results if e["detected"]]
    detected = len(delays)
    hours = valid_background / 60
    return (
        dict(
            events=len(ee),
            detected=detected,
            missed=len(ee) - detected,
            event_recall=detected / len(ee) if ee else None,
            false_alarm_episodes=false_alarms,
            normal_valid_hours=hours,
            false_alarms_per_hour=false_alarms / hours if hours else None,
            delay_mean_min=float(np.mean(delays)) if delays else None,
            delay_max_min=max(delays) if delays else None,
            fragments=sum(max(0, e["onset_count"] - 1) for e in event_results),
            valid_fraction=sum(r["valid"] for r in rows) / len(rows),
            point_counts=dict(tp=tp, fp=fp, fn=fn, tn=tn),
            point_precision=tp / (tp + fp) if tp + fp else None,
            point_recall=tp / (tp + fn) if tp + fn else None,
        ),
        event_results,
    )


def select(rows, events, cfg):
    val = [r for r in rows if r["split"] == "validation"]
    chosen = {}
    candidates = []
    for method, thresholds in cfg["thresholds"].items():
        cs = []
        for threshold in thresholds:
            for persistence in cfg["persistence_candidates"]:
                m, _ = evaluate(
                    alarms(val, method, threshold, persistence, cfg["clear_count"]),
                    events,
                )
                c = dict(
                    method=method, threshold=threshold, persistence=persistence, **m
                )
                cs.append(c)
                candidates.append(c)
        feasible = [
            c
            for c in cs
            if c["false_alarms_per_hour"] <= cfg["false_alarms_per_hour_budget"]
        ]
        # Predeclared lexicographic choice; no test feedback.
        key = lambda c: (
            -c["event_recall"],
            c["delay_mean_min"] if c["delay_mean_min"] is not None else 1e9,
            c["false_alarms_per_hour"],
            c["persistence"],
            c["threshold"],
        )
        winner = (
            min(feasible, key=key)
            if feasible
            else min(cs, key=lambda c: (c["false_alarms_per_hour"], *key(c)))
        )
        chosen[method] = dict(
            threshold=winner["threshold"],
            persistence=winner["persistence"],
            budget_met=bool(feasible),
        )
    return chosen, candidates


def diagnose(r, confidence=0.8):
    """A consistency check yields a hypothesis, never a confirmed cause."""
    if not r["valid"]:
        return "data_unavailable", "wait_for_complete_window"
    if not r["alarm"]:
        return "no_alarm", "continue_observation"
    vr, dv, tr = [r[k] for k in FEATURES[:3]]
    sensor = abs(dv) > 0.025
    resistance = vr < -0.030 and abs(dv) < 0.020
    thermal = tr > 0.8
    signatures = [
        k
        for k, ok in [
            ("voltage_bias", sensor),
            ("resistance_rise", resistance),
            ("cooling_loss", thermal),
        ]
        if ok
    ]
    if len(signatures) != 1:
        return "unknown", "independent_voltage_and_temperature_check"
    if r["class_confidence"] < confidence or r["class_prediction"] != signatures[0]:
        return "unknown", "repeat_independent_measurement"
    return signatures[0], "verify_" + signatures[0]


def run(out):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("output directory is not empty")
    cfg = config()
    rows, events = generate(cfg)
    validate(rows, cfg)
    feat = features(rows, cfg["window"])
    models = fit_models(feat)
    scored = score_rows(feat, models)
    chosen, candidates = select(scored, events, cfg)
    all_predictions = []
    results = {}
    event_log = []
    for method, params in chosen.items():
        pp = alarms(
            scored,
            method,
            params["threshold"],
            params["persistence"],
            cfg["clear_count"],
        )
        results[method] = {}
        for split in ["validation", "test"]:
            rr = [r for r in pp if r["split"] == split]
            m, ev = evaluate(rr, events)
            results[method][split] = m
            event_log.extend(dict(e, method=method) for e in ev)
        for r in pp:
            diagnosis, action = diagnose(r, cfg["diagnosis_confidence"])
            r.update(method=method, diagnosis=diagnosis, next_check=action)
        all_predictions.extend(pp)
    # Classifier matrix uses valid known-class test samples, not event counts.
    tt = [
        r
        for r in scored
        if r["split"] == "test" and r["valid"] and r["scenario"] != "novel_dual"
    ]
    labels = cfg["class_names"]
    cm = confusion_matrix(
        [r["label"] for r in tt], [r["class_prediction"] for r in tt], labels=labels
    )
    evidence = []
    for e in events:
        if e["split"] != "test":
            continue
        rr = [
            r
            for r in all_predictions
            if r["method"] == "logistic"
            and r["session_id"] == e["session_id"]
            and r["onset"]
            and e["start_min"] <= r["minute"] < e["end_min"]
        ]
        r = rr[0] if rr else None
        evidence.append(
            dict(
                event_id=e["event_id"],
                kind=e["kind"],
                onset_min=r["minute"] if r else None,
                diagnosis=r["diagnosis"] if r else "missed",
                class_prediction=r["class_prediction"] if r else None,
                confidence=r["class_confidence"] if r else None,
                next_check=r["next_check"] if r else "review_missed_event",
            )
        )
    metrics = dict(
        data_origin=cfg["data_origin"],
        counts={s: sum(r["split"] == s for r in rows) for s in cfg["split"]},
        train_n=models["train_n"],
        normal_train_n=models["normal_n"],
        selected=chosen,
        metrics=results,
        confusion_labels=labels,
        confusion_matrix=cm.tolist(),
        diagnostic_evidence=evidence,
        training_warnings=models["warnings"],
        evaluation_protocol="new onset inside [start,end), no point adjustment; rate denominator valid non-event hours",
        diagnostic_status="hypothesis_only",
    )
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "observations.csv", rows)
    write_csv(out / "events.csv", events)
    write_csv(out / "test_scores.csv", [r for r in scored if r["split"] == "test"])
    write_csv(out / "predictions.csv", all_predictions)
    write_csv(out / "event_results.csv", event_log)
    write_json(out / "metrics.json", metrics)
    write_json(out / "threshold_candidates.json", candidates)
    (out / "models.pkl").write_bytes(pickle.dumps(models, protocol=5))
    reloaded = pickle.loads((out / "models.pkl").read_bytes())
    repeat = score_rows(feat, reloaded)
    metrics["reload_max_abs"] = max(
        abs(a["logistic_score"] - b["logistic_score"])
        for a, b in zip(scored, repeat)
        if a["valid"]
    )
    write_json(out / "metrics.json", metrics)
    write_json(
        out / "manifest.json",
        dict(
            python=platform.python_version(),
            numpy=np.__version__,
            sklearn=sklearn.__version__,
            seed=cfg["seed"],
            inputs={
                n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest()
                for n in ["run.py", "config.json"]
            },
            outputs={
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(out.iterdir())
                if p.is_file()
            },
        ),
    )
    print(
        json.dumps(
            {"selected": chosen, "test": {k: v["test"] for k, v in results.items()}},
            ensure_ascii=False,
        )
    )
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results/run_001"))
    args = parser.parse_args()
    run(args.out if args.out.is_absolute() else ROOT / args.out)

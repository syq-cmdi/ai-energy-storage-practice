"""Independent event accounting and causal-boundary checks; no fixed score target."""

from pathlib import Path
import copy, csv, json, math, tempfile, hashlib
import numpy as np
import run

checks = []


def check(name, ok):
    checks.append(dict(check=name, passed=bool(ok)))
    if not ok:
        raise AssertionError(name)


def rejects(name, call):
    try:
        call()
    except (ValueError, FileExistsError):
        check(name, True)
    else:
        check(name, False)


cfg = run.config()
rows, events = run.generate(cfg)
run.validate(rows, cfg)
check("18000 constructed observations", len(rows) == 18000)
check("52 independent injection events", len(events) == 52)
sets = list(map(set, cfg["split"].values()))
check(
    "devices disjoint",
    all(not a & b for i, a in enumerate(sets) for b in sets[i + 1 :]),
)
check(
    "novel dual injection excluded from train and selection",
    all(r["split"] == "test" for r in rows if r["scenario"] == "novel_dual"),
)
check(
    "labels obey half-open event bounds",
    all(
        (r["label"] != "normal")
        == (r["scenario"] in run.KNOWN + ["novel_dual"] and 60 <= r["minute"] < 130)
        for r in rows
    ),
)
for mutation, name in [
    (lambda rr: rr[1].update(minute=0), "duplicate timestamp"),
    (lambda rr: rr[0].update(voltage_a_v=float("nan")), "NaN signal"),
    (lambda rr: rr[0].update(soc=1.2), "SOC outside range"),
    (lambda rr: rr[0].update(split="test"), "device split mismatch"),
]:
    rr = copy.deepcopy(rows[:20])
    mutation(rr)
    rejects(name, lambda: run.validate(rr, cfg))
f = run.features(rows)
session = [r for r in rows if r["session_id"] == "D13_voltage_bias"]
a = run.features(session)
b = copy.deepcopy(session)
for r in b[100:]:
    r["voltage_a_v"] += 10
fb = run.features(b)
check("future perturbation leaves history unchanged", a[:100] == fb[:100])
b = copy.deepcopy(session)
for r in b:
    r.update(label="unknown", scenario="hidden")
fb = run.features(b)
check(
    "labels and scenario not used as numeric features",
    all(
        [r[k] for k in run.FEATURES] == [s[k] for k in run.FEATURES]
        for r, s in zip(a, fb)
    ),
)
q = [r for r in f if r["session_id"] == "D13_missing_data"]
check(
    "missing samples and four recovery samples unavailable",
    all(not q[t]["valid"] for t in range(72, 96)),
)
check("fifth complete recovery sample valid", q[96]["valid"])


# Small independent timeline: q=3, release=2; reset on unavailable data.
def toy(scores, valid=None):
    return [
        dict(
            session_id="S", minute=i, valid=(valid[i] if valid else True), rule_score=s
        )
        for i, s in enumerate(scores)
    ]


t = run.alarms(toy([0, 4, 4, 4, 0, 0, 4, 4, 4]), "rule", 3, 3)
check(
    "persistence and release timeline",
    [r["alarm"] for r in t]
    == [False, False, False, True, True, False, False, False, True],
)
t = run.alarms(toy([4, 4, 4, 4, 4], [True, True, False, True, True]), "rule", 3, 3)
check("missing value resets consecutive count", not any(r["alarm"] for r in t))
rejects("invalid persistence", lambda: run.alarms(toy([1]), "rule", 1, 0))
# One event detected after 1 min; another is missed. Pre-onset alarm is not credited.
r = [
    dict(
        session_id="S",
        minute=i,
        valid=True,
        alarm=i in [0, 1, 3, 4, 8],
        onset=i in [0, 3, 8],
    )
    for i in range(12)
]
e = [
    dict(event_id="E1", session_id="S", start_min=2, end_min=5),
    dict(event_id="E2", session_id="S", start_min=9, end_min=11),
]
m, ev = run.evaluate(r, e)
check("event recall independently 1/2", m["event_recall"] == 0.5 and m["missed"] == 1)
check(
    "one detected-event delay is 1 min",
    m["delay_mean_min"] == 1 and ev[1]["delay_min"] is None,
)
check(
    "background exposure 7 min and 2 false episodes",
    m["normal_valid_hours"] == 7 / 60 and m["false_alarm_episodes"] == 2,
)
check(
    "point counts not adjusted by event hit",
    m["point_counts"] == dict(tp=2, fp=3, fn=3, tn=4),
)
m, _ = run.evaluate(r, [dict(event_id="E", session_id="S", start_min=1, end_min=3)])
check("existing pre-onset alarm does not detect event", m["detected"] == 0)
r2 = [dict(x) for x in r]
for i in range(2, 5):
    r2[i]["valid"] = False
    r2[i]["alarm"] = False
    r2[i]["onset"] = False
m, _ = run.evaluate(r2, e)
check("unavailable event is retained as missed", m["missed"] == 2)
base = dict(
    valid=True,
    alarm=True,
    class_confidence=0.99,
    class_prediction="voltage_bias",
    voltage_residual_v=0.08,
    channel_difference_v=0.08,
    temperature_residual_c=2.0,
)
check("multiple physical signatures stay unknown", run.diagnose(base)[0] == "unknown")
check(
    "single agreeing signature yields hypothesis",
    run.diagnose(dict(base, temperature_residual_c=0.1))[0] == "voltage_bias",
)
check(
    "low model score stays unknown",
    run.diagnose(dict(base, temperature_residual_c=0.1, class_confidence=0.55))[0]
    == "unknown",
)
check(
    "unavailable is distinct from normal",
    run.diagnose(dict(base, valid=False))[0] == "data_unavailable",
)
with tempfile.TemporaryDirectory(prefix="ch03_verify_") as tmp:
    out = Path(tmp) / "result"
    metrics = run.run(out)
    rejects("nonempty output protected", lambda: run.run(out))
    check("exact saved-model reload", metrics["reload_max_abs"] == 0)
    import pickle

    models = pickle.loads((out / "models.pkl").read_bytes())
    scored = run.score_rows(f, models)
    x = np.array(
        [
            [r[k] for k in run.FEATURES]
            for r in f
            if r["split"] == "train" and r["valid"]
        ]
    )
    check(
        "scaler only fit on training rows",
        np.allclose(
            models["logistic"].steps[0][1].mean_, x.mean(axis=0), rtol=0, atol=1e-12
        ),
    )
    check(
        "isolation model trained only on healthy training rows",
        models["normal_n"]
        == sum(
            r["split"] == "train" and r["valid"] and r["scenario"] in ["normal", "load_step", "missing_data"] for r in f
        ),
    )
    selected, candidates = run.select(scored, events, cfg)
    altered = [dict(r) for r in scored]
    for r in altered:
        if r["split"] == "test":
            r.update(
                rule_score=100, logistic_score=0, isolation_score=1, label="arbitrary"
            )
    check(
        "test signals and labels cannot change selection",
        run.select(altered, events, cfg)[0] == selected,
    )
    for method, p in selected.items():
        pp = run.alarms(
            [r for r in scored if r["split"] == "test"],
            method,
            p["threshold"],
            p["persistence"],
        )
        ee = [e for e in events if e["split"] == "test"]
        hits = []
        false_count = 0
        background = 0
        for e0 in ee:
            hit = [
                r["minute"] - e0["start_min"]
                for r in pp
                if r["onset"]
                and r["session_id"] == e0["session_id"]
                and e0["start_min"] <= r["minute"] < e0["end_min"]
            ]
            if hit:
                hits.append(min(hit))
        for r in pp:
            inside = any(
                e0["session_id"] == r["session_id"]
                and e0["start_min"] <= r["minute"] < e0["end_min"]
                for e0 in ee
            )
            background += int(r["valid"] and not inside)
            false_count += int(r["onset"] and not inside)
        actual = metrics["metrics"][method]["test"]
        check(
            method + " independent event ledger",
            actual["detected"] == len(hits) and actual["events"] == len(ee),
        )
        check(
            method + " independent false-alarm rate",
            abs(actual["false_alarms_per_hour"] - false_count / (background / 60))
            < 1e-12,
        )
        check(
            method + " independent detected-event delay",
            abs(actual["delay_mean_min"] - sum(hits) / len(hits)) < 1e-12,
        )
    matrix = np.array(metrics["confusion_matrix"])
    check(
        "known-class confusion matrix count",
        matrix.sum()
        == sum(
            r["valid"] and r["split"] == "test" and r["scenario"] != "novel_dual"
            for r in f
        ),
    )
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    check(
        "all declared hashes agree",
        all(
            hashlib.sha256((out / k).read_bytes()).hexdigest() == v
            for k, v in manifest["outputs"].items()
        ),
    )
report = dict(status="PASS", checks_passed=len(checks), checks=checks)
run.write_json(run.ROOT / "verification_report.json", report)
print(json.dumps(dict(status="PASS", checks_passed=len(checks))))

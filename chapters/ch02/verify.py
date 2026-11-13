"""Independent numeric and information-boundary checks for Chapter 2."""

from pathlib import Path
import tempfile, json, csv, math, pickle, copy
import numpy as np
import run

ROOT = Path(__file__).resolve().parent
checks = []


def check(name, condition):
    checks.append({"check": name, "passed": bool(condition)})
    if not condition:
        raise AssertionError(name)


def reject(name, rows):
    try:
        run.validate(rows)
    except ValueError:
        check(name, True)
    else:
        check(name, False)


with tempfile.TemporaryDirectory(prefix="practice_ch2_") as td:
    out = Path(td) / "fresh"
    m = run.run(out)
    rows = run.generate()
    x, y, meta = run.samples(rows)
    ids = np.array([r["cell_id"] for r in meta])
    cfg = json.loads((ROOT / "config.json").read_text())
    check(
        "1920 cycle records for 12 cells",
        len(rows) == 1920 and len(set(r["cell_id"] for r in rows)) == 12,
    )
    check(
        "155 targets per cell",
        all(sum(z["cell_id"] == c for z in meta) == 155 for c in set(ids)),
    )
    check(
        "no future information in windows",
        all(r["last_input_cycle"] == r["target_cycle"] - 1 for r in meta),
    )
    sets = [set(v) for v in cfg["split"].values()]
    check(
        "all split cell sets are disjoint",
        all(not a & b for i, a in enumerate(sets) for b in sets[i + 1 :]),
    )
    bundle = pickle.loads((out / "models.pkl").read_bytes())
    xf = x.reshape(len(x), -1)
    tr = np.isin(ids, cfg["split"]["train"])
    for family in ["ridge", "window_mlp"]:
        for k, model in enumerate(bundle["models"][family]["estimators"]):
            check(
                f"{family} {k} scaler sees training rows only",
                np.allclose(
                    model.steps[0][1].mean_, xf[tr].mean(0), atol=1e-12, rtol=0
                ),
            )
    pp = list(csv.DictReader((out / "predictions.csv").open()))
    for family in m["scores"]:
        for split in ["validation", "calibration", "test"]:
            rr = [r for r in pp if r["split"] == split]
            err = [100 * (float(r[family]) - float(r["target_soh"])) for r in rr]
            mae = sum(map(abs, err)) / len(err)
            rmse = math.sqrt(sum(e * e for e in err) / len(err))
            check(
                f"{family}/{split} independent MAE",
                abs(mae - m["scores"][family][split]["mae_pp"]) < 1e-10,
            )
            check(
                f"{family}/{split} independent RMSE",
                abs(rmse - m["scores"][family][split]["rmse_pp"]) < 1e-10,
            )
    check(
        "family chosen on validation only",
        m["selected_family"]
        == min(m["scores"], key=lambda f: (m["scores"][f]["validation"]["mae_pp"], f)),
    )
    for family, hp in m["selected_hyperparameters"].items():
        chosen = min(
            [r for r in m["validation_candidates"] if r["family"] == family],
            key=lambda r: (r["mae_pp"], r["hyperparameter"]),
        )
        check(
            f"{family} hyperparameter chosen using C07", hp == chosen["hyperparameter"]
        )
    check(
        "model reload agreement", all(v <= 1e-12 for v in m["reload_max_abs"].values())
    )
    sc = list(csv.DictReader((out / "soc.csv").open()))
    end = sc[-1]
    check(
        "SOC hand calculated endpoint",
        abs(float(end["reference"]) - (0.8 - 0.35 / 1.8)) < 1e-12,
    )
    check(
        "SOC sensor-bias closed form",
        abs(m["soc"]["current_bias"]["final_error_pp"] - (-0.02 / 1.8 * 100)) < 1e-10,
    )
    check(
        "SOC capacity-error closed form",
        abs(
            m["soc"]["nominal_capacity"]["final_error_pp"]
            - (0.35 / 1.8 - 0.35 / 2) * 100
        )
        < 1e-10,
    )
    check(
        "SOC initial bias stays constant",
        all(
            abs(float(r["initial_bias"]) - float(r["reference"]) - 0.05) < 1e-12
            for r in sc
        ),
    )
    # Perturb a future label: the final input window must remain bitwise unchanged.
    future = copy.deepcopy(rows)
    future[-1]["capacity_ah"] += 0.2
    xx, yy, mm = run.samples(future)
    check("last future label cannot change any input window", np.array_equal(x, xx))
    check("future label change reaches the target only", np.count_nonzero(y != yy) == 1)
    # Independent interval count and held-out threshold labels.
    rr = [r for r in pp if r["split"] == "test"]
    cover = sum(
        float(r["lower_soh"]) <= float(r["target_soh"]) <= float(r["upper_soh"])
        for r in rr
    ) / len(rr)
    check(
        "interval coverage independently recomputed",
        abs(cover - m["empirical_interval"]["test_coverage"]) < 1e-12,
    )
    for c, entry in m["rul_observed_labels"].items():
        cr = [r["cycle"] for r in rows if r["cell_id"] == c and r["capacity_ah"] <= 1.6]
        check(
            f"{c} censoring preserved",
            entry["first_observed_crossing"] == (min(cr) if cr else None)
            and entry["right_censored"] == (not bool(cr)),
        )
    bad = copy.deepcopy(rows)
    bad[1] = bad[0]
    reject("duplicate cycle rejected", bad)
    bad = copy.deepcopy(rows)
    bad[0]["capacity_ah"] = float("nan")
    reject("nonfinite capacity rejected", bad)
    bad = copy.deepcopy(rows)
    bad[0]["reference_capacity_ah"] = 0
    reject("zero reference capacity rejected", bad)
    bad = copy.deepcopy(rows)
    bad[5]["cycle"] = 999
    reject("cycle discontinuity rejected", bad)
    try:
        run.run(out)
    except ValueError:
        check("nonempty output is protected", True)
    else:
        check("nonempty output is protected", False)
    report = {
        "status": "PASS",
        "checks_passed": len(checks),
        "checks": checks,
        "temporary_directory_cleaned": True,
    }
(ROOT / "verification_report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2)
)
print(
    json.dumps({k: v for k, v in report.items() if k != "checks"}, ensure_ascii=False)
)

"""Chapter 2 reproducible teaching experiment. Data are constructed, not measured."""

from pathlib import Path
import argparse, csv, json, hashlib, platform, pickle, warnings, sys
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.exceptions import ConvergenceWarning
import sklearn
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parent


def write_json(p, obj):
    p.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )


def csv_out(p, rows):
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def generate():
    """生成12个教学电芯；容量、内阻与温度均为构造量。"""
    rows = []
    for j in range(12):
        rng = np.random.default_rng(20261114 + j)
        a = [
            0.00080,
            0.00100,
            0.00090,
            0.00070,
            0.00110,
            0.00085,
            0.00095,
            0.00078,
            0.00103,
            0.00074,
            0.00115,
            0.00088,
        ][j]
        knee = [95, 105, 100, 110, 90, 108, 102, 98, 96, 115, 85, 104][j]
        b = [
            0.000011,
            0.000010,
            0.000012,
            0.000010,
            0.000009,
            0.000013,
            0.000011,
            0.000010,
            0.000013,
            0.000009,
            0.000012,
            0.000011,
        ][j]
        for n in range(1, 161):
            h = 1 - a * n - b * max(n - knee, 0) ** 2
            temp = 25 + 2 * np.sin(n / 11 + j) + rng.normal(0, 0.25)
            capacity = 2 * h + rng.normal(0, 0.004)
            resistance = (
                0.035 + 0.14 * (1 - h) + 0.0002 * (temp - 25) + rng.normal(0, 0.0005)
            )
            rows.append(
                dict(
                    cell_id=f"C{j+1:02}",
                    cycle=n,
                    capacity_ah=capacity,
                    reference_capacity_ah=2.0,
                    resistance_ohm=resistance,
                    temperature_c=temp,
                    latent_soh=h,
                    source_kind="constructed",
                )
            )
    return rows


def validate(rows):
    """在构窗前拒绝重复键、循环断档、非有限值和非法容量。"""
    seen = set()
    last = {}
    for r in rows:
        k = (r["cell_id"], int(r["cycle"]))
        if k in seen:
            raise ValueError("duplicate cell/cycle")
        seen.add(k)
        if k[0] in last and k[1] != last[k[0]] + 1:
            raise ValueError("cycle gap or order error")
        last[k[0]] = k[1]
        for f in [
            "capacity_ah",
            "reference_capacity_ah",
            "resistance_ohm",
            "temperature_c",
        ]:
            if not np.isfinite(float(r[f])):
                raise ValueError("nonfinite " + f)
        if float(r["capacity_ah"]) <= 0 or float(r["reference_capacity_ah"]) <= 0:
            raise ValueError("nonpositive capacity")
        if r["source_kind"] != "constructed":
            raise ValueError("this protocol expects constructed data")


def samples(rows, window=5):
    """每个样本只读取目标循环之前的5条历史，返回5×3张量。"""
    validate(rows)
    x = []
    y = []
    meta = []
    ids = sorted(set(r["cell_id"] for r in rows))
    for cell in ids:
        rr = [r for r in rows if r["cell_id"] == cell]
        for k in range(window, len(rr)):
            hist = rr[k - window : k]
            x.append(
                [
                    [
                        r["capacity_ah"] / r["reference_capacity_ah"],
                        r["resistance_ohm"],
                        r["temperature_c"],
                    ]
                    for r in hist
                ]
            )
            y.append(rr[k]["capacity_ah"] / rr[k]["reference_capacity_ah"])
            meta.append(
                dict(
                    cell_id=cell,
                    target_cycle=rr[k]["cycle"],
                    last_input_cycle=hist[-1]["cycle"],
                )
            )
    return np.array(x), np.array(y), meta


def score(y, p):
    """SOH为无量纲；乘100后统一报告百分点误差。"""
    e = (p - y) * 100
    return dict(
        mae_pp=float(np.mean(np.abs(e))),
        rmse_pp=float(np.sqrt(np.mean(e * e))),
        bias_pp=float(np.mean(e)),
        max_abs_pp=float(np.max(np.abs(e))),
    )


def soc():
    """积分四段已知电流，以闭式可核对的三种偏差作对照。"""
    n = 360
    dt = 10.0
    curr = np.repeat([0.6, 1.2, -0.4, 0], 90)
    q = 1.8
    z0 = 0.8
    ref = np.r_[z0, z0 - np.cumsum(curr) * dt / (3600 * q)]
    measured = curr + 0.02
    configs = [
        ("correct", curr, q, z0),
        ("current_bias", measured, q, z0),
        ("nominal_capacity", curr, 2.0, z0),
        ("initial_bias", curr, q, 0.85),
    ]
    traj = {"reference": ref}
    metrics = {}
    for name, i, cap, start in configs:
        z = np.r_[start, start - np.cumsum(i) * dt / (3600 * cap)]
        traj[name] = z
        metrics[name] = {
            **score(ref[1:], z[1:]),
            "final_error_pp": float((z[-1] - ref[-1]) * 100),
            "final_soc": float(z[-1]),
        }
    rows = [
        {"time_s": k * dt, **{name: float(v[k]) for name, v in traj.items()}}
        for k in range(n + 1)
    ]
    return rows, metrics


def run(out):
    """按训练→验证选模→校准→冻结测试的顺序执行。"""
    if out.exists() and any(out.iterdir()):
        raise ValueError("output directory is nonempty; choose a new --out")
    out.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "config.json").read_text())
    rows = generate()
    csv_out(out / "cycles.csv", rows)
    x, y, meta = samples(rows, config["window"])
    xf = x.reshape(len(x), -1)
    base = x[:, -1, 0]
    delta = (y - base) * 100
    ids = np.array([r["cell_id"] for r in meta])
    masks = {key: np.isin(ids, cells) for key, cells in config["split"].items()}
    sets = list(config["split"].values())
    assert sum(map(len, sets)) == len(set(sum(sets, [])))
    # 学习目标为下一循环相对末次观测的变化量，单位是百分点。
    # 这条残差路径对应书稿图2.7；测试数据不参与任何拟合。
    models = {}
    validation = []
    captured = []
    with threadpool_limits(limits=1):
        for family in ["ridge", "forest", "window_mlp"]:
            choices = []
            for hp in config["candidates"][family]:
                fits = []
                vp = []
                seeds = (
                    config["seeds"] if family == "window_mlp" else [config["seeds"][0]]
                )
                for seed in seeds:
                    if family == "ridge":
                        m = make_pipeline(StandardScaler(), Ridge(alpha=hp))
                    elif family == "forest":
                        m = RandomForestRegressor(
                            n_estimators=80,
                            max_depth=hp,
                            min_samples_leaf=8,
                            random_state=seed,
                            n_jobs=1,
                        )
                    else:
                        m = make_pipeline(
                            StandardScaler(),
                            MLPRegressor(
                                hidden_layer_sizes=(16,),
                                activation="tanh",
                                solver="lbfgs",
                                alpha=hp,
                                max_iter=1200,
                                max_fun=20000,
                                random_state=seed,
                                tol=1e-7,
                            ),
                        )
                    with warnings.catch_warnings(record=True) as ww:
                        warnings.simplefilter("always")
                        m.fit(xf[masks["train"]], delta[masks["train"]])
                    captured.extend(
                        [
                            {
                                "family": family,
                                "hp": hp,
                                "seed": seed,
                                "warning": str(w.message),
                            }
                            for w in ww
                        ]
                    )
                    fits.append(m)
                    vp.append(m.predict(xf[masks["validation"]]))
                pred = base[masks["validation"]] + np.mean(vp, axis=0) / 100
                val = score(y[masks["validation"]], pred)
                row = {"family": family, "hyperparameter": hp, **val}
                validation.append(row)
                choices.append((val["mae_pp"], hp, fits))
            choices.sort(key=lambda v: (v[0], v[1]))
            models[family] = {
                "hyperparameter": choices[0][1],
                "estimators": choices[0][2],
            }
        preds = {"persistence": base}
        for fam, obj in models.items():
            preds[fam] = (
                base + np.mean([m.predict(xf) for m in obj["estimators"]], axis=0) / 100
            )
        # Model family selection uses validation only; calibration and test are untouched until this point.
        family_scores = {
            fam: score(y[masks["validation"]], p[masks["validation"]])["mae_pp"]
            for fam, p in preds.items()
        }
        chosen = min(family_scores, key=lambda f: (family_scores[f], f))
        residual = (
            np.abs(preds[chosen][masks["calibration"]] - y[masks["calibration"]]) * 100
        )
        radius = float(
            np.quantile(residual, config["interval_quantile"], method="higher")
        )
        summary = {
            fam: {
                split: score(y[mask], p[mask])
                for split, mask in masks.items()
                if split != "train"
            }
            for fam, p in preds.items()
        }
        per_cell = {
            fam: {
                cell: score(y[ids == cell], p[ids == cell])
                for cell in config["split"]["test"]
            }
            for fam, p in preds.items()
        }
        # Frozen models under a resistance-sensor offset; labels and other features stay unchanged.
        xp = x.copy()
        xp[:, :, 1] += 0.02
        xp = xp.reshape(len(xp), -1)
        shifted = {
            fam: score(
                y[masks["test"]],
                (
                    base
                    + np.mean([m.predict(xp) for m in o["estimators"]], axis=0) / 100
                )[masks["test"]],
            )
            for fam, o in models.items()
        }
        seeds_result = []
        for seed, m in zip(config["seeds"], models["window_mlp"]["estimators"]):
            pp = base + m.predict(xf) / 100
            seeds_result.append(
                {"seed": seed, **score(y[masks["test"]], pp[masks["test"]])}
            )
        bundle = {
            "models": models,
            "selected_family": chosen,
            "feature_order": ["soh", "resistance_ohm", "temperature_c"],
            "window": config["window"],
            "config": config,
        }
        (out / "models.pkl").write_bytes(pickle.dumps(bundle, protocol=5))
        reload = pickle.loads((out / "models.pkl").read_bytes())
        reload_max = {}
        for fam, obj in reload["models"].items():
            p2 = (
                base + np.mean([m.predict(xf) for m in obj["estimators"]], axis=0) / 100
            )
            reload_max[fam] = float(np.max(np.abs(p2 - preds[fam])))
    records = []
    for k, r in enumerate(meta):
        split = next(s for s, mask in masks.items() if mask[k])
        p = preds[chosen][k]
        records.append(
            {
                **r,
                "split": split,
                "target_soh": y[k],
                **{fam: float(v[k]) for fam, v in preds.items()},
                "lower_soh": p - radius / 100,
                "upper_soh": p + radius / 100,
            }
        )
    csv_out(out / "predictions.csv", records)
    sr, sm = soc()
    csv_out(out / "soc.csv", sr)
    coverage = {
        cell: float(
            np.mean(np.abs(preds[chosen][ids == cell] - y[ids == cell]) * 100 <= radius)
        )
        for cell in config["split"]["test"]
    }
    life = {}
    for cell in config["split"]["test"]:
        rr = [r for r in rows if r["cell_id"] == cell]
        cross = [r["cycle"] for r in rr if r["capacity_ah"] / 2 <= 0.8]
        life[cell] = {
            "first_observed_crossing": min(cross) if cross else None,
            "last_observed_cycle": 160,
            "right_censored": not bool(cross),
        }
    result = {
        "data_kind": "constructed",
        "split_counts": {k: int(v.sum()) for k, v in masks.items()},
        "selected_family": chosen,
        "selected_hyperparameters": {f: o["hyperparameter"] for f, o in models.items()},
        "validation_candidates": validation,
        "scores": summary,
        "per_cell_test": per_cell,
        "window_mlp_seed_scores": seeds_result,
        "sensor_offset_test": shifted,
        "empirical_interval": {
            "calibration_cell": "C08",
            "quantile": config["interval_quantile"],
            "radius_pp": radius,
            "coverage_per_cell": coverage,
            "test_coverage": float(
                np.mean(
                    np.abs(preds[chosen][masks["test"]] - y[masks["test"]]) * 100
                    <= radius
                )
            ),
            "guarantee": "empirical envelope only; serial correlation and cell shift invalidate an iid coverage claim",
        },
        "soc": sm,
        "rul_observed_labels": life,
        "reload_max_abs": reload_max,
        "warnings": captured,
    }
    write_json(out / "metrics.json", result)
    write_json(
        out / "manifest.json",
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "sklearn": sklearn.__version__,
            "inputs": {n: sha(ROOT / n) for n in ["run.py", "config.json"]},
            "outputs": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()},
        },
    )
    print(
        json.dumps(
            {
                "selected": chosen,
                "test": summary[chosen]["test"],
                "counts": result["split_counts"],
                "warnings": len(captured),
            },
            ensure_ascii=False,
        )
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="results/run_001")
    args = parser.parse_args()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    run(out)

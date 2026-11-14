"""W-C1 teaching experiment: capacity, cooling quality and causal rolling control.

All loads, tariffs, weather and investment assumptions are constructed here.
No field observations or external services are used. Units: h, kW, kWh, C, CNY.
"""

from pathlib import Path
from dataclasses import dataclass, asdict, replace
import argparse, csv, hashlib, json, platform
import numpy as np
import scipy
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import lil_matrix
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[2]
VOLUMES = [0, 10, 20, 30, 40, 50, 60]
WEIGHTS = {"cool": 150, "mild": 120, "hot": 90, "heatwave": 5}
NAMES = {
    "cool": "凉爽日",
    "mild": "温和日",
    "hot": "炎热日",
    "heatwave": "热浪日",
    "quality": "温度资格失效",
}


@dataclass(frozen=True)
class Config:
    eta_c: float = 0.95
    eta_d: float = 0.95
    loss: float = 0.002
    useful: float = 0.85
    p_chiller: float = 55.0
    p_charge: float = 30.0
    p_discharge: float = 30.0
    loop_flow: float = 3.2
    t_chiller: float = 6.0
    t_tank: float = 6.0
    t_return: float = 12.0
    t_max: float = 7.0
    pump_ratio: float = 0.015
    shortage_price: float = 100.0
    dt: float = 1.0


CFG = Config()


def capacity(volume, cfg=CFG):
    return cfg.useful * volume * 1000 * 4.18 * (cfg.t_return - cfg.t_tank) / 3600


def cop(temp):
    return np.clip(5.8 - 0.06 * (np.asarray(temp) - 25), 3.2, 6.4)


def tariff():
    h = np.arange(24)
    return np.where(h < 7, 0.35, np.where((h >= 12) & (h < 20), 1.10, 0.68))


def features(temp, hour):
    t = np.asarray(temp)
    h = np.asarray(hour)
    return np.column_stack(
        [
            t,
            np.maximum(t - 26, 0),
            np.sin(2 * np.pi * h / 24),
            np.cos(2 * np.pi * h / 24),
            np.sin(4 * np.pi * h / 24),
            np.cos(4 * np.pi * h / 24),
        ]
    )


def make_day(key, mean, seed, shock=0.0):
    h = np.arange(24)
    rng = np.random.default_rng(seed)
    baseline = mean + 5 * np.cos(2 * np.pi * (h - 15) / 24)
    # Weather forecast is issued before the operating day. Its errors are explicit.
    weather_forecast = baseline + 0.6 * np.sin(2 * np.pi * h / 24 + 0.7) + 0.3
    temp = baseline + rng.normal(0, 0.35, 24)
    occupancy = 16 * np.exp(-(((h - 14) / 5) ** 4))
    load = 18 + 1.6 * np.maximum(temp - 18, 0) + occupancy + rng.normal(0, 0.8, 24)
    load += shock * ((h >= 13) & (h < 18))
    return {
        "key": key,
        "name": NAMES.get(key, key),
        "seed": seed,
        "hour": h,
        "temp": temp,
        "weather_forecast": weather_forecast,
        "load": np.maximum(load, 10),
        "price": tariff(),
    }


def dataset():
    train = [
        make_day(f"train_{i:02d}", 21 + (i % 10) * 1.25, 100 + i) for i in range(28)
    ]
    validation = [make_day(f"validation_{i}", 24 + i * 1.8, 200 + i) for i in range(7)]
    tests = [
        make_day("cool", 22, 401),
        make_day("mild", 26, 402),
        make_day("hot", 30, 403),
        make_day("heatwave", 34, 404, shock=19),
    ]
    q = make_day("quality", 30, 403)
    tests.append(q)
    return train, validation, tests


def train_forecaster(train, validation):
    X = np.concatenate([features(d["temp"], d["hour"]) for d in train])
    y = np.concatenate([d["load"] for d in train])
    candidates = []
    models = []
    for alpha in [0.01, 0.1, 1, 10, 100]:
        m = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        m.fit(X, y)
        models.append(m)
        errors = np.concatenate(
            [
                m.predict(features(d["weather_forecast"], d["hour"])) - d["load"]
                for d in validation
            ]
        )
        candidates.append(
            {"alpha": alpha, "validation_rmse_kw": float(np.sqrt(np.mean(errors**2)))}
        )
    ix = int(np.argmin([v["validation_rmse_kw"] for v in candidates]))
    m = models[ix]
    return m, {
        "training_days": 28,
        "validation_days": 7,
        "training_rows": 672,
        "validation_rows": 168,
        "selected_alpha": candidates[ix]["alpha"],
        "candidates": candidates,
        "scaler_mean": m[0].mean_.tolist(),
        "scaler_scale": m[0].scale_.tolist(),
        "coefficients": m[1].coef_.tolist(),
        "intercept": float(m[1].intercept_),
    }


def forecast(model, day, k, horizon, bias=0.0):
    """Current request is known at interval start; correction uses only past load."""
    ix = np.arange(k, min(k + horizon, 24))
    weather = day["weather_forecast"][ix].copy()
    pred = model.predict(features(weather, ix)) * (1 + bias)
    if k:
        previous = float(
            model.predict(features([day["weather_forecast"][k - 1]], [k - 1]))[0]
        ) * (1 + bias)
        pred += (day["load"][k - 1] - previous) * np.exp(-(ix - k + 1) / 4)
    pred = np.maximum(pred, 0)
    pred[0] = day["load"][k]
    weather[0] = day["temp"][k]
    return pred, weather


def solve(load, temp, price, volume, initial=0.0, cfg=CFG, hard_service=False):
    """Six variables per interval: direct, charge, discharge, shortage, next E, mode.

    Binary mode enforces charge/discharge exclusivity. Every horizon ends empty.
    Returns optimizer result as well as physical arrays, so status is inspectable.
    """
    L = np.asarray(load, dtype=float)
    n = len(L)
    nc = 6 * n
    cap = capacity(volume, cfg)
    a = 1 - cfg.loss
    objective = np.zeros(nc)
    lb = np.zeros(nc)
    ub = np.full(nc, np.inf)
    integrality = np.zeros(nc)
    beta = np.asarray(price) * (1 / cop(temp) + cfg.pump_ratio) * cfg.dt
    objective[0::6] = beta
    objective[1::6] = beta
    objective[2::6] = np.asarray(price) * cfg.pump_ratio * cfg.dt
    objective[3::6] = cfg.shortage_price * cfg.dt
    ub[0::6] = cfg.p_chiller
    ub[1::6] = cfg.p_charge if volume else 0
    ub[2::6] = cfg.p_discharge if volume and cfg.t_tank <= cfg.t_max else 0
    ub[3::6] = 0 if hard_service else L
    ub[4::6] = cap
    ub[5::6] = 1
    integrality[5::6] = 1
    # Exact empty end condition makes inter-policy energy inventories comparable.
    ub[6 * (n - 1) + 4] = 0
    A = lil_matrix((6 * n, nc))
    low = np.full(6 * n, -np.inf)
    high = np.zeros(6 * n)
    for j in range(n):
        v = 6 * j
        r = 6 * j
        A[r, v] = 1
        A[r, v + 2] = 1
        A[r, v + 3] = 1
        low[r] = high[r] = L[j]
        A[r + 1, v + 4] = 1
        A[r + 1, v + 1] = -cfg.eta_c * cfg.dt
        A[r + 1, v + 2] = cfg.dt / cfg.eta_d
        if j:
            A[r + 1, v - 2] = -a
        low[r + 1] = high[r + 1] = a * initial if j == 0 else 0
        A[r + 2, v] = 1
        A[r + 2, v + 1] = 1
        high[r + 2] = cfg.p_chiller
        A[r + 3, v + 1] = 1
        A[r + 3, v + 5] = -cfg.p_charge
        high[r + 3] = 0
        A[r + 4, v + 2] = 1
        A[r + 4, v + 5] = cfg.p_discharge
        high[r + 4] = cfg.p_discharge
        # Flow limits use the actual stream temperature differences.
        A[r + 5, v] = 1 / (4.18 * (cfg.t_return - cfg.t_chiller))
        A[r + 5, v + 2] = 1 / (4.18 * (cfg.t_return - cfg.t_tank))
        high[r + 5] = cfg.loop_flow
    result = milp(
        objective,
        integrality=integrality,
        bounds=Bounds(lb, ub),
        constraints=LinearConstraint(A.tocsc(), low, high),
        options={"mip_rel_gap": 1e-9, "time_limit": 10},
    )
    if result.status != 0:
        return result, None
    x = result.x.reshape(n, 6)
    return result, {
        "g": x[:, 0],
        "c": x[:, 1],
        "d": x[:, 2],
        "u": x[:, 3],
        "energy": np.r_[initial, x[:, 4]],
        "mode": x[:, 5],
    }


def rule_action(load, hour, energy, volume, cfg=CFG):
    available = (1 - cfg.loss) * energy
    d = 0.0
    c = 0.0
    if 12 <= hour < 20 and cfg.t_tank <= cfg.t_max:
        d = min(load, cfg.p_discharge, available * cfg.eta_d / cfg.dt)
    g = min(max(load - d, 0), cfg.p_chiller)
    # Charge only during the morning cheap period; serve the current load first.
    if hour < 7 and volume and cfg.t_tank <= cfg.t_max:
        c = max(
            0,
            min(
                cfg.p_charge,
                cfg.p_chiller - g,
                (capacity(volume, cfg) - available) / (cfg.eta_c * cfg.dt),
            ),
        )
    flow = g / (4.18 * (cfg.t_return - cfg.t_chiller)) + d / (
        4.18 * (cfg.t_return - cfg.t_tank)
    )
    if flow > cfg.loop_flow:
        excess = (flow - cfg.loop_flow) * 4.18 * (cfg.t_return - cfg.t_tank)
        d = max(0, d - excess)
    u = max(0, load - g - d)
    end = available + cfg.eta_c * c * cfg.dt - d * cfg.dt / cfg.eta_d
    return g, c, d, u, max(0, end)


def summarize(day, out, cfg):
    g, c, d, u = [np.array(out[k]) for k in ["g", "c", "d", "u"]]
    energy = np.array(out["energy"])
    electricity = (g + c) / cop(day["temp"]) + cfg.pump_ratio * (g + c + d)
    flow_g = g / (4.18 * (cfg.t_return - cfg.t_chiller))
    flow_d = d / (4.18 * (cfg.t_return - cfg.t_tank))
    flow = flow_g + flow_d
    supply = np.divide(
        flow_g * cfg.t_chiller + flow_d * cfg.t_tank,
        flow,
        out=np.full(24, np.nan),
        where=flow > 1e-8,
    )
    residual = (
        energy[1:]
        - (1 - cfg.loss) * energy[:-1]
        - cfg.eta_c * c * cfg.dt
        + d * cfg.dt / cfg.eta_d
    )
    cost = float(np.dot(electricity, day["price"]) * cfg.dt)
    unmet = float(u.sum() * cfg.dt)
    return {
        "electricity": electricity,
        "flow": flow,
        "supply_temp": supply,
        "balance_residual": residual,
        "metrics": {
            "electricity_cost_cny": cost,
            "unmet_kwh": unmet,
            "objective_cny": cost + cfg.shortage_price * unmet,
            "electricity_kwh": float(electricity.sum() * cfg.dt),
            "peak_electric_kw": float(electricity.max()),
            "unmet_hours": int(np.sum(u > 1e-6)),
            "end_inventory_kwh": float(energy[-1]),
            "max_supply_c": (
                float(np.nanmax(supply)) if np.any(np.isfinite(supply)) else None
            ),
            "max_loop_flow_kg_s": float(flow.max()),
            "max_balance_residual_kwh": float(np.abs(residual).max()),
        },
    }


def simulate(day, volume, policy, model=None, horizon=24, bias=0.0, cfg=CFG):
    cfg = replace(cfg, t_tank=8.0) if day["key"] == "quality" else cfg
    out = {k: [] for k in ["g", "c", "d", "u"]}
    out["energy"] = [0.0]
    logs = []
    plans = []
    if policy == "perfect":
        res, plan = solve(day["load"], day["temp"], day["price"], volume, cfg=cfg)
        if plan is None:
            raise RuntimeError(f"Optimization failed: {res.status}: {res.message}")
        out = plan
        logs = [
            {
                "k": 0,
                "status": int(res.status),
                "gap": float(res.mip_gap),
                "dual_bound": float(res.mip_dual_bound),
                "objective": float(res.fun),
            }
        ]
    else:
        for k in range(24):
            if policy == "rule":
                g, c, d, u, end = rule_action(
                    day["load"][k], k, out["energy"][-1], volume, cfg
                )
            else:
                predicted, weather = forecast(model, day, k, horizon, bias)
                res, p = solve(
                    predicted,
                    weather,
                    day["price"][k : k + len(predicted)],
                    volume,
                    out["energy"][-1],
                    cfg,
                )
                if p is None:
                    raise RuntimeError(f"MPC failed k={k}: {res.status}: {res.message}")
                g, c, d, u, end = (
                    p["g"][0],
                    p["c"][0],
                    p["d"][0],
                    p["u"][0],
                    p["energy"][1],
                )
                logs.append(
                    {
                        "k": k,
                        "status": int(res.status),
                        "gap": float(res.mip_gap),
                        "dual_bound": float(res.mip_dual_bound),
                        "objective": float(res.fun),
                    }
                )
                plans.append(
                    {
                        "k": k,
                        "forecast": predicted,
                        "weather": weather,
                        "energy": p["energy"],
                        "g": p["g"],
                        "c": p["c"],
                        "d": p["d"],
                    }
                )
            for key, val in zip(["g", "c", "d", "u"], [g, c, d, u]):
                out[key].append(float(val))
            out["energy"].append(float(end))
    audit = summarize(day, out, cfg)
    return {
        "id": f"{day['key']}_{volume}_{policy}_{horizon}_{bias:+.2f}",
        "scenario": day["key"],
        "volume": volume,
        "policy": policy,
        "horizon": horizon,
        "bias": bias,
        "config": asdict(cfg),
        "capacity_kwh": capacity(volume, cfg),
        "hour": day["hour"],
        "load": day["load"],
        "temp": day["temp"],
        "price": day["price"],
        "weather_forecast": day["weather_forecast"],
        **out,
        **audit,
        "solver_log": logs,
        "plans": plans,
    }


def annualize(runs, weights=WEIGHTS, investment_scale=1.0):
    rate = 0.05
    years = 15
    crf = rate * (1 + rate) ** years / ((1 + rate) ** years - 1)
    rows = []
    for v in VOLUMES:
        invest = (8000 + 600 * v) * investment_scale if v else 0
        for policy in ["rule", "perfect", "mpc"]:
            sel = [
                next(
                    r
                    for r in runs
                    if r["scenario"] == s
                    and r["volume"] == v
                    and r["policy"] == policy
                    and r["horizon"] == 24
                    and r["bias"] == 0
                )
                for s in weights
            ]
            cost = sum(
                weights[r["scenario"]] * r["metrics"]["electricity_cost_cny"]
                for r in sel
            )
            unmet = sum(weights[r["scenario"]] * r["metrics"]["unmet_kwh"] for r in sel)
            rows.append(
                {
                    "volume": v,
                    "policy": policy,
                    "investment_cny": invest,
                    "annual_capital_cny": invest * crf,
                    "weighted_electricity_cost_cny": cost,
                    "weighted_total_cost_cny": cost + invest * crf,
                    "weighted_unmet_kwh": unmet,
                    "weight_days": sum(weights.values()),
                }
            )
    return {"rate": rate, "years": years, "crf": crf, "weights": weights, "rows": rows}


def plain(value):
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, (np.integer, np.floating)):
        return plain(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def experiment():
    train, valid, days = dataset()
    model, learning = train_forecaster(train, valid)
    runs = []
    for day in days:
        for volume in VOLUMES:
            for policy in ["rule", "perfect", "mpc"]:
                runs.append(simulate(day, volume, policy, model))
        print(f"Finished {day['key']}", flush=True)
    heat = next(d for d in days if d["key"] == "heatwave")
    for horizon in [6, 12, 24]:
        for bias in [-0.15, 0, 0.15]:
            if horizon == 24 and bias == 0:
                continue
            runs.append(simulate(heat, 20, "mpc", model, horizon, bias))
    annual = annualize(runs)
    sensitivities = [
        {"investment_scale": s, **annualize(runs, investment_scale=s)}
        for s in [0.5, 1, 2]
    ]
    return plain(
        {
            "chapter": 5,
            "version": "0.1.0",
            "data_source": "explicitly constructed teaching data",
            "config": asdict(CFG),
            "forecast_training": learning,
            "training": train,
            "validation": valid,
            "days": days,
            "runs": runs,
            "annual": annual,
            "investment_sensitivity": sensitivities,
            "runtime": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
            },
        }
    )


def write_outputs(out, data):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("Choose an empty output directory")
    out.mkdir(parents=True, exist_ok=True)
    (out / "experiment.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    summary = {
        k: v
        for k, v in data.items()
        if k not in ["training", "validation", "days", "runs"]
    }
    summary["runs"] = [
        {
            k: r[k]
            for k in [
                "id",
                "scenario",
                "volume",
                "policy",
                "horizon",
                "bias",
                "capacity_kwh",
                "metrics",
                "solver_log",
            ]
        }
        for r in data["runs"]
    ]
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (out / "dispatch.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "run_id",
                "hour",
                "load_kw",
                "direct_kw",
                "charge_kw",
                "discharge_kw",
                "unmet_kw",
                "energy_start_kwh",
                "energy_end_kwh",
                "supply_c",
                "loop_flow_kg_s",
                "electricity_kw",
            ]
        )
        for r in data["runs"]:
            for k in range(24):
                w.writerow(
                    [
                        r["id"],
                        k,
                        *[r[n][k] for n in ["load", "g", "c", "d", "u"]],
                        r["energy"][k],
                        r["energy"][k + 1],
                        r["supply_temp"][k],
                        r["flow"][k],
                        r["electricity"][k],
                    ]
                )
    manifest = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.iterdir()
        if p.is_file()
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=ROOT / "results/ch05")
    a = p.parse_args()
    if a.out.exists() and any(a.out.iterdir()):
        p.error("Output must be empty")
    summary = write_outputs(a.out, experiment())
    print(
        json.dumps(
            {"runs": len(summary["runs"]), "annual": summary["annual"]},
            ensure_ascii=False,
            indent=2,
        )
    )

"""Constructed pumped-storage teaching cases with exact finite-grid dynamic programming.

Flow is positive for pumping (upper-reservoir filling); electric power is positive
for generation. All prices, efficiencies and plant parameters are teaching inputs.
"""

from dataclasses import dataclass, asdict, replace
from pathlib import Path
from functools import lru_cache
import argparse, csv, hashlib, json, platform
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
NAMES = {
    "typical": "峰谷日",
    "flat": "平价日",
    "solar": "午间低价日",
    "lowwater": "低初始水位",
    "derated": "机组降额",
}
POLICIES = {
    "rule": "阈值规则",
    "fixed": "定参数规划",
    "head": "变水头定效率",
    "full": "变水头变效率",
}


@dataclass(frozen=True)
class Config:
    volume_max: float = 1152000.0
    area_upper: float = 48000.0
    area_lower: float = 72000.0
    head_base: float = 200.0
    head_ref: float = 220.0
    loss_coeff: float = 0.001
    pump_max: float = 150.0
    gen_max: float = 120.0
    ramp: float = 65.0
    flow_step: float = 20.0
    flow_max: float = 60.0
    dt: float = 1.0
    initial_volume: float = 576000.0
    rho: float = 1000.0
    gravity: float = 9.81


CFG = Config()


def prices():
    return np.array(
        [
            280,
            260,
            240,
            230,
            250,
            300,
            450,
            620,
            700,
            650,
            560,
            500,
            420,
            380,
            400,
            520,
            700,
            950,
            1100,
            1000,
            820,
            600,
            450,
            320,
        ],
        dtype=float,
    )


def slope(cfg=CFG):
    return 1 / cfg.area_upper + 1 / cfg.area_lower


def head(volume, cfg=CFG):
    return cfg.head_base + slope(cfg) * np.asarray(volume)


def potential(volume, cfg=CFG):
    v = np.asarray(volume)
    return (
        cfg.rho * cfg.gravity * (cfg.head_base * v + 0.5 * slope(cfg) * v * v) / 3.6e9
    )


def efficiency(flow, hm, cfg=CFG):
    q = abs(flow)
    return (
        0.91 - 0.10 * ((q - 40) / 40) ** 2 - 0.06 * ((hm - 220) / 40) ** 2,
        0.93 - 0.12 * ((q - 40) / 40) ** 2 - 0.05 * ((hm - 220) / 40) ** 2,
    )


def transition(volume, flow, cfg=CFG, model="full"):
    end = volume + flow * 3600 * cfg.dt
    hm = float(head((volume + end) / 2, cfg)) if model != "fixed" else cfg.head_ref
    loss = cfg.loss_coeff * flow**2 if model != "fixed" else 0.0
    ep, eg = efficiency(flow, hm, cfg) if model == "full" else (0.90, 0.91)
    if flow == 0:
        return {
            "end": end,
            "head": hm,
            "head_loss": 0.0,
            "efficiency": None,
            "power": 0.0,
            "delta_u": 0.0,
            "hydraulic_loss": 0.0,
            "conversion_loss": 0.0,
        }
    water_work = cfg.rho * cfg.gravity * abs(flow) * hm * cfg.dt / 1e6
    hydraulic = cfg.rho * cfg.gravity * abs(flow) * loss * cfg.dt / 1e6
    if flow > 0:
        power = -(water_work + hydraulic) / ep / cfg.dt
        conv = -power * cfg.dt - water_work - hydraulic
    else:
        power = (water_work - hydraulic) * eg / cfg.dt
        conv = water_work - hydraulic - power * cfg.dt
    return {
        "end": end,
        "head": hm,
        "head_loss": loss,
        "efficiency": ep if flow > 0 else eg,
        "power": power,
        "delta_u": water_work if flow > 0 else -water_work,
        "hydraulic_loss": hydraulic,
        "conversion_loss": conv,
    }


@lru_cache(maxsize=128)
def graph(cfg=CFG, model="full"):
    dv = cfg.flow_step * 3600 * cfg.dt
    n = int(round(cfg.volume_max / dv))
    a = int(round(cfg.flow_max / cfg.flow_step))
    if (
        abs(n * dv - cfg.volume_max) > 1e-6
        or abs(a * cfg.flow_step - cfg.flow_max) > 1e-8
    ):
        raise ValueError("Bounds must align with grid")
    actions = range(-a, a + 1)
    edges = {}
    for i in range(n + 1):
        for prev in actions:
            if not 0 <= i - prev <= n:
                continue
            pp = transition((i - prev) * dv, prev * cfg.flow_step, cfg, model)["power"]
            candidates = []
            for action in actions:
                j = i + action
                if not 0 <= j <= n or prev * action < 0:
                    continue
                tr = transition(i * dv, action * cfg.flow_step, cfg, model)
                pe = tr["power"]
                if (
                    pe > cfg.gen_max + 1e-9
                    or -pe > cfg.pump_max + 1e-9
                    or abs(pe - pp) > cfg.ramp + 1e-9
                ):
                    continue
                candidates.append(((j, action), pe))
            edges[(i, prev)] = tuple(candidates)
    return edges


def plan(price, cfg=CFG, model="full", rule=False, terminal_volume="initial"):
    price = np.asarray(price, dtype=float)
    T = len(price)
    dv = cfg.flow_step * 3600 * cfg.dt
    iv = int(round(cfg.initial_volume / dv))
    if abs(iv * dv - cfg.initial_volume) > 1e-6:
        raise ValueError("Initial volume must align with grid")
    terminal = cfg.initial_volume if terminal_volume == "initial" else terminal_volume
    if terminal is not None and abs(round(terminal / dv) * dv - terminal) > 1e-6:
        raise ValueError("Terminal volume must align with grid")
    edges = graph(cfg, model)
    values = [{} for _ in range(T + 1)]
    choice = {}
    evaluated = 0
    for state in edges:
        if state[1] == 0 and (terminal is None or abs(state[0] * dv - terminal) < 1e-6):
            values[T][state] = 0.0
    for k in range(T - 1, -1, -1):
        for state, candidates in edges.items():
            best = -np.inf
            selected = None
            for nxt, pe in candidates:
                if nxt not in values[k + 1]:
                    continue
                score = price[k] * pe * cfg.dt + values[k + 1][nxt]
                evaluated += 1
                if score > best + 1e-8:
                    best = score
                    selected = nxt
            if selected is not None:
                values[k][state] = float(best)
                choice[k, state] = selected
    state = (iv, 0)
    if state not in values[0]:
        return {
            "status": "infeasible",
            "evaluated_edges": evaluated,
            "flow": [],
            "objective_cny": None,
        }
    flows = []
    for k in range(T):
        if rule:
            feasible = [n for n, p in edges[state] if n in values[k + 1]]
            direction = 1 if price[k] <= 320 else -1 if price[k] >= 700 else 0
            wanted = [n for n in feasible if np.sign(n[1]) == direction]
            if wanted:
                nxt = min(wanted, key=lambda n: (-abs(n[1]), n[0]))
            elif (state[0], 0) in feasible:
                nxt = (state[0], 0)
            else:
                nxt = min(feasible, key=lambda n: (abs(n[0] - iv), abs(n[1]), n[1]))
        else:
            nxt = choice[k, state]
        flows.append(nxt[1] * cfg.flow_step)
        state = nxt
    replayed = replay(flows, price, cfg, model)
    return {
        "status": "rule_feasible" if rule else "optimal_on_grid",
        "flow": flows,
        "objective_cny": replayed["metrics"]["profit_cny"],
        "bellman_value_cny": values[0][iv, 0],
        "evaluated_edges": evaluated,
        "state_count": len(edges),
        "terminal_volume": terminal,
    }


def replay(flows, price, cfg=CFG, model="full"):
    volume = [cfg.initial_volume]
    power = []
    hs = []
    etas = []
    hyd = []
    conv = []
    du = []
    violations = []
    prev = 0.0
    prev_flow = 0.0
    for k, (q, p) in enumerate(zip(flows, price)):
        tr = transition(volume[-1], q, cfg, model)
        pe = tr["power"]
        end = tr["end"]
        for name, value, limit in [
            ("pump_power", -pe, cfg.pump_max),
            ("generation_power", pe, cfg.gen_max),
            ("ramp", abs(pe - prev), cfg.ramp),
            ("upper_volume", end, cfg.volume_max),
            ("lower_volume", -end, 0.0),
        ]:
            if value > limit + 1e-7:
                violations.append(
                    {
                        "hour": k,
                        "constraint": name,
                        "value": float(value),
                        "limit": limit,
                        "excess": float(value - limit),
                    }
                )
        if q * prev_flow < 0:
            violations.append(
                {
                    "hour": k,
                    "constraint": "mode_switch",
                    "value": 1.0,
                    "limit": 0.0,
                    "excess": 1.0,
                }
            )
        volume.append(end)
        power.append(pe)
        hs.append(tr["head"])
        etas.append(tr["efficiency"])
        hyd.append(tr["hydraulic_loss"])
        conv.append(tr["conversion_loss"])
        du.append(tr["delta_u"])
        prev = pe
        prev_flow = q
    power = np.asarray(power)
    price = np.asarray(price)
    Ein = float(-np.minimum(power, 0).sum() * cfg.dt)
    Eout = float(np.maximum(power, 0).sum() * cfg.dt)
    metrics = {
        "profit_cny": float((power * price).sum() * cfg.dt),
        "pump_energy_mwh": Ein,
        "generation_energy_mwh": Eout,
        "energy_output_input_ratio": Eout / Ein if Ein > 1e-10 else None,
        "round_trip_efficiency": (
            Eout / Ein if Ein > 1e-10 and abs(volume[-1] - volume[0]) < 1e-6 else None
        ),
        "delta_storage_mwh": float(
            potential(volume[-1], cfg) - potential(volume[0], cfg)
        ),
        "hydraulic_loss_mwh": float(sum(hyd)),
        "conversion_loss_mwh": float(sum(conv)),
        "end_volume_error_m3": float(volume[-1] - cfg.initial_volume),
        "violation_count": len(violations),
        "max_ramp_mw": (
            float(np.max(np.abs(np.diff(np.r_[0, power])))) if len(power) else 0.0
        ),
    }
    return {
        "flow": list(map(float, flows)),
        "price": price.tolist(),
        "volume": list(map(float, volume)),
        "head_mid": hs,
        "head_boundary": head(volume, cfg).tolist(),
        "upper_level": [
            280 + v / cfg.area_upper + (cfg.head_base - 200) for v in volume
        ],
        "lower_level": [64 + (cfg.volume_max - v) / cfg.area_lower for v in volume],
        "power": power.tolist(),
        "efficiency": etas,
        "hydraulic_loss": hyd,
        "conversion_loss": conv,
        "delta_u": du,
        "violations": violations,
        "metrics": metrics,
    }


def make_run(key, price, cfg, policy, group="scenario", terminal_volume="initial"):
    model = "full" if policy == "rule" else policy
    p = plan(price, cfg, model, policy == "rule", terminal_volume)
    if p["status"] == "infeasible":
        raise ValueError("Unexpected infeasible case " + key)
    actual = replay(p["flow"], price, cfg, "full")
    pred = replay(p["flow"], price, cfg, model)
    return {
        "id": f"{key}_{policy}_q{cfg.flow_step:g}_r{cfg.ramp:g}_h{cfg.head_base:g}",
        "scenario": key,
        "policy": policy,
        "group": group,
        "config": asdict(cfg),
        "plan": p,
        "predicted_power": pred["power"],
        "predicted_profit_cny": pred["metrics"]["profit_cny"],
        **actual,
    }


def experiment():
    base = prices()
    solar = base.copy()
    solar[10:16] = [150, 30, -80, -100, -20, 180]
    scenarios = [
        ("typical", base, CFG),
        ("flat", np.full(24, 500.0), CFG),
        ("solar", solar, CFG),
        ("lowwater", base, replace(CFG, initial_volume=288000.0)),
        ("derated", base, replace(CFG, pump_max=120.0, gen_max=96.0)),
    ]
    runs = [make_run(k, p, cfg, pol) for k, p, cfg in scenarios for pol in POLICIES]
    for h in [180.0, 200.0, 220.0]:
        for ramp in [40.0, 65.0, 100.0]:
            if h == 200 and ramp == 65:
                continue
            runs.append(
                make_run(
                    "typical",
                    base,
                    replace(CFG, head_base=h, ramp=ramp),
                    "full",
                    "sensitivity",
                )
            )
    for q in [10.0, 5.0]:
        for ramp in [40.0, 65.0]:
            runs.append(
                make_run(
                    "typical",
                    base,
                    replace(CFG, flow_step=q, ramp=ramp),
                    "full",
                    "grid",
                )
            )
    runs.append(make_run("typical", base, CFG, "full", "free_terminal", None))
    runs[-1]["id"] += "_free_terminal"
    failures = [
        {
            "case": "one_hour_unreachable_terminal",
            "config": asdict(CFG),
            "hours": 1,
            "terminal_volume": CFG.volume_max,
            "result": plan([1100], CFG, "full", terminal_volume=CFG.volume_max),
        }
    ]
    return {
        "chapter": 6,
        "version": "0.1.0",
        "source": "constructed teaching model and data",
        "config": asdict(CFG),
        "names": NAMES,
        "policies": POLICIES,
        "runs": runs,
        "failures": failures,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
    }


def write_outputs(out, data):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("Choose an empty output directory")
    out.mkdir(parents=True, exist_ok=True)
    (out / "experiment.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    summary = {k: v for k, v in data.items() if k != "runs"}
    summary["runs"] = [
        {
            k: r[k]
            for k in [
                "id",
                "scenario",
                "policy",
                "group",
                "config",
                "metrics",
                "predicted_profit_cny",
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
                "price_cny_mwh",
                "flow_m3_s",
                "power_mw",
                "volume_start_m3",
                "volume_end_m3",
                "head_mid_m",
                "efficiency",
                "hydraulic_loss_mwh",
                "conversion_loss_mwh",
            ]
        )
        for r in data["runs"]:
            for k in range(24):
                w.writerow(
                    [
                        r["id"],
                        k,
                        r["price"][k],
                        r["flow"][k],
                        r["power"][k],
                        r["volume"][k],
                        r["volume"][k + 1],
                        r["head_mid"][k],
                        r["efficiency"][k],
                        r["hydraulic_loss"][k],
                        r["conversion_loss"][k],
                    ]
                )
    (out / "manifest.json").write_text(
        json.dumps(
            {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in out.iterdir()
                if p.is_file()
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=ROOT / "results/ch06")
    a = p.parse_args()
    if a.out.exists() and any(a.out.iterdir()):
        p.error("Output must be empty")
    data = experiment()
    write_outputs(a.out, data)
    print(
        json.dumps(
            [{"id": r["id"], **r["metrics"]} for r in data["runs"]],
            ensure_ascii=False,
            indent=2,
        )
    )

"""Independent conservation checks and exhaustive small-problem comparison."""

from dataclasses import replace
from itertools import product
from pathlib import Path
import json, tempfile
import numpy as np
import run as model


def independent(volume, flow, cfg):
    end = volume + flow * 3600 * cfg.dt
    hm = cfg.head_base + (volume + end) / 2 * (1 / cfg.area_upper + 1 / cfg.area_lower)
    ep = 0.91 - 0.10 * ((abs(flow) - 40) / 40) ** 2 - 0.06 * ((hm - 220) / 40) ** 2
    eg = 0.93 - 0.12 * ((abs(flow) - 40) / 40) ** 2 - 0.05 * ((hm - 220) / 40) ** 2
    loss = cfg.loss_coeff * flow * flow
    power = (
        0.0
        if flow == 0
        else (
            -cfg.rho * cfg.gravity * flow * (hm + loss) / ep / 1e6
            if flow > 0
            else cfg.rho * cfg.gravity * (-flow) * (hm - loss) * eg / 1e6
        )
    )
    return end, hm, power


def audit(run):
    c = model.Config(**run["config"])
    v = np.array(run["volume"])
    q = np.array(run["flow"])
    p = np.array(run["power"])
    price = np.array(run["price"])
    results = {}
    results["water_balance"] = bool(np.max(np.abs(np.diff(v) - q * 3600 * c.dt)) < 1e-6)
    results["total_water"] = bool(
        np.allclose(v + (c.volume_max - v), c.volume_max, rtol=0, atol=1e-7)
    )
    results["volume_bounds"] = bool(
        np.all(v >= -1e-6) and np.all(v <= c.volume_max + 1e-6)
    )
    predicted = [independent(v[k], q[k], c) for k in range(len(q))]
    results["power_recomputed"] = bool(
        np.allclose(p, [x[2] for x in predicted], rtol=0, atol=1e-8)
    )
    results["head_recomputed"] = bool(
        np.allclose(run["head_mid"], [x[1] for x in predicted], rtol=0, atol=1e-8)
    )
    results["reservoir_levels"] = bool(
        np.allclose(
            np.array(run["upper_level"]) - run["lower_level"],
            run["head_boundary"],
            rtol=0,
            atol=1e-8,
        )
    )
    results["mode_transition"] = bool(np.all(q[1:] * q[:-1] >= 0))
    results["final_idle"] = bool(q[-1] == 0)
    results["terminal"] = bool(
        abs(v[-1] - v[0]) < 1e-6 or run["group"] == "free_terminal"
    )
    loss = np.array(run["hydraulic_loss"]) + run["conversion_loss"]
    du = np.array(run["delta_u"])
    results["energy_each_step"] = bool(np.max(np.abs(-p * c.dt - du - loss)) < 1e-8)
    expected_u = (
        c.rho
        * c.gravity
        * (
            c.head_base * (v[-1] - v[0])
            + 0.5 * (1 / c.area_upper + 1 / c.area_lower) * (v[-1] ** 2 - v[0] ** 2)
        )
        / 3.6e9
    )
    results["energy_integral"] = bool(abs(du.sum() - expected_u) < 1e-7)
    results["energy_day"] = bool(abs(-p.sum() * c.dt - expected_u - loss.sum()) < 1e-7)
    results["cash"] = bool(
        abs(np.dot(price, p) * c.dt - run["metrics"]["profit_cny"]) < 1e-6
    )
    results["loss_positive"] = bool(
        np.all(np.asarray(run["hydraulic_loss"]) >= -1e-9)
        and np.all(np.asarray(run["conversion_loss"]) >= -1e-9)
    )
    # Collect expected replay violations independently; approximations retain them.
    issues = []
    prev = 0.0
    for k, pe in enumerate(p):
        for name, value, limit in [
            ("pump_power", -pe, c.pump_max),
            ("generation_power", pe, c.gen_max),
            ("ramp", abs(pe - prev), c.ramp),
        ]:
            if value > limit + 1e-7:
                issues.append((k, name))
        prev = pe
    actual = [(x["hour"], x["constraint"]) for x in run["violations"]]
    results["violation_log"] = issues == actual
    results["full_model_feasibility"] = (
        not issues if run["policy"] in ["full", "rule"] else True
    )
    results["reported_efficiency"] = (
        run["metrics"]["round_trip_efficiency"] is None
        if run["group"] == "free_terminal"
        else True
    )
    return results


def verify(data):
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    c = model.CFG
    check("initial head is 220 m", abs(model.head(c.initial_volume) - 220) < 1e-10)
    check("one flow quantum is 72000 m3", c.flow_step * 3600 * c.dt == 72000)
    check(
        "one quantum changes head by 2.5 m",
        abs(model.head(72000) - model.head(0) - 2.5) < 1e-10,
    )
    check(
        "potential integral at initial volume is 329.616 MWh",
        abs(model.potential(c.initial_volume) - 329.616) < 1e-8,
    )
    for q in [-60, -40, -20, 0, 20, 40, 60]:
        tr = model.transition(c.initial_volume, q)
        end, hm, pe = independent(c.initial_volume, q, c)
        check(
            f"independent conversion for {q} m3/s",
            abs(tr["power"] - pe) < 1e-10 and abs(tr["end"] - end) < 1e-6,
        )
    # Exhaust all 7^4 paths using independent power and constraints.
    price = np.array([200.0, 500.0, 1100.0, 500.0])
    best = -np.inf
    feasible = 0
    for actions in product(range(-3, 4), repeat=4):
        v = c.initial_volume
        prev = 0.0
        old = 0
        cash = 0.0
        ok = True
        for a, pr in zip(actions, price):
            q = a * 20
            end, hm, p = independent(v, q, c)
            if (
                not 0 <= end <= c.volume_max
                or a * old < 0
                or -p > c.pump_max + 1e-9
                or p > c.gen_max + 1e-9
                or abs(p - prev) > c.ramp + 1e-9
            ):
                ok = False
                break
            v = end
            cash += pr * p
            prev = p
            old = a
        if ok and abs(v - c.initial_volume) < 1e-8 and old == 0:
            feasible += 1
            best = max(best, cash)
    result = model.plan(price)
    check(
        "Bellman equals exhaustive 2401-path search",
        abs(result["objective_cny"] - best) < 1e-7 and feasible > 1,
    )
    check(
        "one-hour terminal request is infeasible",
        data["failures"][0]["result"]["status"] == "infeasible",
    )
    g = model.graph()
    a = {n for n, p in g[(8, -1)]}
    b = {n for n, p in g[(8, 1)]}
    check("previous mode changes feasible actions", a != b)
    check(
        "ramp includes initial idle boundary",
        all(
            abs(model.transition(c.initial_volume, q)["power"]) <= 65 + 1e-8
            for q in [n[1] * 20 for n, p in g[(8, 0)]]
        ),
    )
    flags = [audit(r) for r in data["runs"]]
    for k in flags[0]:
        check("all trajectories: " + k, all(f[k] for f in flags))
    get = lambda s, p: next(
        r
        for r in data["runs"]
        if r["group"] == "scenario" and r["scenario"] == s and r["policy"] == p
    )
    for s in model.NAMES:
        optimum = get(s, "full")["metrics"]["profit_cny"]
        for p in model.POLICIES:
            r = get(s, p)
            if r["metrics"]["violation_count"] == 0:
                check(
                    f"full model dominates feasible replay {s}/{p}",
                    optimum >= r["metrics"]["profit_cny"] - 1e-6,
                )
    check(
        "flat prices lead to idle optimum",
        abs(get("flat", "full")["metrics"]["profit_cny"]) < 1e-8
        and sum(abs(x) for x in get("flat", "full")["flow"]) == 0,
    )
    check(
        "equal typical fixed and full schedules retained",
        get("typical", "fixed")["flow"] == get("typical", "full")["flow"],
    )
    check(
        "solar fixed replay retains violation",
        get("solar", "fixed")["metrics"]["violation_count"] > 0,
    )
    check(
        "low-water fixed replay retains violation",
        get("lowwater", "fixed")["metrics"]["violation_count"] > 0,
    )
    check(
        "derating reduces feasible optimum",
        get("derated", "full")["metrics"]["profit_cny"]
        <= get("typical", "full")["metrics"]["profit_cny"],
    )
    for ramp in [40, 65]:
        rs = [
            r
            for r in data["runs"]
            if r["scenario"] == "typical"
            and r["policy"] == "full"
            and r["config"]["head_base"] == 200
            and r["config"]["ramp"] == ramp
            and r["group"] != "free_terminal"
        ]
        rs = sorted(rs, key=lambda r: -r["config"]["flow_step"])
        vs = [r["metrics"]["profit_cny"] for r in rs]
        check(
            f"nested flow grid monotonic at ramp {ramp}",
            all(b >= a - 1e-6 for a, b in zip(vs, vs[1:])),
        )
    free = next(r for r in data["runs"] if r["group"] == "free_terminal")
    check(
        "free endpoint reports storage depletion",
        free["metrics"]["delta_storage_mwh"] < 0
        and free["metrics"]["round_trip_efficiency"] is None,
    )
    check(
        "free endpoint ratio can exceed one",
        free["metrics"]["energy_output_input_ratio"] > 1,
    )
    import copy

    bad = copy.deepcopy(get("typical", "full"))
    bad["volume"][5] += 100
    check("corrupted water record detected", not audit(bad)["water_balance"])
    bad = copy.deepcopy(get("solar", "fixed"))
    bad["violations"] = []
    check("removed violation log detected", not audit(bad)["violation_log"])
    with tempfile.TemporaryDirectory() as t:
        p = Path(t)
        (p / "keep.txt").write_text("retained")
        try:
            model.write_outputs(p, data)
            preserved = False
        except FileExistsError:
            preserved = (p / "keep.txt").read_text() == "retained"
        check("existing outputs preserved", preserved)
    return {
        "passed": len(checks),
        "trajectory_count": len(flags),
        "trajectory_checks": len(flags) * len(flags[0]),
        "exhaustive_paths": 7**4,
        "checks": checks,
    }


if __name__ == "__main__":
    print(json.dumps(verify(model.experiment()), ensure_ascii=False, indent=2))

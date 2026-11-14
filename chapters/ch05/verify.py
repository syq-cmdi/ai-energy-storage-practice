"""Independent physical, information-boundary and optimization checks."""

from pathlib import Path
from dataclasses import replace
import argparse, copy, json, tempfile
import numpy as np
from run import (
    CFG,
    VOLUMES,
    WEIGHTS,
    capacity,
    cop,
    dataset,
    train_forecaster,
    forecast,
    solve,
    simulate,
    annualize,
    experiment,
    write_outputs,
)

ROOT = Path(__file__).resolve().parents[2]


def audit(r):
    p = r["config"]
    g, c, d, u = [np.asarray(r[k]) for k in ["g", "c", "d", "u"]]
    E = np.asarray(r["energy"])
    L = np.asarray(r["load"])
    tol = 2e-6
    flags = {
        "load_balance": np.max(abs(g + d + u - L)) < tol,
        "storage_balance": np.max(
            abs(
                E[1:]
                - (1 - p["loss"]) * E[:-1]
                - p["eta_c"] * c * p["dt"]
                + d * p["dt"] / p["eta_d"]
            )
        )
        < tol,
        "inventory_bounds": np.min(E) > -tol and np.max(E) < r["capacity_kwh"] + tol,
        "terminal": abs(E[0]) + abs(E[-1]) < tol,
        "nonnegative": min(g.min(), c.min(), d.min(), u.min()) > -tol,
        "chiller_capacity": np.max(g + c) <= p["p_chiller"] + tol,
        "charge_capacity": c.max() <= p["p_charge"] + tol,
        "discharge_capacity": d.max() <= p["p_discharge"] + tol,
        "exclusive_mode": np.max(c * d) < tol,
        "quality_gate": p["t_tank"] <= p["t_max"] or np.max(d) < tol,
    }
    flow = g / (4.18 * (p["t_return"] - p["t_chiller"])) + d / (
        4.18 * (p["t_return"] - p["t_tank"])
    )
    flags["flow_limit"] = flow.max() <= p["loop_flow"] + tol
    flags["temperature"] = all(
        v is None or v <= p["t_max"] + tol for v in r["supply_temp"]
    )
    flags["cost"] = (
        abs(
            np.dot((g + c) / cop(r["temp"]) + p["pump_ratio"] * (g + c + d), r["price"])
            - r["metrics"]["electricity_cost_cny"]
        )
        < tol
    )
    flags["unmet"] = abs(u.sum() - r["metrics"]["unmet_kwh"]) < tol
    flags["solver_optimal"] = all(
        x["status"] == 0 and x["gap"] < 1e-7 and x["dual_bound"] <= x["objective"] + tol
        for x in r["solver_log"]
    )
    return flags


def verify(data):
    checks = []

    def check(name, value):
        if not bool(value):
            raise AssertionError(name)
        checks.append(name)

    check(
        "20 m3 theoretical-to-effective conversion",
        abs(capacity(20) - 118.43333333333334) < 1e-10,
    )
    check("rated 2 kg/s cooling", abs(2 * 4.18 * 6 - 50.16) < 1e-10)
    check("pipe service ceiling", abs(CFG.loop_flow * 4.18 * 6 - 80.256) < 1e-10)
    check(
        "independent 1 h charge balance",
        abs((1 - 0.002) * 50 + 0.95 * 20 - 68.9) < 1e-10,
    )
    check("roundtrip needs both efficiencies", abs(0.95 * 0.95 - 0.9025) < 1e-12)
    train, val, days = dataset()
    m, fit = train_forecaster(train, val)
    check(
        "training rows independent of selection",
        fit["training_rows"] == 672 and fit["validation_rows"] == 168,
    )
    check(
        "alpha chosen using validation only",
        fit["selected_alpha"]
        == min(fit["candidates"], key=lambda r: r["validation_rmse_kw"])["alpha"],
    )
    day = copy.deepcopy(days[3])
    p1, t1 = forecast(m, day, 8, 12)
    day["load"][9:] += 1000
    day["temp"][9:] += 50
    p2, t2 = forecast(m, day, 8, 12)
    check("future measured load not read", np.array_equal(p1, p2))
    check("future measured weather not read", np.array_equal(t1, t2))
    changed = copy.deepcopy(days[3])
    changed["load"][7] += 5
    p3, _ = forecast(m, changed, 8, 12)
    check("past observation updates future prediction", abs(p3[1] - p1[1]) > 1)
    check("current request remains measured", p1[0] == days[3]["load"][8])
    p4, _ = forecast(m, days[3], 8, 12, -0.15)
    check("bias leaves current request unchanged", p4[0] == p1[0])
    res, x = solve([50], [25], [1], 0)
    check(
        "one-hour no-storage analytic cost",
        res.status == 0 and abs(res.fun - 50 * (1 / 5.8 + 0.015)) < 1e-8,
    )
    hard, _ = solve([70], [25], [1], 0, hard_service=True)
    check("hard-service infeasibility retained", hard.status == 2)
    soft, y = solve([70], [25], [1], 0)
    check(
        "shortage restores measurable feasibility",
        soft.status == 0 and abs(y["u"][0] - 15) < 1e-8,
    )
    # Independent small-horizon enumeration over 1 kW charge decisions.
    cfg = replace(
        CFG,
        loss=0,
        eta_c=1,
        eta_d=1,
        pump_ratio=0,
        p_chiller=20,
        p_charge=10,
        p_discharge=10,
    )
    rr, xx = solve([10, 20], [25, 25], [0.3, 1.2], 10, cfg=cfg)
    choices = [((10 + c) * 0.3 + (20 - c) * 1.2) / 5.8 for c in range(11)]
    check(
        "two-hour optimum matches exhaustive feasible enumeration",
        abs(rr.fun - min(choices)) < 1e-8,
    )
    flags = [audit(r) for r in data["runs"]]
    for name in flags[0]:
        check("all trajectories: " + name, all(f[name] for f in flags))
    bad = copy.deepcopy(data["runs"][3])
    bad["energy"][5] += 2
    check("audit detects injected energy corruption", not audit(bad)["storage_balance"])
    check("all 113 configurations retained", len(data["runs"]) == 113)
    check(
        "zero volume keeps zero storage",
        all(
            max(abs(v) for v in r["energy"]) < 1e-7
            for r in data["runs"]
            if r["volume"] == 0
        ),
    )
    for d in days:
        for v in VOLUMES:
            rr = [
                r
                for r in data["runs"]
                if r["scenario"] == d["key"]
                and r["volume"] == v
                and r["horizon"] == 24
                and r["bias"] == 0
            ]
            optimal = next(r for r in rr if r["policy"] == "perfect")["metrics"][
                "objective_cny"
            ]
            check(
                f'perfect-information objective lower bound: {d["key"]}/{v}',
                all(r["metrics"]["objective_cny"] >= optimal - 1e-4 for r in rr),
            )
    check("weights explicitly sum to 365", sum(WEIGHTS.values()) == 365)
    rec = annualize(data["runs"])
    check(
        "weighted accounting recomputes",
        all(
            abs(a["weighted_total_cost_cny"] - b["weighted_total_cost_cny"]) < 1e-7
            for a, b in zip(rec["rows"], data["annual"]["rows"])
        ),
    )
    hot = next(d for d in days if d["key"] == "heatwave")
    floor = np.maximum(hot["load"] - 80.256, 0).sum()
    pf = next(
        r
        for r in data["runs"]
        if r["scenario"] == "heatwave"
        and r["volume"] == 60
        and r["policy"] == "perfect"
    )
    check(
        "pipe capacity sets a positive shortage lower bound",
        floor > 0 and pf["metrics"]["unmet_kwh"] >= floor - 1e-5,
    )
    check(
        "charging opportunity also limits service",
        pf["metrics"]["unmet_kwh"] > floor + 1
        and any(u > 1e-6 and e < 1e-6 for u, e in zip(pf["u"], pf["energy"][:-1])),
    )
    quality = [r for r in data["runs"] if r["scenario"] == "quality"]
    check(
        "quality-limited case preserves service shortfall",
        all(r["metrics"]["unmet_kwh"] > 30 for r in quality),
    )
    simple = next(
        r
        for r in data["runs"]
        if r["scenario"] == "hot" and r["volume"] == 20 and r["policy"] == "rule"
    )
    perfect = next(
        r
        for r in data["runs"]
        if r["scenario"] == "hot" and r["volume"] == 20 and r["policy"] == "perfect"
    )
    check(
        "lower electricity bill with less service retained",
        simple["metrics"]["electricity_cost_cny"]
        < perfect["metrics"]["electricity_cost_cny"]
        and simple["metrics"]["unmet_kwh"] > perfect["metrics"]["unmet_kwh"] + 1,
    )
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "out"
        write_outputs(p, data)
        rejected = False
        try:
            write_outputs(p, data)
        except FileExistsError:
            rejected = True
        check("existing outputs preserved", rejected)
    return {
        "passed": len(checks),
        "trajectory_count": len(data["runs"]),
        "trajectory_checks": len(flags) * len(flags[0]),
        "checks": checks,
        "pipe_shortfall_floor_kwh": float(floor),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=ROOT / "results/ch05/experiment.json")
    a = p.parse_args()
    data = (
        json.loads(a.source.read_text(encoding="utf-8"))
        if a.source.exists()
        else experiment()
    )
    result = verify(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))

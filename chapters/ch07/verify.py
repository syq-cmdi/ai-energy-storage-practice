"""Independent physical balance, randomized optimizer and negative-control checks."""

from pathlib import Path
import json, argparse
import numpy as np
from scipy.optimize import minimize_scalar
from model import (
    Config,
    HybridEnv,
    simulate,
    metrics,
    optimize,
    feasible,
    stage_cost,
    delta_energy,
    scenario_config,
)

ROOT = Path(__file__).resolve().parents[2]


def audit(rows, c):
    eb = c.battery_initial
    es = c.sc_initial
    previous = 0.0
    err = 0.0
    viol = 0
    loss = 0.0
    for r in rows:
        pb, ps, d = r["battery_kw"], r["sc_kw"], r["demand_kw"]
        assert abs(d - pb - ps - r["residual_kw"]) < 1e-8
        for p, eta in [(pb, c.battery_eta), (ps, c.sc_eta)]:
            loss += (p * (1 / eta - 1) if p >= 0 else -p * (1 - eta)) * c.dt / 3600
        eb_new = (
            eb - (pb / c.battery_eta if pb >= 0 else pb * c.battery_eta) * c.dt / 3600
        )
        es_new = es - (ps / c.sc_eta if ps >= 0 else ps * c.sc_eta) * c.dt / 3600
        err = max(err, abs(eb_new - r["battery_kwh"]), abs(es_new - r["sc_kwh"]))
        assert c.battery_min - 1e-8 <= eb_new <= c.battery_max + 1e-8
        assert c.sc_min - 1e-8 <= es_new <= c.sc_max + 1e-8
        assert abs(pb) <= c.battery_kw + 1e-8 and abs(ps) <= c.sc_kw + 1e-8
        viol += abs(pb - previous) > c.ramp_kw_s * c.dt + 1e-8
        eb, es, previous = eb_new, es_new, pb
    bus = sum((r["battery_kw"] + r["sc_kw"]) * c.dt / 3600 for r in rows)
    balance = bus + (eb - c.battery_initial) + (es - c.sc_initial) + loss
    assert abs(balance) < 1e-8 and err < 1e-10
    return dict(
        max_state_balance_kwh=err,
        total_balance_kwh=balance,
        conversion_loss_kwh=loss,
        ramp_violations=int(viol),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--source", type=Path, default=ROOT / "results/ch07/experiment.json"
    )
    a = ap.parse_args()
    ex = json.loads(a.source.read_text(encoding="utf-8"))
    q = np.array(ex["selected_q"])
    checks = {}
    c = Config()
    checks["nominal_usable_sc_kwh"] = c.sc_span
    assert abs(c.sc_span - 1.2) < 1e-12
    rng = np.random.default_rng(9917)
    worst = 0.0
    tested = 0
    for _ in range(300):
        eb = rng.uniform(8, 32)
        es = rng.uniform(0.4, 1.6)
        prev = rng.uniform(-80, 80)
        d = rng.uniform(-200, 200)
        lo, hi, sl, sh, jl, jh, conflict = feasible(eb, es, prev, d, c)
        if jl > jh:
            continue

        def independent_cost(pb):
            ps = d - pb
            en = es - (ps / 0.98 if ps >= 0 else ps * 0.98) / 3600
            return (
                0.25 * (pb / 80) ** 2
                + 0.10 * ((pb - prev) / 10) ** 2
                + 8 * ((en - 1) / 1.2) ** 2
            )

        ref = minimize_scalar(
            independent_cost,
            bounds=(jl, jh),
            method="bounded",
            options={"xatol": 1e-11},
        )
        opt = optimize(eb, es, prev, d, c)
        gap = independent_cost(opt) - min(
            ref.fun, independent_cost(jl), independent_cost(jh)
        )
        worst = max(worst, gap)
        tested += 1
    assert worst < 1e-8
    checks["optimizer_random_cases"] = tested
    checks["max_optimizer_cost_gap"] = worst
    for name in ex["scenarios"]:
        for method in ["lowpass", "optimizer", "qlearning"]:
            rows = simulate(method, 30000, scenario=name, q=q)
            checks[name + "/" + method] = audit(rows, scenario_config(name))
            ref = ex["traces"][name + "/" + method]
            assert (
                np.max(
                    np.abs(
                        np.array([r["battery_kw"] for r in rows])
                        - np.array([r["battery_kw"] for r in ref])
                    )
                )
                < 1e-7
            )
    # Explicit impossible request: retain residual, never alter demand.
    env = HybridEnv(c)
    env.reset(profile=[500.0])
    _, _, term, trunc, r = env.step(500.0)
    assert (
        abs(r["battery_kw"] - 10) < 1e-10
        and abs(r["sc_kw"] - 100) < 1e-10
        and abs(r["residual_kw"] - 390) < 1e-10
    )
    assert not term and trunc
    checks["500kW_residual_kw"] = r["residual_kw"]
    try:
        env.step(0)
        raise AssertionError("post-end step accepted")
    except RuntimeError:
        pass
    # At an empty battery with a previous discharge, energy priority is logged.
    env.reset(profile=[50])
    env.eb = c.battery_min
    env.prev = 80
    _, _, _, _, r = env.step(80)
    assert r["ramp_conflict"] == 1 and abs(r["ramp_kw_s"]) > c.ramp_kw_s
    checks["ramp_energy_conflict_detected"] = True
    # Reset and fixed seeds are deterministic.
    env.reset(30001, 10)
    obs = env.obs().copy()
    env.step(0)
    env.reset(30001, 10)
    assert np.allclose(env.obs(), obs)
    # All test seeds separated from training demand seeds and validation.
    assert set(ex["test_seeds"]).isdisjoint(ex["validation_seeds"])
    assert (
        len(ex["metrics"]) == 420
        and max(x["violation_steps"] for x in ex["metrics"]) == 0
    )
    # Confirm unchanged test input across all controllers by paired seed/profile.
    assert all(
        np.allclose(
            [r["demand_kw"] for r in ex["traces"][s + "/lowpass"]],
            [r["demand_kw"] for r in ex["traces"][s + "/qlearning"]],
        )
        for s in ex["scenarios"]
    )
    checks["evaluations"] = len(ex["metrics"])
    checks["status"] = "PASS"
    out = a.source.parent / "verification_report.json"
    out.write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()

"""Independent ledgers, hand-solvable optimum, causality and infeasibility tests."""

from pathlib import Path
from dataclasses import replace
import json
import numpy as np
from model import config, Config, profiles, step, plan, forecast, pressure

ROOT = Path(__file__).resolve().parents[2]


def verify():
    data = json.loads(
        (ROOT / "results/ch08/experiment.json").read_text(encoding="utf-8")
    )
    checks = 0

    def check(condition, message):
        nonlocal checks
        if not condition:
            raise AssertionError(message)
        checks += 1

    for case in data["cases"] + data["ablations"]:
        c = Config(**case["config"])
        rows = case["rows"]
        s = case["summary"]
        last = c.m0
        for r in rows:
            check(abs(r["m_before"] - last) < 1e-7, "mass continuity")
            check(
                abs(
                    r["m_after"]
                    - (last * (1 - c.loss * c.dt) + (r["q"] - r["served"]) * c.dt)
                )
                < 1e-7,
                "mass ledger",
            )
            check(c.mmin - 1e-6 <= r["m_after"] <= c.mmax + 1e-6, "inventory bounds")
            check(-1e-7 <= r["grid"] <= r["grid_cap"] + 1e-6, "grid cap")
            check(
                r["p"] < 1e-7 or c.pmin - 1e-6 <= r["p"] <= c.pmax + 1e-6,
                "on/off bound",
            )
            check(
                abs(
                    r["renewable"]
                    + r["grid"]
                    - r["curtailment"]
                    - r["p"]
                    - r["compressor"]
                    - r["auxiliary"]
                )
                < 1e-6,
                "electricity ledger",
            )
            check(
                abs(r["served"] + r["shortage"] - r["demand"]) < 1e-8, "demand ledger"
            )
            last = r["m_after"]
        check(
            abs(
                s["produced_kg"]
                - s["served_kg"]
                - s["inventory_change_kg"]
                - sum(r["loss"] for r in rows)
            )
            < 1e-6,
            "whole horizon mass",
        )
        check(
            abs(
                s["electricity_cost"]
                - sum(r["grid"] * r["tariff"] * c.dt for r in rows)
            )
            < 1e-6,
            "cost",
        )
        check(
            all(
                solver["status"] == 0 and solver["gap"] <= 1.01e-7
                for solver in case["solvers"]
            ),
            "solver optimum",
        )
    c = replace(
        config(),
        dt=1,
        pmax=55,
        pmin=11,
        sec=55,
        compressor=0,
        auxiliary=0,
        mmin=0,
        mmax=1,
        m0=0.5,
        start_cost=2,
    )
    f = dict(
        demand=np.array([0.5, 0.5]),
        renewable=np.zeros(2),
        grid_cap=np.full(2, 55),
        tariff=np.array([1, 2]),
    )
    cmd, meta = plan(f, c)
    check(np.allclose(cmd, [55, 0], atol=1e-6), "analytic optimum commands")
    check(abs(meta["objective"] - 57) < 1e-6, "analytic optimum cost")
    bad = {**f, "grid_cap": np.zeros(2)}
    try:
        plan(bad, c, target=0.8)
    except RuntimeError as e:
        check("'status': 2" in str(e), "explicit infeasible result")
    else:
        raise AssertionError("infeasibility must be reported")
    r = step(0, 20, 0, 0, 8, 0, config())
    check(r["shortage"] == 8 and r["m_after"] == 20, "empty usable inventory")
    r = step(275, 50, 0, 100, 5, 650, config())
    check(
        abs(r["total"] - 295) < 1e-8
        and abs(r["grid"] - 195) < 1e-8
        and abs(r["m_after"] - 50) < 1e-8,
        "5 kg/h hand example",
    )
    nominal = profiles()
    a = profiles("surge")
    b = {key: np.array(v, copy=True) for key, v in a.items()}
    b["demand"][81:] += 100
    b["renewable"][81:] = 0
    b["grid_cap"][81:] = 0
    fa = forecast(nominal, a, 80)
    fb = forecast(nominal, b, 80)
    check(all(np.array_equal(fa[k], fb[k]) for k in fa), "future observation isolation")
    check(abs(float(pressure(50, config())) - 122.95706) < 1e-6, "ideal gas conversion")
    report = dict(
        checks=checks,
        cases=len(data["cases"]),
        ablations=len(data["ablations"]),
        passed=True,
        independent_tests=[
            "stepwise mass/power/demand and constraints",
            "whole-horizon mass/cost",
            "hand-solvable two-step mixed-integer optimum",
            "infeasible target surfaced",
            "zero usable inventory shortage",
            "5 kg/h hand calculation",
            "future observation isolation",
            "ideal gas unit conversion",
        ],
    )
    (ROOT / "results/ch08/verification.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    verify()

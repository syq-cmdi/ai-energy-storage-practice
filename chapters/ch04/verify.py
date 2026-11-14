"""Independent numerical and protocol checks for the W-H1 teaching experiment."""

import json
from pathlib import Path
import tempfile
import numpy as np
from scipy.integrate import quad
import run as model


def main():
    count = 0

    def check(ok, message):
        nonlocal count
        if not ok:
            raise AssertionError(message)
        count += 1

    c, ua, dt = 418.0, 0.01, 120.0
    check(
        abs(model.linear_step(50, 0.3, 20, c, ua) - 50) < 1e-12, "thermal equilibrium"
    )
    check(
        abs(model.linear_step(38, 2, 20, c, 0) - 38 - 240 / 418) < 1e-12,
        "adiabatic limit",
    )
    cooling = model.linear_step(60, 0, 20, c, ua)
    check(20 < cooling < 60, "passive cooling monotonicity")
    for bad in [(-1, 0.01, 120), (418, -0.01, 120), (418, 0.01, 0)]:
        try:
            model.linear_step(40, 1, 20, *bad)
        except ValueError:
            check(True, "invalid physical input rejected")
        else:
            check(False, "invalid physical input accepted")
    a = model.linear_step(38, 2, 20, c, ua)
    b = model.linear_step(model.linear_step(38, 2, 20, c, ua, 60), 2, 20, c, ua, 60)
    check(abs(a - b) < 1e-12, "semigroup of exact ZOH transition")
    heat = quad(
        lambda t: 2 - 0.01 * (20 + 200 + (38 - 220) * np.exp(-0.01 * t / 418) - 20),
        0,
        120,
    )[0]
    check(abs(c * (a - 38) - heat) < 1e-9, "independent quadrature of heat flow")
    u = np.array([1.0, 0.0, 0.4, 1.5])
    ta = np.full(4, 20.0)
    ref, energy = model.reference(u, ta, 35)
    check(
        np.max(abs(ref - model.simulate(u, ta, 35, c, ua))) < 1e-9,
        "DOP853 vs closed form",
    )
    refg, _ = model.reference(u, ta, 35, 0.00012)
    check(
        np.max(abs(refg - model.simulate(u, ta, 35, c, ua, 0.00012))) < 1e-7,
        "DOP853 vs RK4 nonlinear",
    )
    check(
        np.max(abs(c * np.diff(ref) - energy)) < 1e-9,
        "augmented reference energy state",
    )
    # Future observations cannot change already issued estimates.
    e = {
        "power": np.ones(50),
        "ambient": np.full(50, 20.0),
        "observed": np.full(51, 40.0),
    }
    k = model.filter_episode(e, c, ua, q=0.001)
    e2 = {**e, "observed": e["observed"].copy()}
    e2["observed"][30:] += 10
    k2 = model.filter_episode(e2, c, ua, q=0.001)
    check(
        np.allclose(k["temperature"][:30], k2["temperature"][:30], atol=0, rtol=0),
        "causal filtering",
    )
    check(np.all(k["variance"] > 0), "Joseph update positive variance")
    check(np.all((k["gain"] >= 0) & (k["gain"] <= 1)), "gain range")
    check(
        k["temperature"][0] == 42 and k["variance"][0] == 4, "no initial double update"
    )
    # A biased sensor can mislead a responsive filter even with a smooth output.
    steady = {
        "power": np.full(360, 0.3),
        "ambient": np.full(360, 20.0),
        "observed": np.full(361, 51.2),
    }
    responsive = model.filter_episode(steady, c, ua, q=0.01, initial_offset=0)
    check(responsive["temperature"][-1] > 51, "sensor bias is not removed by KF")
    with tempfile.TemporaryDirectory(prefix="wh1_verify_") as tmp:
        out = Path(tmp) / "run"
        s = model.run(out)
        data = json.loads((out / "experiment.json").read_text(encoding="utf-8"))
        check(
            abs(s["physical_fit"]["capacity"] - 418) < 2,
            "capacity recovered within tolerance",
        )
        check(
            abs(s["physical_fit"]["ua"] - 0.01) < 0.0001,
            "UA recovered within tolerance",
        )
        check(
            abs(s["beta_fitted"] - 0.00012) < 0.000005,
            "power residual coefficient recovered",
        )
        check(
            s["sensitivity"]["steady"]["rank"] == 1,
            "steady experiment cannot identify capacity",
        )
        check(s["sensitivity"]["pulse"]["rank"] == 2, "pulses separate parameters")
        check(len(data["episodes"]) == 10, "ten complete trajectories")
        check(
            sum(len(e["truth"]) for e in data["episodes"]) == 5410, "data row contract"
        )
        roles = {e["id"]: e["role"] for e in data["episodes"]}
        check(
            all(roles[x["episode"]] == "selection" for x in s["q_selection"]),
            "Q selected only on selection trajectories",
        )
        check(
            all(roles[x["episode"]] == "selection" for x in s["residual_selection"]),
            "residual comparison uses selection trajectories",
        )
        check(len(s["q_selection"]) == 12, "all Q candidates retained")
        check(
            set(s["metrics"]) == {k for k, v in roles.items() if v == "test"},
            "all independent tests reported",
        )
        m = s["metrics"]
        check(
            m["test_loss"]["gray"]["rmse_C"] < m["test_loss"]["physical"]["rmse_C"],
            "gray improvement in matching regime",
        )
        check(
            m["test_nominal"]["gray"]["rmse_C"]
            > m["test_nominal"]["physical"]["rmse_C"],
            "negative transfer retained",
        )
        check(
            m["test_hot"]["gray"]["rmse_C"] > m["test_loss"]["gray"]["rmse_C"],
            "high-temperature shift retained",
        )
        byid = {x["id"]: x for x in data["episodes"]}
        check(
            byid["test_loss"]["truth"] == byid["test_bias"]["truth"],
            "paired sensor-bias case identical plant",
        )
        check(
            byid["test_loss"]["noise"] == byid["test_bias"]["noise"],
            "paired sensor-bias case identical noise",
        )
        check(
            abs(
                byid["test_bias"]["observed"][-1]
                - byid["test_loss"]["observed"][-1]
                - 1.2
            )
            < 1e-10,
            "specified sensor bias",
        )
        try:
            model.run(out)
        except FileExistsError:
            check(True, "nonempty result directory protected")
        else:
            check(False, "overwriting forbidden")
        # Fit APIs work after reference-only fields are removed entirely.
        calibration = [
            {k: e[k] for k in ["power", "ambient", "observed"]}
            for e in data["episodes"]
            if e["role"] == "calibration"
        ]
        for e in calibration:
            for k in e:
                e[k] = np.asarray(e[k])
        fit = model.fit_physical(calibration)
        check(
            abs(fit["capacity"] - s["physical_fit"]["capacity"]) < 1e-8,
            "fitting requires no reference state",
        )
    print(f"PASS: {count} numerical and protocol checks")


if __name__ == "__main__":
    main()

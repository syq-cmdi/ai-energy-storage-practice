"""W-H1: identification, filtering and independent thermal validation.

All observations are constructed, not field data. Run from any directory:
    python chapters/ch04/run.py --out results/ch04
The reference uses DOP853; deployed models use exact linear or RK4 updates.
"""

from pathlib import Path
import argparse
import csv
import json
import platform
import hashlib
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares
from scipy.stats import t as student_t

ROOT = Path(__file__).resolve().parent
DT = 120.0
C_REF, UA_REF, SIGMA = 418.0, 0.010, 0.25
BETA_REF = 0.00012
SEED = 20261114


def linear_step(temp, power, ambient, capacity, ua, dt=DT):
    """Exact zero-order-hold solution. Units: degC, kW, kJ/K, kW/K, s."""
    if capacity <= 0 or ua < 0 or dt <= 0:
        raise ValueError("capacity>0, ua>=0, dt>0 are required")
    if ua == 0:
        return temp + power * dt / capacity
    b = -np.expm1(-ua * dt / capacity)
    return temp + b * (ambient + power / ua - temp)


def gray_step(temp, power, ambient, capacity, ua, beta, dt=DT):
    """One RK4 step with a learned quadratic heat-loss correction (kW)."""
    if beta == 0:
        return linear_step(temp, power, ambient, capacity, ua, dt)

    def rate(x):
        delta = x - ambient
        return (power - ua * delta - beta * delta * abs(delta)) / capacity

    k1 = rate(temp)
    k2 = rate(temp + dt * k1 / 2)
    k3 = rate(temp + dt * k2 / 2)
    k4 = rate(temp + dt * k3)
    return temp + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6


def simulate(power, ambient, initial, capacity, ua, beta=0):
    out = [float(initial)]
    for u, ta in zip(power, ambient):
        out.append(float(gray_step(out[-1], u, ta, capacity, ua, beta)))
    return np.array(out)


def reference(power, ambient, initial, beta=0, high_loss=False):
    """Independent adaptive solver with simultaneous heat-flow quadrature."""
    temps, energies = [float(initial)], []
    for u, ta in zip(power, ambient):

        def rhs(_, state):
            delta = state[0] - ta
            # An intentionally unmodelled high-temperature loss in the OOD case.
            extra = 0.0005 * max(state[0] - 65, 0) ** 2 if high_loss else 0
            net = u - UA_REF * delta - beta * delta * abs(delta) - extra
            return [net / C_REF, net]

        sol = solve_ivp(
            rhs, (0, DT), [temps[-1], 0], method="DOP853", rtol=1e-11, atol=1e-12
        )
        if not sol.success:
            raise RuntimeError(sol.message)
        temps.append(float(sol.y[0, -1]))
        energies.append(float(sol.y[1, -1]))
    return np.array(temps), np.array(energies)


def make_episode(
    name, role, hours, initial, seed, beta=0, bias=0, ambient0=20, high_loss=False
):
    rng = np.random.default_rng(seed)
    n = int(hours * 3600 / DT)
    blocks = rng.choice([0, 0.3, 0.8, 1.5], int(np.ceil(n / 15)))
    blocks[2::3] = 0
    power = np.repeat(blocks, 15)[:n]
    if name == "cal_cool":
        power[:120] = 1.5
        power[120:420] = 0
    if high_loss:
        power[:120] = 0.5
    ambient = ambient0 + 1.5 * np.sin(2 * np.pi * np.arange(n) * DT / 86400)
    truth, energy = reference(power, ambient, initial, beta, high_loss)
    noise = rng.normal(0, SIGMA, n + 1)
    sensor_bias = np.where(np.arange(n + 1) * DT >= 21600, bias, 0.0)
    observed = truth + noise + sensor_bias
    return {
        "id": name,
        "role": role,
        "hours": hours,
        "initial": initial,
        "seed": seed,
        "beta_reference": beta,
        "high_loss": high_loss,
        "t_s": np.arange(n + 1) * DT,
        "power": power,
        "ambient": ambient,
        "truth": truth,
        "energy_ref": energy,
        "noise": noise,
        "bias": sensor_bias,
        "observed": observed,
    }


def build_data():
    specs = [
        ("cal_pulse", "calibration", 24, 28, 11, 0, 0, 20, False),
        ("cal_cool", "calibration", 24, 38, 12, 0, 0, 20, False),
        ("residual_a", "residual_train", 18, 35, 21, BETA_REF, 0, 20, False),
        ("residual_b", "residual_train", 18, 48, 22, BETA_REF, 0, 22, False),
        ("select_base", "selection", 12, 32, 31, 0, 0, 21, False),
        ("select_gray", "selection", 18, 43, 32, BETA_REF, 0, 19, False),
        ("test_nominal", "test", 12, 30, 41, 0, 0, 20, False),
        ("test_loss", "test", 18, 40, 42, BETA_REF, 0, 21, False),
        ("test_bias", "test", 18, 40, 42, BETA_REF, 1.2, 21, False),
        ("test_hot", "test", 18, 78, 43, BETA_REF, 0, 26, True),
    ]
    return [make_episode(*s) for s in specs]


def fit_physical(episodes):
    """Joint trajectory fit: C, UA and one nuisance initial temperature per run.

    Fit observed temperatures only. Neither reference states nor heat integrals
    are accessed. The initial observation is included once in the objective.
    """

    def residual(z):
        return np.concatenate(
            [
                simulate(e["power"], e["ambient"], z[2 + i], z[0], z[1]) - e["observed"]
                for i, e in enumerate(episodes)
            ]
        )

    x0 = [380, 0.015] + [e["observed"][0] for e in episodes]
    fit = least_squares(
        residual,
        x0,
        bounds=([200, 0.002] + [0] * len(episodes), [800, 0.04] + [95] * len(episodes)),
        x_scale=[418, 0.01] + [1] * len(episodes),
        jac="3-point",
        ftol=1e-11,
        xtol=1e-11,
        gtol=1e-10,
    )
    if not fit.success:
        raise RuntimeError(fit.message)
    dof = len(fit.fun) - len(fit.x)
    s2 = float(fit.fun @ fit.fun / dof)
    cov = s2 * np.linalg.inv(fit.jac.T @ fit.jac)
    half = student_t.ppf(0.975, dof) * np.sqrt(np.diag(cov))
    scaled = fit.jac * np.array([418, 0.01] + [1] * len(episodes))
    return {
        "capacity": float(fit.x[0]),
        "ua": float(fit.x[1]),
        "initials": fit.x[2:].tolist(),
        "sigma_fit": s2**0.5,
        "ci95": np.column_stack((fit.x - half, fit.x + half)).tolist(),
        "covariance": cov.tolist(),
        "scaled_condition": float(np.linalg.cond(scaled)),
        "n_observations": len(fit.fun),
        "dof": dof,
        "success": bool(fit.success),
    }


def fit_residual(episodes, params):
    """Learn one power-residual coefficient; freeze the physical parameters."""

    def residual(z):
        return np.concatenate(
            [
                simulate(
                    e["power"],
                    e["ambient"],
                    z[i + 1],
                    params["capacity"],
                    params["ua"],
                    z[0] * 1e-4,
                )
                - e["observed"]
                for i, e in enumerate(episodes)
            ]
        )

    fit = least_squares(
        residual,
        [1] + [e["observed"][0] for e in episodes],
        bounds=([0] + [0] * len(episodes), [5] + [95] * len(episodes)),
        jac="3-point",
        ftol=1e-10,
        xtol=1e-10,
        gtol=1e-9,
    )
    if not fit.success:
        raise RuntimeError(fit.message)
    return float(fit.x[0] * 1e-4)


def filter_episode(e, capacity, ua, beta=0, q=0.0001, r=SIGMA**2, initial_offset=2):
    """Scalar KF (beta=0), extended KF otherwise. Initial sample is prior only.

    The initial prior mean is y[0]+offset, P0=4 K²; no double update at t=0.
    Joseph covariance update avoids loss of positivity. Q is per 120-s step.
    """
    if q < 0 or r <= 0:
        raise ValueError("q>=0 and r>0 required")
    estimate, variance = [float(e["observed"][0] + initial_offset)], [4.0]
    innovation, gain, nll = [0.0], [0.0], []
    for k, (u, ta) in enumerate(zip(e["power"], e["ambient"])):
        x = estimate[-1]
        pred = gray_step(x, u, ta, capacity, ua, beta)
        a = (
            gray_step(x + 1e-4, u, ta, capacity, ua, beta)
            - gray_step(x - 1e-4, u, ta, capacity, ua, beta)
        ) / 2e-4
        prior_var = a * a * variance[-1] + q
        s = prior_var + r
        g = prior_var / s
        v = e["observed"][k + 1] - pred
        estimate.append(float(pred + g * v))
        innovation.append(float(v))
        gain.append(float(g))
        variance.append(float((1 - g) ** 2 * prior_var + g * g * r))
        nll.append(float(0.5 * (np.log(2 * np.pi * s) + v * v / s)))
    return {
        "temperature": np.array(estimate),
        "variance": np.array(variance),
        "innovation": np.array(innovation),
        "gain": np.array(gain),
        "mean_nll": float(np.mean(nll)),
    }


def rmse(a, b):
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def evaluate(e, params, beta, q):
    c, ua = params["capacity"], params["ua"]
    # Common observed initial value for all open-loop alternatives.
    base = simulate(e["power"], e["ambient"], e["observed"][0], c, ua)
    gray = simulate(e["power"], e["ambient"], e["observed"][0], c, ua, beta)
    kf = filter_episode(e, c, ua, 0, q["physical"])
    ekf = filter_episode(e, c, ua, beta, q["gray"])
    methods = {
        "measurement": e["observed"],
        "physical": base,
        "gray": gray,
        "kf": kf["temperature"],
        "ekf": ekf["temperature"],
    }
    metrics = {}
    mask = np.arange(len(e["truth"])) * DT >= 1200  # predeclared 20-min burn-in
    for method, values in methods.items():
        err = values[mask] - e["truth"][mask]
        metrics[method] = {
            "rmse_C": rmse(values[mask], e["truth"][mask]),
            "mae_C": float(np.mean(abs(err))),
            "bias_C": float(np.mean(err)),
        }
        if method in ("physical", "gray"):
            er = C_REF * np.diff(values) - e["energy_ref"]
            metrics[method].update(
                energy_rmse_kJ=float(np.sqrt(np.mean(er**2))),
                cumulative_energy_kJ=float(np.sum(er)),
            )
    for method, result in [("kf", kf), ("ekf", ekf)]:
        err = result["temperature"] - e["truth"]
        metrics[method]["coverage95_percent"] = float(
            100 * np.mean(abs(err[mask]) <= 1.96 * np.sqrt(result["variance"][mask]))
        )
    return {"methods": methods, "kf": kf, "ekf": ekf, "metrics": metrics}


def serial(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serial(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def run(out):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(
            f"Output is not empty: {out}; choose a new --out directory"
        )
    out.mkdir(parents=True, exist_ok=True)
    episodes = build_data()
    physical = fit_physical([e for e in episodes if e["role"] == "calibration"])
    beta = fit_residual(
        [e for e in episodes if e["role"] == "residual_train"], physical
    )
    validation = [e for e in episodes if e["role"] == "selection"]
    selection_rows, chosen_q = [], {}
    q_grid = [0, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2]
    for label, b in [("physical", 0), ("gray", beta)]:
        # Separate operating regimes: do not pretend a residual is universally valid.
        selected = validation[0] if label == "physical" else validation[1]
        candidates = []
        for q in q_grid:
            score = filter_episode(
                selected, physical["capacity"], physical["ua"], b, q
            )["mean_nll"]
            row = {"model": label, "episode": selected["id"], "q": q, "mean_nll": score}
            selection_rows.append(row)
            candidates.append(row)
        chosen_q[label] = min(candidates, key=lambda x: x["mean_nll"])["q"]
    # Validation comparison against observable temperatures; reference states excluded.
    residual_selection = []
    for e in validation:
        for label, b in [("physical", 0), ("gray", beta)]:
            pred = simulate(
                e["power"],
                e["ambient"],
                e["observed"][0],
                physical["capacity"],
                physical["ua"],
                b,
            )
            residual_selection.append(
                {
                    "episode": e["id"],
                    "model": label,
                    "observed_rmse_C": rmse(pred[1:], e["observed"][1:]),
                }
            )
    results = {e["id"]: evaluate(e, physical, beta, chosen_q) for e in episodes}
    # Finite-difference sensitivity to relative parameter perturbations.
    sensitivities = {}
    e = episodes[0]
    for name, u, initial in [
        ("pulse", e["power"], 28),
        ("steady", np.full(720, 0.3), 50),
    ]:
        ambient = np.full(len(u), 20.0)
        cols = []
        for j, nominal in enumerate([C_REF, UA_REF]):
            plus = [C_REF, UA_REF]
            minus = plus.copy()
            plus[j] *= 1.001
            minus[j] *= 0.999
            cols.append(
                (
                    simulate(u, ambient, initial, *plus)
                    - simulate(u, ambient, initial, *minus)
                )
                / 0.002
            )
        matrix = np.column_stack(cols)
        sv = np.linalg.svd(matrix, compute_uv=False)
        sensitivities[name] = {
            "singular_values": sv.tolist(),
            "rank": int(np.linalg.matrix_rank(matrix)),
            "condition": float(sv[0] / sv[-1]) if sv[-1] > 1e-10 else None,
            "C_sensitivity": cols[0].tolist(),
            "UA_sensitivity": cols[1].tolist(),
        }
    summary = {
        "schema_version": 1,
        "provenance": "Author-constructed W-H1 simulation; no field observations.",
        "reference": {
            "capacity": C_REF,
            "ua": UA_REF,
            "dt_s": DT,
            "sigma_C": SIGMA,
            "beta": BETA_REF,
        },
        "physical_fit": physical,
        "beta_fitted": beta,
        "chosen_q": chosen_q,
        "q_selection": selection_rows,
        "residual_selection": residual_selection,
        "burn_in_s": 1200,
        "initial_prior_offset_C": 2,
        "initial_variance_K2": 4,
        "metrics": {
            e["id"]: results[e["id"]]["metrics"]
            for e in episodes
            if e["role"] == "test"
        },
        "sensitivity": sensitivities,
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
    }
    (out / "summary.json").write_text(
        json.dumps(serial(summary), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "experiment.json").write_text(
        json.dumps(
            serial({"summary": summary, "episodes": episodes, "results": results}),
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    with (out / "trajectories.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "episode",
                "role",
                "time_s",
                "T_ref_C",
                "y_C",
                "u_kW",
                "Ta_C",
                "energy_ref_kJ",
                "T_physical_C",
                "T_gray_C",
                "T_kf_C",
                "T_ekf_C",
            ]
        )
        for e in episodes:
            rr = results[e["id"]]["methods"]
            for k, t in enumerate(e["t_s"]):
                w.writerow(
                    [
                        e["id"],
                        e["role"],
                        t,
                        e["truth"][k],
                        e["observed"][k],
                        e["power"][k] if k < len(e["power"]) else "",
                        e["ambient"][k] if k < len(e["ambient"]) else "",
                        e["energy_ref"][k] if k < len(e["energy_ref"]) else "",
                        rr["physical"][k],
                        rr["gray"][k],
                        rr["kf"][k],
                        rr["ekf"][k],
                    ]
                )
    manifest = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.iterdir())
        if p.is_file()
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(out),
                "capacity": physical["capacity"],
                "ua": physical["ua"],
                "beta": beta,
                "q": chosen_q,
                "test_rmse": {
                    k: {m: round(z["rmse_C"], 5) for m, z in v.items()}
                    for k, v in summary["metrics"].items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT.parents[1] / "results/ch04")
    run(parser.parse_args().out)

"""Train on complete trajectories; freeze development choices, then evaluate."""

from pathlib import Path
import argparse, hashlib, json, platform, time, warnings
import numpy as np
from scipy.optimize import least_squares
from sklearn.neural_network import MLPRegressor
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits
from model import (
    ROOT,
    DT,
    C_REF,
    UA_REF,
    BETA_REF,
    HORIZON,
    COST,
    PHYSICAL_BOUNDS,
    INTERLOCK_T,
    reference_step,
    linear_step,
    predict,
    domain_ok,
    plan,
    execute_action,
)

REPO = ROOT.parents[1]
HORIZONS = [1, 5, 15, 30]


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
        newline="\n",
    )


def episode(
    name, split, initial, seed, ambient0=21.0, hours=6, max_power=1.5, beta=BETA_REF
):
    rng = np.random.default_rng(seed)
    n = int(hours * 3600 / DT)
    grid = np.linspace(0, max_power, 6)
    power = np.repeat(rng.choice(grid, int(np.ceil(n / 6))), 6)[:n]
    if split == "calibration":
        power = np.tile(np.r_[np.full(30, 1.5), np.zeros(30)], int(np.ceil(n / 60)))[:n]
    ambient = ambient0 + 0.6 * np.sin(2 * np.pi * np.arange(n) / n + seed * 0.3)
    temp, energy = [float(initial)], []
    for u, ta in zip(power, ambient):
        t, e = reference_step(temp[-1], u, ta, beta=beta, return_energy=True)
        temp.append(t)
        energy.append(e)
    return dict(
        id=name,
        split=split,
        scenario=name,
        seed=seed,
        hours=hours,
        t_s=(np.arange(n + 1) * DT).tolist(),
        power=power.tolist(),
        ambient=ambient.tolist(),
        temperature=temp,
        energy_net_kJ=energy,
        beta_reference=beta,
        measurement_noise_std=0.0,
        action_upper=max_power,
    )


def build_episodes():
    out = [
        episode("cal_heat", "calibration", 32, 1, hours=4, beta=0),
        episode("cal_cool", "calibration", 58, 2, hours=4, beta=0),
    ]
    for i, (t, ta) in enumerate(
        zip([30, 37, 44, 51, 58, 65, 34, 61], [18, 20, 22, 24, 19, 21, 23, 22])
    ):
        out.append(episode(f"train_{i+1:02d}", "train", t, 101 + i, ta))
    for i, (t, ta) in enumerate([(36, 20), (49, 22), (63, 23)]):
        out.append(episode(f"validation_{i+1:02d}", "validation", t, 201 + i, ta))
    out += [
        episode("test_nominal", "test", 46, 301, 21),
        episode("test_ambient", "test", 54, 302, 23.5),
        episode("test_actions", "test", 48, 303, 21, max_power=2.4),
        episode("test_hot", "test", 82, 304, 22),
    ]
    return out


def fit_physics(calibration):
    def errors(params):
        values = []
        for e in calibration:
            t = e["temperature"][0]
            for u, ta, y in zip(e["power"], e["ambient"], e["temperature"][1:]):
                t = linear_step(t, u, ta, *params)
                values.append(t - y)
        return np.array(values)

    fit = least_squares(
        errors,
        [380, 0.015],
        bounds=([200, 0.001], [800, 0.05]),
        x_scale=[418, 0.01],
        ftol=1e-12,
        xtol=1e-12,
        gtol=1e-12,
    )
    if not fit.success:
        raise RuntimeError(fit.message)
    return dict(
        capacity=float(fit.x[0]),
        ua=float(fit.x[1]),
        calibration_rmse=float(np.sqrt(np.mean(fit.fun**2))),
        source_trajectories=[e["id"] for e in calibration],
        success=bool(fit.success),
    )


def training_arrays(episodes):
    x = np.concatenate(
        [
            np.column_stack((e["temperature"][:-1], e["ambient"], e["power"]))
            for e in episodes
        ]
    )
    y = np.concatenate([np.array(e["temperature"][1:]) for e in episodes])
    return x, y


def fit_mlp(kind, width, episodes, physics):
    x, next_t = training_arrays(episodes)
    base = (
        x[:, 0]
        if kind == "direct"
        else linear_step(x[:, 0], x[:, 2], x[:, 1], physics["capacity"], physics["ua"])
    )
    y = next_t - base
    xmean = x.mean(0)
    xscale = x.std(0)
    yscale = float(y.std())
    ymean = float(y.mean())
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        net = MLPRegressor(
            hidden_layer_sizes=(width,),
            activation="tanh",
            solver="lbfgs",
            alpha=1e-4,
            max_iter=1000,
            max_fun=30000,
            tol=1e-8,
            random_state=410 + width,
        )
        net.fit((x - xmean) / xscale, (y - ymean) / yscale)
    return dict(
        kind=kind,
        capacity=physics["capacity"],
        ua=physics["ua"],
        x_mean=xmean.tolist(),
        x_scale=xscale.tolist(),
        y_mean=ymean,
        y_scale=yscale,
        coefs=[w.tolist() for w in net.coefs_],
        biases=[v.tolist() for v in net.intercepts_],
        width=width,
        alpha=1e-4,
        seed=410 + width,
        n_iter=int(net.n_iter_),
        loss=float(net.loss_),
        warnings=[str(w.message) for w in caught],
        training_ids=[e["id"] for e in episodes],
    )


def window_errors(model, e, horizon):
    if (
        not isinstance(horizon, int)
        or isinstance(horizon, bool)
        or not 1 <= horizon <= len(e["power"])
    ):
        raise ValueError("horizon must be an integer in [1, number of intervals]")
    t = np.array(e["temperature"])
    u = np.array(e["power"])
    ta = np.array(e["ambient"])
    starts = np.arange(len(u) - horizon + 1)
    state = t[starts].copy()
    for j in range(horizon):
        state = predict(model, state, u[starts + j], ta[starts + j])
    return state - t[starts + horizon]


def metric(model, e, horizon, band=None):
    err = window_errors(model, e, horizon)
    return dict(
        episode=e["id"],
        model=model["kind"],
        horizon_steps=horizon,
        n_windows=len(err),
        rmse=float(np.sqrt(np.mean(err**2))),
        mae=float(np.mean(abs(err))),
        bias=float(np.mean(err)),
        empirical_half_width_K=band,
        empirical_coverage=(
            float(np.mean(abs(err) <= band + 1e-12)) if band is not None else None
        ),
    )


def scenarios():
    n = 120
    k = np.arange(n)
    target = np.r_[np.full(40, 55.0), np.full(40, 60.0), np.full(41, 56.0)]
    ambient = 22 + 0.5 * np.sin(2 * np.pi * k / n)
    return [
        dict(
            id="nominal",
            initial=50.0,
            ambient=ambient.tolist(),
            target=target.tolist(),
            power_limit=1.5,
            action_grid=np.linspace(0, 1.5, 6).tolist(),
        ),
        dict(
            id="extended_power",
            initial=50.0,
            ambient=ambient.tolist(),
            target=np.r_[
                np.full(40, 62.0), np.full(40, 68.0), np.full(41, 60.0)
            ].tolist(),
            power_limit=2.4,
            action_grid=np.linspace(0, 2.4, 7).tolist(),
        ),
        dict(
            id="hot_start",
            initial=82.0,
            ambient=ambient.tolist(),
            target=np.full(n + 1, 62.0).tolist(),
            power_limit=2.4,
            action_grid=np.linspace(0, 2.4, 7).tolist(),
        ),
    ]


def closed_loop(scenario, policy, bundle):
    t = scenario["initial"]
    previous = 0.0
    rows = []
    ambient = scenario["ambient"]
    target = scenario["target"]
    grid = scenario["action_grid"]
    n = len(ambient)
    for k in range(n):
        ta = np.array([ambient[min(n - 1, k + j)] for j in range(HORIZON)])
        ref = np.array([target[min(n, k + j + 1)] for j in range(HORIZON)])
        if policy == "rule":
            requested = (
                max(grid) if t < ref[0] - 0.4 else 0.0 if t > ref[0] + 0.4 else previous
            )
            decision = dict(
                action=requested,
                selected_cost=None,
                candidates=[],
                fallback=False,
                fallback_kind=None,
                fallback_reason=None,
                candidate_rejections=0,
                domain_rejections=0,
                physical_rejections=0,
            )
        else:
            key = "residual" if policy == "guarded_residual" else policy
            decision = plan(
                bundle["models"][key],
                t,
                ta,
                ref,
                previous,
                grid,
                bundle["domain"] if policy == "guarded_residual" else None,
                bundle["physics"],
            )
        u, interlock = execute_action(t, decision["action"], scenario["power_limit"])
        nxt, energy = reference_step(t, u, ambient[k], return_energy=True)
        rows.append(
            dict(
                step=k,
                time_s=k * DT,
                T_before=float(t),
                T_after=float(nxt),
                target=target[k + 1],
                ambient=ambient[k],
                action=u,
                requested_action=decision["action"],
                status=(
                    "interlock"
                    if interlock
                    else (
                        "fallback"
                        if decision["fallback"]
                        else "rule" if policy == "rule" else "planned"
                    )
                ),
                selected_cost=decision["selected_cost"],
                candidates=decision["candidates"],
                fallback=decision["fallback"],
                fallback_kind=decision["fallback_kind"],
                fallback_reason=decision["fallback_reason"],
                fallback_action=decision["action"] if decision["fallback"] else None,
                candidate_rejections=decision["candidate_rejections"],
                domain_rejections=decision["domain_rejections"],
                physical_rejections=decision["physical_rejections"],
                fallback_executed=bool(decision["fallback"] and not interlock),
                requested_fallback_action=(
                    decision["action"] if decision["fallback"] else None
                ),
                executed_fallback_action=(
                    u if decision["fallback"] and not interlock else None
                ),
                interlock=interlock,
                energy_net_kJ=energy,
            )
        )
        t = nxt
        previous = u
    error = np.array([row["T_after"] - row["target"] for row in rows])
    actions = np.array([row["action"] for row in rows])
    temperature = np.array([row["T_after"] for row in rows])
    metrics = dict(
        rmse_K=float(np.sqrt(np.mean(error**2))),
        mae_K=float(np.mean(abs(error))),
        electricity_kWh=float(actions.sum() * DT / 3600),
        total_variation_kW=float(np.abs(np.diff(np.r_[0.0, actions])).sum()),
        max_temperature_C=float(max(scenario["initial"], temperature.max())),
        temperature_violations=int(
            (
                (temperature < PHYSICAL_BOUNDS[0]) | (temperature > PHYSICAL_BOUNDS[1])
            ).sum()
        ),
        fallback_count=sum(r["fallback"] for r in rows),
        fallback_requested_count=sum(r["fallback"] for r in rows),
        fallback_executed_count=sum(r["fallback_executed"] for r in rows),
        fallback_overridden_count=sum(r["fallback"] and r["interlock"] for r in rows),
        domain_rejections=sum(r["domain_rejections"] for r in rows),
        physical_rejections=sum(r["physical_rejections"] for r in rows),
        candidate_rejections=sum(r["candidate_rejections"] for r in rows),
        interlock_count=sum(r["interlock"] for r in rows),
        outside_action_count=int(
            (actions > bundle["domain"]["power"][1] + 1e-10).sum()
        ),
        outside_input_domain_count=sum(
            not domain_ok(bundle["domain"], r["T_before"], r["action"], r["ambient"])
            for r in rows
        ),
        state_temperature_outside_count=sum(
            not bundle["domain"]["temperature"][0]
            <= r["T_before"]
            <= bundle["domain"]["temperature"][1]
            for r in rows
        ),
    )
    return dict(scenario=scenario["id"], policy=policy, metrics=metrics, rows=rows)


def main(out):
    started = time.perf_counter()
    out.mkdir(exist_ok=True, parents=True)
    episodes = build_episodes()
    cal = [e for e in episodes if e["split"] == "calibration"]
    train = [e for e in episodes if e["split"] == "train"]
    validation = [e for e in episodes if e["split"] == "validation"]
    dump(ROOT / "data/trajectories.json", episodes)
    data_sha = hashlib.sha256(
        (ROOT / "data/trajectories.json").read_bytes()
    ).hexdigest()
    physics = fit_physics(cal)
    physical = dict(kind="physical", capacity=physics["capacity"], ua=physics["ua"])
    models = {"physical": physical}
    selection = []
    development_candidates = []
    for kind in ["direct", "residual"]:
        candidates = []
        for width in [8, 16]:
            m = fit_mlp(kind, width, train, physics)
            errors = np.concatenate([window_errors(m, e, 15) for e in validation])
            r = dict(
                model=kind,
                width=width,
                alpha=m["alpha"],
                seed=m["seed"],
                validation_h15_rmse=float(np.sqrt(np.mean(errors**2))),
                n_iter=m["n_iter"],
                loss=m["loss"],
                warnings=m["warnings"],
            )
            selection.append(r)
            development_candidates.append(dict(metrics=r, model=m))
            candidates.append((r["validation_h15_rmse"], width, m))
        models[kind] = min(candidates, key=lambda x: (x[0], x[1]))[2]
    x, _ = training_arrays(train)
    domain = dict(
        temperature=[float(x[:, 0].min()), float(x[:, 0].max())],
        ambient=[float(x[:, 1].min()), float(x[:, 1].max())],
        power=[float(x[:, 2].min()), float(x[:, 2].max())],
    )
    bands = {
        kind: {
            str(h): float(
                np.quantile(
                    np.abs(
                        np.concatenate([window_errors(model, e, h) for e in validation])
                    ),
                    0.95,
                    method="higher",
                )
            )
            for h in HORIZONS
        }
        for kind, model in models.items()
    }
    config = dict(
        dt_s=DT,
        C_reference_kJ_K=C_REF,
        UA_reference_kW_K=UA_REF,
        beta_reference_kW_K2=BETA_REF,
        training_state_observation="exact reference temperature; no sensor noise",
        forecast_information="known prescribed future ambient and setpoint, shared by all planners",
        selection_horizon_steps=15,
        evaluation_horizons=HORIZONS,
        controller_horizon_steps=HORIZON,
        cost_weights=COST,
        temperature_bounds_C=PHYSICAL_BOUNDS,
        interlock_temperature_C=INTERLOCK_T,
        domain_check="axis-aligned training ranges, every predicted input and next state",
        fallback="nearest common action to clipped physical feedback; zero power for invalid observation",
        calibration_hours=8,
        train_hours=48,
        validation_hours=18,
        test_hours=24,
        data_sha256=data_sha,
    )
    bundle = dict(
        physics=physics,
        models=models,
        domain=domain,
        empirical_bands=bands,
        development_candidates=development_candidates,
    )
    # Persist frozen selection before using any test outcome.
    dump(ROOT / "models.json", bundle)
    dump(
        out / "selected_config.json",
        dict(
            config=config,
            selection=selection,
            chosen_widths={k: v.get("width") for k, v in models.items()},
            empirical_bands=bands,
        ),
    )
    metrics = []
    rollouts = []
    for e in [x for x in episodes if x["split"] in ["validation", "test"]]:
        for kind, model in models.items():
            for h in HORIZONS:
                metrics.append(metric(model, e, h, bands[kind][str(h)]))
            t = e["temperature"][0]
            traj = [t]
            for u, ta in zip(e["power"], e["ambient"]):
                t = predict(model, t, u, ta)
                traj.append(t)
            rollouts.append(dict(episode=e["id"], model=kind, temperature=traj))
    scenario_list = scenarios()
    control = [
        closed_loop(s, p, bundle)
        for s in scenario_list
        for p in ["rule", "physical", "direct", "residual", "guarded_residual"]
    ]
    probes = []
    for name, t, ta in [
        ("in_domain", 50.0, 22.0),
        ("hot_state", 90.0, 22.0),
        ("unknown_ambient", 50.0, 32.0),
        ("invalid_observation", float("nan"), 22.0),
    ]:
        result = plan(
            models["residual"],
            t,
            np.full(HORIZON, ta),
            np.full(HORIZON, 60.0),
            0.0,
            np.linspace(0, 2.4, 7),
            domain,
            physics,
        )
        probes.append(
            dict(
                case=name,
                temperature=None if not np.isfinite(t) else t,
                ambient=ta,
                result=result,
            )
        )
    summary = dict(
        config=config,
        physics=physics,
        selection=selection,
        chosen_widths={k: v.get("width") for k, v in models.items()},
        domain=domain,
        empirical_bands=bands,
        prediction_metrics=metrics,
        control_metrics=[
            dict(scenario=c["scenario"], policy=c["policy"], **c["metrics"])
            for c in control
        ],
        elapsed_s=time.perf_counter() - started,
    )
    result = dict(
        config=config,
        bundle=bundle,
        selection=selection,
        episodes=episodes,
        prediction_metrics=metrics,
        open_loop=rollouts,
        control_scenarios=scenario_list,
        control=control,
        domain_probes=probes,
        summary=summary,
    )
    dump(out / "experiment.json", result)
    dump(out / "summary.json", summary)
    dump(REPO / "docs/ch10/reference_summary.json", summary)
    print(
        json.dumps(
            dict(
                seconds=summary["elapsed_s"],
                physics=physics,
                selection=selection,
                domain=domain,
                control=summary["control_metrics"],
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=REPO / "results/ch10")
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        main(args.out)

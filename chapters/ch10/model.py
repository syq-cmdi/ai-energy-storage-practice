"""Action-conditioned W-H1 dynamics and finite-candidate receding planning.

Reference integration is independent of the exported learned/deployed predictors.
Temperatures degC, power kW, capacitance kJ/K, time seconds; all data synthetic.
"""

from pathlib import Path
import json
import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parent
DT = 120.0
C_REF, UA_REF, BETA_REF = 418.0, 0.010, 0.00012
HORIZON = 12
COST = {"tracking": 1.0, "power": 0.08, "switching": 0.15}
PHYSICAL_BOUNDS = [15.0, 85.0]
INTERLOCK_T = 80.0


def linear_step(temp, power, ambient, capacity, ua, dt=DT):
    if capacity <= 0 or ua < 0 or dt <= 0:
        raise ValueError("capacity>0, ua>=0, dt>0 required")
    temp, power, ambient = np.broadcast_arrays(temp, power, ambient)
    result = (
        temp + power * dt / capacity
        if ua == 0
        else temp - np.expm1(-ua * dt / capacity) * (ambient + power / ua - temp)
    )
    return float(result) if result.ndim == 0 else result


def reference_step(
    temp, power, ambient, beta=BETA_REF, high_loss=False, return_energy=False
):
    """DOP853 integrates state and net heat independently; one ZOH interval."""

    def rhs(_, state):
        delta = state[0] - ambient
        extra = 0.0005 * max(state[0] - 65, 0) ** 2 if high_loss else 0.0
        net = power - UA_REF * delta - beta * delta * abs(delta) - extra
        return [net / C_REF, net]

    sol = solve_ivp(
        rhs, (0, DT), [float(temp), 0.0], method="DOP853", rtol=1e-10, atol=1e-11
    )
    if not sol.success:
        raise RuntimeError(sol.message)
    t, heat = map(float, sol.y[:, -1])
    return (t, heat) if return_energy else t


def predict(model, temp, power, ambient):
    """Exportable tanh network. Input order [T, Ta, u]; both learned targets in K."""
    t, u, ta = np.broadcast_arrays(temp, power, ambient)
    if model["kind"] == "physical":
        return linear_step(t, u, ta, model["capacity"], model["ua"])
    shape = t.shape
    z = np.column_stack((t.ravel(), ta.ravel(), u.ravel()))
    z = (z - np.array(model["x_mean"])) / np.array(model["x_scale"])
    for j, (weights, bias) in enumerate(zip(model["coefs"], model["biases"])):
        z = z @ np.array(weights) + np.array(bias)
        if j + 1 < len(model["coefs"]):
            z = np.tanh(z)
    delta = (z[:, 0] * model["y_scale"] + model["y_mean"]).reshape(shape)
    base = (
        t
        if model["kind"] == "direct"
        else linear_step(t, u, ta, model["capacity"], model["ua"])
    )
    result = base + delta
    return float(result) if result.ndim == 0 else result


def load_bundle(path=None):
    return json.loads(
        (Path(path) if path else ROOT / "models.json").read_text(encoding="utf-8")
    )


def domain_ok(domain, temp, power, ambient):
    """Checks axis-aligned variable ranges; joint support requires separate analysis."""
    return all(
        np.isfinite(v) and domain[key][0] - 1e-10 <= v <= domain[key][1] + 1e-10
        for key, v in [("temperature", temp), ("power", power), ("ambient", ambient)]
    )


def physical_feedback(temp, ambient, target, grid, physics):
    if not np.isfinite(temp) or not np.isfinite(ambient) or not np.isfinite(target):
        return 0.0, "zero_power"
    request = physics["capacity"] * (target - temp) / 1800.0 + physics["ua"] * (
        temp - ambient
    )
    request = np.clip(request, min(grid), max(grid))
    return float(min(grid, key=lambda x: (abs(x - request), x))), "physical_feedback"


def plan(
    model, temp, ambient, target, previous_action, grid, domain=None, physics=None
):
    """Evaluate constant-action candidates; all forecast exogenous values are supplied.

    target and ambient each have H elements, referring to T(k+j+1) and Ta(k+j).
    domain=None disables the learned-domain guard. Physical temperature checks stay on.
    """
    ambient, target = np.asarray(ambient, float), np.asarray(target, float)
    grid = np.asarray(grid, float)
    if len(ambient) != len(target) or not len(target):
        raise ValueError("nonempty equally sized ambient and target horizons required")
    if physics is None:
        physics = model
    if (
        not np.isfinite(temp)
        or not np.all(np.isfinite(ambient))
        or not np.all(np.isfinite(target))
    ):
        return {
            "action": 0.0,
            "selected_cost": None,
            "candidates": [],
            "fallback": True,
            "fallback_kind": "zero_power",
            "fallback_reason": "invalid_observation_or_forecast",
            "candidate_rejections": 0,
            "domain_rejections": 0,
            "physical_rejections": 0,
        }
    states = np.full(len(grid), temp, float)
    predictions = np.empty((len(grid), len(target)))
    domain_flags = np.ones(len(grid), bool)
    for j, ta in enumerate(ambient):
        if domain is not None:
            domain_flags &= np.array(
                [domain_ok(domain, t, u, ta) for t, u in zip(states, grid)]
            )
        states = np.asarray(predict(model, states, grid, ta))
        predictions[:, j] = states
        if domain is not None:
            domain_flags &= (states >= domain["temperature"][0] - 1e-10) & (
                states <= domain["temperature"][1] + 1e-10
            )
    physical_flags = np.all(
        np.isfinite(predictions)
        & (predictions >= PHYSICAL_BOUNDS[0])
        & (predictions <= PHYSICAL_BOUNDS[1]),
        axis=1,
    )
    feasible = physical_flags & domain_flags
    costs = (
        np.mean((predictions - target[None, :]) ** 2, axis=1)
        + COST["power"] * grid
        + COST["switching"] * (grid - previous_action) ** 2
    )
    candidates = [
        dict(
            action=float(u),
            physical_ok=bool(p),
            domain_ok=bool(d),
            feasible=bool(ok),
            cost=float(c) if np.isfinite(c) else None,
            prediction=[float(x) if np.isfinite(x) else None for x in pred],
        )
        for u, p, d, ok, c, pred in zip(
            grid, physical_flags, domain_flags, feasible, costs, predictions
        )
    ]
    valid = np.flatnonzero(feasible & np.isfinite(costs))
    if len(valid):
        i = min(valid, key=lambda j: (costs[j], grid[j]))
        return dict(
            action=float(grid[i]),
            selected_cost=float(costs[i]),
            candidates=candidates,
            fallback=False,
            fallback_kind=None,
            fallback_reason=None,
            candidate_rejections=int((~feasible).sum()),
            domain_rejections=int((~domain_flags).sum()),
            physical_rejections=int((~physical_flags).sum()),
        )
    action, kind = physical_feedback(temp, ambient[0], target[0], grid, physics)
    reason = (
        "nonfinite_prediction"
        if not np.any(np.all(np.isfinite(predictions), axis=1))
        else (
            "outside_training_box"
            if domain is not None and not np.any(domain_flags)
            else "no_feasible_prediction"
        )
    )
    return dict(
        action=action,
        selected_cost=None,
        candidates=candidates,
        fallback=True,
        fallback_kind=kind,
        fallback_reason=reason,
        candidate_rejections=int((~feasible).sum()),
        domain_rejections=int((~domain_flags).sum()),
        physical_rejections=int((~physical_flags).sum()),
    )


def execute_action(temp, requested, power_limit):
    """Common observed-temperature interlock and actuator bounds, for every controller."""
    if not np.isfinite(temp) or not np.isfinite(requested):
        return 0.0, True
    clipped = float(np.clip(requested, 0.0, power_limit))
    interlock = temp >= INTERLOCK_T
    return (0.0 if interlock else clipped), bool(interlock)

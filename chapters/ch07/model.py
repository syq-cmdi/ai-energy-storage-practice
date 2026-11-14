"""Causal hybrid storage environment; bus-side kW, internal kWh, seconds.
All controllers use the same physical projection and current observations.
"""

from dataclasses import dataclass, asdict
import numpy as np


@dataclass(frozen=True)
class Config:
    dt: float = 1.0
    battery_kwh: float = 40.0
    battery_min: float = 8.0
    battery_max: float = 32.0
    battery_initial: float = 20.0
    battery_kw: float = 80.0
    battery_eta: float = 0.96
    ramp_kw_s: float = 10.0
    capacitance_f: float = 450.0
    voltage_min: float = 80.0
    voltage_max: float = 160.0
    sc_kw: float = 100.0
    sc_eta: float = 0.98
    sc_fraction: float = 0.5
    tau_s: float = 15.0
    restore_kw: float = 50.0
    w_b: float = 0.25
    w_ramp: float = 0.10
    w_sc: float = 8.0
    w_residual: float = 100.0

    @property
    def sc_min(self):
        return self.capacitance_f * self.voltage_min**2 / 7.2e6

    @property
    def sc_max(self):
        return self.capacitance_f * self.voltage_max**2 / 7.2e6

    @property
    def sc_span(self):
        return self.sc_max - self.sc_min

    @property
    def sc_target(self):
        return (self.sc_min + self.sc_max) / 2

    @property
    def sc_initial(self):
        return self.sc_min + self.sc_span * self.sc_fraction


def demand(seed, n=600, dt=1.0, scenario="nominal"):
    """Synthetic causal experiment input; independent seeds per split."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) * dt
    phase = rng.uniform(0, 2 * np.pi, 3)
    slow = 18 + 22 * np.sin(2 * np.pi * t / 180 + phase[0])
    fast = 26 * np.sin(2 * np.pi * t / 7 + phase[1]) + 13 * np.sin(
        2 * np.pi * t / 3 + phase[2]
    )
    pulse = np.zeros(n)
    for start in np.arange(45, n * dt, 100):
        pulse[(t >= start) & (t < start + 8)] = rng.choice([-1, 1]) * rng.uniform(
            30, 55
        )
    p = slow + fast + pulse + rng.normal(0, 2, n)
    if scenario == "overload":
        p[(t >= 210) & (t < 245)] += 145
    return p


def scenario_config(name):
    if name == "low_energy":
        return Config(sc_fraction=0.03)
    if name == "derated":
        return Config(capacitance_f=225, sc_kw=60)
    if name in ("nominal", "overload"):
        return Config()
    raise ValueError(name)


def delta_energy(p, eta, dt):
    return -p * dt / (3600 * eta) if p >= 0 else -p * eta * dt / 3600


def power_bounds(e, lo, hi, limit, eta, dt):
    return max(-limit, -(hi - e) * 3600 / (eta * dt)), min(
        limit, (e - lo) * 3600 * eta / dt
    )


def feasible(eb, es, prev, d, c):
    bl, bh = power_bounds(
        eb, c.battery_min, c.battery_max, c.battery_kw, c.battery_eta, c.dt
    )
    sl, sh = power_bounds(es, c.sc_min, c.sc_max, c.sc_kw, c.sc_eta, c.dt)
    lo = max(bl, prev - c.ramp_kw_s * c.dt)
    hi = min(bh, prev + c.ramp_kw_s * c.dt)
    conflict = lo > hi + 1e-10
    if conflict:
        lo, hi = bl, bh  # physical energy bound has priority; log ramp conflict
    jl = max(lo, d - sh)
    jh = min(hi, d - sl)
    return lo, hi, sl, sh, jl, jh, conflict


def project(request, eb, es, prev, d, c):
    lo, hi, sl, sh, jl, jh, conflict = feasible(eb, es, prev, d, c)
    if jl <= jh:
        pb = float(np.clip(request, jl, jh))
    else:
        pb = hi if d > hi + sh else lo
    ps = float(np.clip(d - pb, sl, sh))
    residual = d - pb - ps
    return pb, ps, residual, conflict


def stage_cost(pb, ps, res, prev, es_next, c):
    return (
        c.w_b * (pb / c.battery_kw) ** 2
        + c.w_ramp * ((pb - prev) / (c.ramp_kw_s * c.dt)) ** 2
        + c.w_sc * ((es_next - c.sc_target) / c.sc_span) ** 2
        + c.w_residual * (res / 100) ** 2
    )


def optimize(eb, es, prev, d, c):
    """Exact piecewise quadratic one-step controller, no future demand."""
    lo, hi, sl, sh, jl, jh, _ = feasible(eb, es, prev, d, c)
    if jl > jh:
        return hi if d > hi + sh else lo
    cand = [jl, jh]
    for left, right, eta_factor in [
        (jl, min(jh, d), 1 / c.sc_eta),
        (max(jl, d), jh, c.sc_eta),
    ]:
        if left > right:
            continue
        h = c.dt / 3600 * eta_factor
        a = (
            c.w_b / c.battery_kw**2
            + c.w_ramp / (c.ramp_kw_s * c.dt) ** 2
            + c.w_sc * h * h / c.sc_span**2
        )
        b = (
            -c.w_ramp * prev / (c.ramp_kw_s * c.dt) ** 2
            + c.w_sc * h * (es - c.sc_target - h * d) / c.sc_span**2
        )
        cand.append(float(np.clip(-b / a, left, right)))
    return min(
        cand,
        key=lambda pb: stage_cost(
            pb, d - pb, 0, prev, es + delta_energy(d - pb, c.sc_eta, c.dt), c
        ),
    )


ACTIONS = np.array([-20.0, -10.0, -5.0, 0.0, 5.0, 10.0, 20.0])
BINS = [
    np.array([-80, -40, -15, 0, 15, 40, 80, 120]),
    np.linspace(0, 1, 10)[1:-1],
    np.array([-60, -40, -20, -5, 5, 20, 40, 60]),
]
SHAPE = (9, 9, 9)


def state_index(obs, c):
    d, eb, es, prev = obs
    return tuple(
        int(np.searchsorted(b, v, side="right"))
        for b, v in zip(BINS, [d, (es - c.sc_min) / c.sc_span, prev])
    )


class HybridEnv:
    """Minimal reset/step interface. Data end is an external truncation."""

    def __init__(self, c=Config()):
        self.c = c

    def reset(self, seed=30000, n=600, scenario="nominal", profile=None):
        self.p = (
            demand(seed, n, self.c.dt, scenario)
            if profile is None
            else np.asarray(profile, dtype=float)
        )
        if not len(self.p) or not np.all(np.isfinite(self.p)):
            raise ValueError("finite nonempty demand required")
        c = self.c
        self.eb = c.battery_initial
        self.es = c.sc_initial
        self.prev = 0.0
        self.k = 0
        self.done = False
        return self.obs(), {"seed": seed, "source": "synthetic"}

    def obs(self):
        return np.array(
            [self.p[min(self.k, len(self.p) - 1)], self.eb, self.es, self.prev]
        )

    def step(self, request):
        if self.done:
            raise RuntimeError("reset required after truncation")
        if not np.isfinite(request):
            raise ValueError("finite request required")
        c = self.c
        d = float(self.p[self.k])
        eb, es, prev = self.eb, self.es, self.prev
        pb, ps, res, conflict = project(request, eb, es, prev, d, c)
        self.eb += delta_energy(pb, c.battery_eta, c.dt)
        self.es += delta_energy(ps, c.sc_eta, c.dt)
        cost = stage_cost(pb, ps, res, prev, self.es, c)
        row = dict(
            k=self.k,
            time_s=self.k * c.dt,
            demand_kw=d,
            request_kw=float(request),
            battery_kw=pb,
            sc_kw=ps,
            residual_kw=res,
            battery_before_kwh=eb,
            battery_kwh=self.eb,
            sc_before_kwh=es,
            sc_kwh=self.es,
            sc_voltage_v=(self.es * 7.2e6 / c.capacitance_f) ** 0.5,
            ramp_kw_s=(pb - prev) / c.dt,
            projection_kw=pb - request,
            ramp_conflict=int(conflict),
            cost=cost,
        )
        self.prev = pb
        self.k += 1
        self.done = self.k == len(self.p)
        return self.obs(), -cost, False, self.done, row


def simulate(
    method, seed=30000, n=600, scenario="nominal", q=None, c=None, profile=None
):
    c = c or scenario_config(scenario)
    env = HybridEnv(c)
    obs, _ = env.reset(seed, n, scenario, profile)
    lp = 0.0
    rows = []
    while True:
        d, eb, es, prev = obs
        if method == "lowpass":
            alpha = 1 - np.exp(-c.dt / c.tau_s)
            lp += (d - lp) * alpha
            request = lp + c.restore_kw * (c.sc_target - es) / c.sc_span
        elif method == "optimizer":
            request = optimize(eb, es, prev, d, c)
        elif method == "qlearning":
            request = prev + ACTIONS[int(np.argmax(q[state_index(obs, c)]))]
        else:
            raise ValueError(method)
        obs, reward, term, trunc, row = env.step(request)
        rows.append(row)
        if term or trunc:
            break
    return rows


def metrics(rows, c):
    a = lambda k: np.array([r[k] for r in rows])
    pb = a("battery_kw")
    ps = a("sc_kw")
    r = a("residual_kw")
    violation = (
        (a("battery_kwh") < c.battery_min - 1e-8)
        | (a("battery_kwh") > c.battery_max + 1e-8)
        | (a("sc_kwh") < c.sc_min - 1e-8)
        | (a("sc_kwh") > c.sc_max + 1e-8)
        | (np.abs(pb) > c.battery_kw + 1e-8)
        | (np.abs(ps) > c.sc_kw + 1e-8)
        | (np.abs(a("ramp_kw_s")) > c.ramp_kw_s + 1e-8)
    )
    return dict(
        rmse_kw=float(np.sqrt(np.mean(r * r))),
        residual_kwh=float(np.sum(np.abs(r)) * c.dt / 3600),
        battery_throughput_kwh=float(np.sum(np.abs(pb)) * c.dt / 3600),
        battery_rms_kw=float(np.sqrt(np.mean(pb * pb))),
        ramp_rms_kw_s=float(np.sqrt(np.mean(a("ramp_kw_s") ** 2))),
        sc_endpoint_kwh=float(a("sc_kwh")[-1] - c.sc_initial),
        battery_endpoint_kwh=float(a("battery_kwh")[-1] - c.battery_initial),
        projection_steps=int(np.sum(np.abs(a("projection_kw")) > 1e-8)),
        violation_steps=int(violation.sum()),
        ramp_conflicts=int(a("ramp_conflict").sum()),
        mean_cost=float(a("cost").mean()),
    )

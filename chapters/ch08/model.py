"""Teaching hydrogen mass/electricity model. All profiles are synthetic."""

from dataclasses import dataclass, asdict
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix


@dataclass(frozen=True)
class Config:
    dt: float = 0.25
    pmax: float = 500.0
    pmin: float = 100.0
    sec: float = 55.0
    compressor: float = 3.0
    auxiliary: float = 5.0
    mmin: float = 20.0
    mmax: float = 80.0
    m0: float = 50.0
    loss: float = 0.0
    start_cost: float = 2.0
    shortage_penalty: float = 1000.0
    terminal_penalty: float = 100.0
    lhv: float = 33.33
    hhv: float = 39.4
    volume: float = 5.0
    temperature: float = 298.15
    gas_constant: float = 4124.0


def config(capacity=80):
    return Config(
        mmax=float(capacity), m0=(20 + capacity) / 2, volume=5 * capacity / 80
    )


def pressure(m, c, temperature=None, z=1.0):
    return (
        np.asarray(m)
        * c.gas_constant
        * (c.temperature if temperature is None else temperature)
        * z
        / c.volume
        / 1e5
    )


def profiles(scenario="nominal"):
    t = np.arange(192) / 4
    hod = t % 24
    renewable = (
        410 * np.maximum(np.sin(np.pi * (hod - 6) / 12), 0)
        + 65
        + 25 * np.sin(2 * np.pi * t / 8)
    )
    demand = 5.2 + 1.5 * ((hod >= 8) & (hod < 18)) + 0.45 * np.sin(2 * np.pi * t / 6)
    tariff = np.where((hod >= 17) & (hod < 22), 1.05, np.where(hod < 7, 0.35, 0.65))
    grid_cap = np.full(192, 650.0)
    if scenario == "cloud":
        renewable *= np.where((t >= 29) & (t < 42), 0.35, 1.0)
    elif scenario == "surge":
        demand *= np.where((t >= 28) & (t < 44), 1.35, 1.0)
    elif scenario == "supply_cap":
        grid_cap[(t >= 28) & (t < 38)] = 65.0
        renewable *= np.where((t >= 28) & (t < 38), 0.18, 1.0)
        demand *= np.where((t >= 28) & (t < 38), 1.20, 1.0)
    elif scenario != "nominal":
        raise ValueError(scenario)
    return dict(
        time=t, renewable=renewable, demand=demand, tariff=tariff, grid_cap=grid_cap
    )


def step(request, m, previous_on, r, d, gcap, c):
    """15-min mean-flow replay; projects command and records explicit shortage."""
    p = float(np.clip(request, 0, c.pmax))
    p = min(p, max(0, (r + gcap - c.auxiliary) / (1 + c.compressor / c.sec)))
    p = min(p, max(0, ((c.mmax - (1 - c.loss * c.dt) * m) / c.dt + d) * c.sec))
    if p < c.pmin - 1e-6:
        p = 0.0
    on = int(p > 1e-8)
    q = p / c.sec
    served = max(0, min(d, ((1 - c.loss * c.dt) * m - c.mmin) / c.dt + q))
    shortage = d - served
    after = (1 - c.loss * c.dt) * m + (q - served) * c.dt
    comp = c.compressor * q
    aux = c.auxiliary * on
    total = p + comp + aux
    grid = max(0, total - r)
    used = min(r, total)
    curtailed = r - used
    return dict(
        request=float(request),
        p=p,
        on=on,
        start=int(on > previous_on),
        q=q,
        served=served,
        shortage=shortage,
        m_before=m,
        m_after=after,
        compressor=comp,
        auxiliary=aux,
        total=total,
        grid=grid,
        renewable_used=used,
        curtailment=curtailed,
        loss=c.loss * m * c.dt,
        projected=bool(abs(p - request) > 1e-5),
    )


def plan(f, c, m_initial=None, on_initial=0, terminal="hard", target=None):
    """Mixed integer linear plan; binary on/off and start count, explicit slack."""
    n = len(f["demand"])
    m_initial = c.m0 if m_initial is None else m_initial
    target = c.m0 if target is None else target
    # Seven n-vectors: power, on, start, grid, curtailment, shortage, next mass.
    nv = 7 * n + (2 if terminal == "soft" else 0)
    lower = np.zeros(nv)
    upper = np.full(nv, np.inf)
    cost = np.zeros(nv)
    integer = np.zeros(nv)

    def ix(block, k):
        return block * n + k

    upper[:n] = c.pmax
    upper[n : 3 * n] = 1
    integer[n : 2 * n] = 1
    upper[3 * n : 4 * n] = f["grid_cap"]
    upper[4 * n : 5 * n] = f["renewable"]
    upper[5 * n : 6 * n] = f["demand"]
    lower[6 * n : 7 * n] = c.mmin
    upper[6 * n : 7 * n] = c.mmax
    cost[2 * n : 3 * n] = c.start_cost
    cost[3 * n : 4 * n] = np.asarray(f["tariff"]) * c.dt
    cost[5 * n : 6 * n] = c.shortage_penalty * c.dt
    if terminal == "soft":
        cost[-2:] = c.terminal_penalty
    ri = []
    ci = []
    va = []
    lo = []
    hi = []

    def row(items, l=-np.inf, h=np.inf):
        j = len(lo)
        for i, v in items:
            ri.append(j)
            ci.append(i)
            va.append(v)
        lo.append(l)
        hi.append(h)

    for k in range(n):
        p, u, z, g, cur, s, m = [ix(b, k) for b in range(7)]
        row([(p, 1), (u, -c.pmax)], h=0)
        row([(p, -1), (u, c.pmin)], h=0)
        row(
            [(z, 1), (u, -1)] + ([(ix(1, k - 1), 1)] if k else []),
            l=0 if k else -on_initial,
        )
        row(
            [(p, 1 + c.compressor / c.sec), (u, c.auxiliary), (g, -1), (cur, 1)],
            f["renewable"][k],
            f["renewable"][k],
        )
        balance = [(m, 1), (p, -c.dt / c.sec), (s, -c.dt)]
        rhs = -c.dt * f["demand"][k]
        if k:
            balance.append((ix(6, k - 1), -(1 - c.loss * c.dt)))
        else:
            rhs += (1 - c.loss * c.dt) * m_initial
        row(balance, rhs, rhs)
    if terminal == "hard":
        row([(7 * n - 1, 1)], target, target)
    elif terminal == "soft":
        row([(7 * n - 1, 1), (7 * n, -1), (7 * n + 1, 1)], target, target)
    elif terminal != "free":
        raise ValueError(terminal)
    a = coo_matrix((va, (ri, ci)), shape=(len(lo), nv)).tocsc()
    result = milp(
        cost,
        integrality=integer,
        bounds=Bounds(lower, upper),
        constraints=LinearConstraint(a, lo, hi),
        options={"mip_rel_gap": 1e-7, "time_limit": 15.0},
    )
    meta = dict(
        status=int(result.status),
        message=result.message,
        gap=(
            float(result.mip_gap)
            if getattr(result, "mip_gap", None) is not None
            else None
        ),
        objective=float(result.fun) if result.fun is not None else None,
    )
    if result.x is None:
        raise RuntimeError(f"No feasible MILP plan: {meta}")
    if result.status != 0:
        raise RuntimeError(f"Plan did not reach requested optimum: {meta}")
    return result.x[:n], meta


def forecast(nominal, actual, k, horizon=24):
    """Only index k and the nominal calendar are read; later observations hidden."""
    end = min(k + horizon, len(nominal["demand"]))
    f = {key: np.array(v[k:end], copy=True) for key, v in nominal.items()}
    age = np.arange(end - k) / 4
    for key in ["renewable", "demand"]:
        bias = actual[key][k] - nominal[key][k]
        f[key] = np.maximum(0, f[key] + bias * np.exp(-age / 3))
    f["grid_cap"][:] = actual["grid_cap"][k]
    return f


def simulate(policy, actual, c, nominal=None, commands=None):
    nominal = profiles() if nominal is None else nominal
    m = c.m0
    on = 0
    rows = []
    solves = []
    for k in range(len(actual["demand"])):
        if policy == "on_demand":
            req = (actual["demand"][k] + c.loss * m + (c.m0 - m) / 2) * c.sec
        elif policy == "day_ahead":
            req = commands[k]
        elif policy == "rolling":
            if k % 4 == 0:
                schedule, meta = plan(forecast(nominal, actual, k), c, m, on, "soft")
                meta["step"] = k
                solves.append(meta)
            req = schedule[k % 4]
        else:
            raise ValueError(policy)
        r = step(
            req,
            m,
            on,
            actual["renewable"][k],
            actual["demand"][k],
            actual["grid_cap"][k],
            c,
        )
        r.update({name: float(v[k]) for name, v in actual.items()})
        rows.append(r)
        m = r["m_after"]
        on = r["on"]
    return rows, solves


def summary(rows, c):
    def total(key):
        return sum(x[key] for x in rows) * c.dt

    mass_error = max(
        abs(x["m_after"] - x["m_before"] - (x["q"] - x["served"]) * c.dt + x["loss"])
        for x in rows
    )
    power_error = max(abs(x["grid"] + x["renewable_used"] - x["total"]) for x in rows)
    return dict(
        electricity_cost=sum(x["grid"] * x["tariff"] * c.dt for x in rows),
        start_cost=sum(x["start"] for x in rows) * c.start_cost,
        starts=sum(x["start"] for x in rows),
        grid_kwh=total("grid"),
        renewable_kwh=total("renewable_used"),
        curtailed_kwh=total("curtailment"),
        electrolysis_kwh=total("p"),
        compression_kwh=total("compressor"),
        auxiliary_kwh=total("auxiliary"),
        produced_kg=total("q"),
        served_kg=total("served"),
        shortage_kg=total("shortage"),
        end_kg=rows[-1]["m_after"],
        inventory_change_kg=rows[-1]["m_after"] - c.m0,
        minimum_kg=min(x["m_after"] for x in rows),
        projected_steps=sum(x["projected"] for x in rows),
        mass_error_kg=mass_error,
        power_error_kw=power_error,
        lhv_efficiency=total("q") * c.lhv / total("total") if total("total") else 0.0,
    )

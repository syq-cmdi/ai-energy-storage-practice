"""Train from scratch, select on validation seeds, then freeze and evaluate."""

from pathlib import Path
import argparse, json, csv, hashlib
import numpy as np
from model import *

ROOT = Path(__file__).resolve().parents[2]
TRAIN_SEEDS = [11, 22, 33, 44, 55]
VAL_SEEDS = list(range(20000, 20005))
TEST_SEEDS = list(range(30000, 30015))
SCENARIOS = ["nominal", "low_energy", "derated", "overload"]


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def train(seed, episodes=250):
    rng = np.random.default_rng(seed)
    q = np.zeros(SHAPE + (len(ACTIONS),))
    visits = np.zeros_like(q, dtype=int)
    c = Config()
    curve = []
    best = None
    bestval = float("inf")
    env = HybridEnv(c)
    for ep in range(episodes):
        obs, _ = env.reset(100000 + seed * 1000 + ep, n=300)
        eps = max(0.08, 1 - ep / (episodes * 0.8))
        cost = 0.0
        for k in range(300):
            state = state_index(obs, c)
            ai = (
                int(rng.integers(len(ACTIONS)))
                if rng.random() < eps
                else int(np.argmax(q[state]))
            )
            request = obs[3] + ACTIONS[ai]
            nxt, reward, terminated, truncated, row = env.step(request)
            ns = state_index(nxt, c)
            # Last observation repeats the current input at truncation: exclude this
            # final transition from Q updates to avoid fabricating a next demand.
            if not truncated:
                target = reward + 0.97 * np.max(q[ns])
                q[state + (ai,)] += 0.15 * (target - q[state + (ai,)])
                visits[state + (ai,)] += 1
            obs = nxt
            cost -= reward
        if (ep + 1) % 25 == 0:
            val = float(
                np.mean(
                    [
                        metrics(simulate("qlearning", s, n=300, q=q), c)["mean_cost"]
                        for s in VAL_SEEDS
                    ]
                )
            )
            curve.append(
                dict(
                    training_seed=seed,
                    episode=ep + 1,
                    epsilon=eps,
                    training_cost=cost / 300,
                    validation_cost=val,
                )
            )
            if val < bestval:
                bestval = val
                best = q.copy()
                chosen = ep + 1
    return (
        best,
        curve,
        dict(
            training_seed=seed,
            selected_episode=chosen,
            validation_cost=bestval,
            visited_state_actions=int((visits > 0).sum()),
            total_state_actions=int(visits.size),
        ),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "results/ch07")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    qs = {}
    curve = []
    selection = []
    for seed in TRAIN_SEEDS:
        q, h, m = train(seed)
        qs[seed] = q
        curve += h
        selection.append(m)
        np.savez_compressed(out / f"q_seed_{seed}.npz", q=q)
        print("trained", m, flush=True)
    selected = min(selection, key=lambda x: x["validation_cost"])["training_seed"]
    summ = []
    traces = {}
    audit = []
    for scenario in SCENARIOS:
        c = scenario_config(scenario)
        for seed in TEST_SEEDS:
            for method, train_seed in [("lowpass", 0), ("optimizer", 0)] + [
                ("qlearning", s) for s in TRAIN_SEEDS
            ]:
                rows = simulate(method, seed, scenario=scenario, q=qs.get(train_seed))
                m = metrics(rows, c)
                summ.append(
                    dict(
                        scenario=scenario,
                        test_seed=seed,
                        method=method,
                        training_seed=train_seed,
                        **m,
                    )
                )
                # Keep step logs for every evaluation, including residuals and projections.
                for r in rows:
                    if (
                        abs(r["residual_kw"]) > 1e-7
                        or abs(r["projection_kw"]) > 1e-7
                        or r["ramp_conflict"]
                    ):
                        audit.append(
                            dict(
                                scenario=scenario,
                                test_seed=seed,
                                method=method,
                                training_seed=train_seed,
                                **r,
                            )
                        )
                if seed == 30000 and (method != "qlearning" or train_seed == selected):
                    traces[f"{scenario}/{method}"] = rows
    write_csv(out / "evaluation.csv", summ)
    write_csv(out / "training.csv", curve)
    write_csv(out / "constraint_events.csv", audit)
    write_csv(out / "selected_trace.csv", traces["nominal/qlearning"])
    experiment = dict(
        config=asdict(Config()),
        source="synthetic, no field measurements",
        selected_seed=selected,
        selection=selection,
        train_seeds=TRAIN_SEEDS,
        validation_seeds=VAL_SEEDS,
        test_seeds=TEST_SEEDS,
        scenarios=SCENARIOS,
        metrics=summ,
        traces=traces,
        training=curve,
        selected_q=qs[selected].round(10).tolist(),
    )
    (out / "experiment.json").write_text(
        json.dumps(experiment, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (out / "manifest.json").write_text(
        json.dumps(
            dict(
                selected_seed=selected,
                config=asdict(Config()),
                evaluations=len(summ),
                training_episodes=250,
                training_horizon=300,
                evaluation_horizon=600,
                selection=selection,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    print("completed", out, "evaluations", len(summ), flush=True)


if __name__ == "__main__":
    main()

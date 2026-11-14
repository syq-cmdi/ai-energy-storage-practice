"""Run the complete 36-case experiment plus three boundary ablations."""

import argparse, csv, json, time
from pathlib import Path
from dataclasses import asdict, replace
import numpy as np
from model import config, profiles, plan, simulate, summary

ROOT = Path(__file__).resolve().parents[2]


def main(out):
    out.mkdir(parents=True, exist_ok=True)
    cases = []
    start = time.time()
    nominal = profiles()
    for cap in [40, 80, 120]:
        c = config(cap)
        commands, meta = plan(nominal, c)
        for scenario in ["nominal", "cloud", "surge", "supply_cap"]:
            for policy in ["on_demand", "day_ahead", "rolling"]:
                rows, solves = simulate(
                    policy, profiles(scenario), c, commands=commands
                )
                cases.append(
                    dict(
                        id=f"{scenario}_{cap}_{policy}",
                        scenario=scenario,
                        capacity=cap,
                        policy=policy,
                        config=asdict(c),
                        summary=summary(rows, c),
                        rows=rows,
                        solvers=([meta] if policy == "day_ahead" else solves),
                    )
                )
            (out / "checkpoint.json").write_text(
                json.dumps(cases, ensure_ascii=False, default=lambda x: x.item()),
                encoding="utf-8",
            )
            print(f"Completed {scenario} capacity={cap}", flush=True)
    ablations = []
    c = config()
    for name in ["omit_auxiliaries", "free_terminal", "hourly_plan"]:
        planning = (
            replace(c, compressor=0, auxiliary=0) if name == "omit_auxiliaries" else c
        )
        f = nominal
        if name == "hourly_plan":
            planning = replace(c, dt=1.0)
            f = {
                key: np.asarray(v).reshape(-1, 4).mean(axis=1)
                for key, v in nominal.items()
            }
        cmd, meta = plan(
            f, planning, terminal="free" if name == "free_terminal" else "hard"
        )
        if name == "hourly_plan":
            cmd = np.repeat(cmd, 4)
        rows, _ = simulate("day_ahead", nominal, c, commands=cmd)
        ablations.append(
            dict(
                id=name,
                config=asdict(c),
                summary=summary(rows, c),
                rows=rows,
                solvers=[meta],
            )
        )
    payload = dict(
        schema_version=1,
        provenance="Synthetic teaching profiles; no field measurements",
        cases=cases,
        ablations=ablations,
    )
    (out / "experiment.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    with (out / "summary.csv").open("w", encoding="utf-8", newline="") as f:
        keys = ["id", "scenario", "capacity", "policy"] + list(cases[0]["summary"])
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for case in cases:
            w.writerow({**{k: case[k] for k in keys[:4]}, **case["summary"]})
    with (out / "profiles.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario"] + list(nominal))
        for scenario in ["nominal", "cloud", "surge", "supply_cap"]:
            values = profiles(scenario)
            for row in zip(*values.values()):
                w.writerow([scenario, *row])
    print(
        f"Wrote {len(cases)} cases and {len(ablations)} ablations in {time.time()-start:.1f}s",
        flush=True,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ROOT / "results/ch08")
    main(p.parse_args().out)

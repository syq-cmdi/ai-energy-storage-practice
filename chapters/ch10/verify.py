"""Independent numerical, trajectory-isolation and controller-behavior checks."""

from pathlib import Path
import argparse, json, math, copy, hashlib, io, tempfile
from contextlib import redirect_stdout
from unittest.mock import patch
import numpy as np
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
from run import dump, window_errors
import build_demo

REPO = ROOT.parents[1]


def verify(source):
    d = json.loads(source.read_text(encoding="utf-8"))
    checks = []

    def check(label, value):
        if not value:
            raise AssertionError(label)
        checks.append(label)

    # Emulate Windows default newline translation on every platform. This checks
    # the production writers, including the HTML digest, against actual bytes.
    probe = {"lesson": "换行测试", "values": [1, 2]}
    canonical = json.dumps(probe, ensure_ascii=False, indent=2, allow_nan=False)
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="utf-8", newline="\r\n")
    stream.write(canonical)
    stream.flush()
    windows_bytes = buffer.getvalue()
    check(
        "Windows default newline baseline changes JSON bytes and digest",
        b"\r\n" in windows_bytes
        and hashlib.sha256(windows_bytes).digest()
        != hashlib.sha256(canonical.encode("utf-8")).digest(),
    )
    stream.close()
    original_write_text = Path.write_text

    def windows_default_write_text(
        path, data, encoding=None, errors=None, newline=None
    ):
        return original_write_text(
            path,
            data,
            encoding=encoding,
            errors=errors,
            newline="\r\n" if newline is None else newline,
        )

    with tempfile.TemporaryDirectory(prefix="ch10-lf-") as directory:
        folder = Path(directory)
        console_buffer = io.BytesIO()
        console = io.TextIOWrapper(console_buffer, encoding="cp1252")
        with patch.object(Path, "write_text", windows_default_write_text):
            dump(folder / "probe.json", probe)
            with patch(
                "sys.argv",
                [
                    "build_demo.py",
                    "--results",
                    str(source.resolve()),
                    "--out",
                    str(folder / "demo"),
                ],
            ), redirect_stdout(console):
                build_demo.main()
        console.flush()
        console_metadata = json.loads(console_buffer.getvalue().decode("cp1252"))
        console.close()
        check(
            "JSON writer preserves canonical UTF-8 LF under Windows simulation",
            (folder / "probe.json").read_bytes() == canonical.encode("utf-8"),
        )
        metadata = json.loads(
            (folder / "demo/build_manifest.json").read_text(encoding="utf-8")
        )
        check(
            "console JSON remains readable with Windows cp1252 encoding",
            console_metadata == metadata,
        )
        check(
            "demo HTML digest equals actual emitted bytes under Windows simulation",
            metadata["html_sha256"]
            == hashlib.sha256((folder / "demo/index.html").read_bytes()).hexdigest(),
        )
        check(
            "demo source digest equals input file bytes under Windows simulation",
            metadata["source_sha256"]
            == hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        for filename in ["index.html", "lesson.json", "build_manifest.json"]:
            check(
                "demo " + filename + " retains LF under Windows simulation",
                b"\r\n" not in (folder / "demo" / filename).read_bytes(),
            )

    episodes = d["episodes"]
    byid = {e["id"]: e for e in episodes}
    bundle = d["bundle"]
    models = bundle["models"]
    check(
        "saved data hash matches all trajectory records",
        hashlib.sha256(
            json.dumps(episodes, ensure_ascii=False, indent=2, allow_nan=False).encode(
                "utf-8"
            )
        ).hexdigest()
        == d["config"]["data_sha256"],
    )
    check(
        "all four development models retained",
        len(bundle["development_candidates"]) == 4,
    )
    check("unique trajectory identifiers", len(byid) == len(episodes) == 17)
    check("disjoint generation seeds", len({e["seed"] for e in episodes}) == 17)
    splits = {
        s: {e["id"] for e in episodes if e["split"] == s}
        for s in ["calibration", "train", "validation", "test"]
    }
    check(
        "whole-trajectory split sizes", [len(splits[s]) for s in splits] == [2, 8, 3, 4]
    )
    check(
        "98 hours / 2940 intervals",
        sum(len(e["power"]) for e in episodes) == 2940
        and sum(e["hours"] for e in episodes) == 98,
    )
    for e in episodes:
        n = len(e["power"])
        check(
            e["id"] + " aligned states and intervals",
            len(e["temperature"]) == n + 1
            and len(e["ambient"]) == n
            and np.allclose(e["t_s"], np.arange(n + 1) * DT),
        )
        check(
            e["id"] + " exact-state observation declared",
            e["measurement_noise_std"] == 0,
        )
        residual = C_REF * np.diff(e["temperature"]) - np.array(e["energy_net_kJ"])
        check(
            e["id"] + " integrated thermal balance", float(abs(residual).max()) < 2e-8
        )
    for t, u, ta in [(40.0, 0.0, 20.0), (30.0, 1.5, 22.0), (75.0, 0.6, 18.0)]:
        exact = ta + u / UA_REF + (t - ta - u / UA_REF) * math.exp(-UA_REF * DT / C_REF)
        check(
            "independent beta0 solution " + str(t),
            abs(reference_step(t, u, ta, beta=0) - exact) < 1e-8,
        )
    check(
        "UA zero limiting solution",
        abs(linear_step(40.0, 1.5, 20.0, 418.0, 0) - (40 + 1.5 * DT / 418)) < 1e-12,
    )
    check(
        "physical calibration identified C",
        abs(bundle["physics"]["capacity"] - C_REF) < 1e-6,
    )
    check(
        "physical calibration identified UA",
        abs(bundle["physics"]["ua"] - UA_REF) < 1e-10,
    )
    train = [byid[k] for k in sorted(splits["train"])]
    x = np.concatenate(
        [
            np.column_stack([e["temperature"][:-1], e["ambient"], e["power"]])
            for e in train
        ]
    )
    for kind in ["direct", "residual"]:
        m = models[kind]
        check(
            kind + " scaler trained only on training trajectories",
            np.allclose(m["x_mean"], x.mean(0), rtol=0, atol=1e-12)
            and np.allclose(m["x_scale"], x.std(0), rtol=0, atol=1e-12),
        )
        check(
            kind + " explicit training ids", set(m["training_ids"]) == splits["train"]
        )
        records = [c for c in d["selection"] if c["model"] == kind]
        best = min(records, key=lambda c: (c["validation_h15_rmse"], c["width"]))
        check(kind + " selected by validation only", m["width"] == best["width"])
        archived = [
            c["model"]
            for c in bundle["development_candidates"]
            if c["model"]["kind"] == kind and c["model"]["width"] == m["width"]
        ]
        check(
            kind + " selected weights equal archived development model", archived == [m]
        )
        check(
            kind + " finite network weights",
            all(np.isfinite(w).all() for w in [np.array(v) for v in m["coefs"]]),
        )
    for kind, m in models.items():
        for h in [1, 5, 15, 30]:
            errors = np.concatenate(
                [window_errors(m, byid[k], h) for k in sorted(splits["validation"])]
            )
            ordered = np.sort(abs(errors))
            manual = ordered[math.ceil(0.95 * (len(ordered) - 1))]
            check(
                kind + str(h) + " validation empirical envelope",
                abs(manual - bundle["empirical_bands"][kind][str(h)]) < 1e-12,
            )
            for e in [byid[k] for k in sorted(splits["test"])]:
                errors = window_errors(m, e, h)
                s = 37
                t = e["temperature"][s]
                for j in range(h):
                    t = predict(m, t, e["power"][s + j], e["ambient"][s + j])
                check(
                    kind + e["id"] + str(h) + " independent endpoint rollout",
                    len(errors) == len(e["power"]) - h + 1
                    and abs(errors[s] - (t - e["temperature"][s + h])) < 1e-10,
                )
    for bad_h in [0, -1, 181, True, 1.5]:
        try:
            window_errors(models["direct"], byid["test_nominal"], bad_h)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid horizon accepted")
        checks.append("invalid horizon " + str(bad_h) + " rejected")
    scenario = {s["id"]: s for s in d["control_scenarios"]}
    for c in d["control"]:
        s = scenario[c["scenario"]]
        rows = c["rows"]
        name = c["scenario"] + "/" + c["policy"]
        grid = s["action_grid"]
        check(name + " common initial state", rows[0]["T_before"] == s["initial"])
        check(name + " common length", len(rows) == len(s["ambient"]) == 120)
        check(
            name + " shared action set",
            all(min(abs(r["action"] - u) for u in grid) < 1e-10 for r in rows),
        )
        check(
            name + " causal time alignment",
            all(
                r["time_s"] == k * DT
                and r["target"] == s["target"][k + 1]
                and r["ambient"] == s["ambient"][k]
                for k, r in enumerate(rows)
            ),
        )
        energy = sum(r["action"] for r in rows) * DT / 3600
        check(
            name + " independent kWh sum",
            abs(energy - c["metrics"]["electricity_kWh"]) < 1e-10,
        )
        check(
            name + " thermal balance",
            max(
                abs(C_REF * (r["T_after"] - r["T_before"]) - r["energy_net_kJ"])
                for r in rows
            )
            < 2e-8,
        )
        check(
            name + " executed fallback accounting",
            c["metrics"]["fallback_requested_count"]
            == c["metrics"]["fallback_executed_count"]
            + c["metrics"]["fallback_overridden_count"],
        )
        check(
            name + " observed temperature interlock",
            all(r["action"] == 0 for r in rows if r["T_before"] >= INTERLOCK_T),
        )
        for r in rows:
            if c["policy"] == "rule":
                continue
            check(
                name + str(r["step"]) + " identical planner candidate actions",
                np.allclose([x["action"] for x in r["candidates"]], grid),
            )
            feasible = [v for v in r["candidates"] if v["feasible"]]
            if not r["fallback"]:
                best = min(feasible, key=lambda v: (v["cost"], v["action"]))
                check(
                    name + str(r["step"]) + " candidate minimum",
                    abs(best["action"] - r["requested_action"]) < 1e-12,
                )
            else:
                check(
                    name
                    + str(r["step"])
                    + " fallback has no feasible learned candidate",
                    not feasible,
                )
            if r["step"] in [0, 39, 80, 119]:
                refs = np.array(
                    [s["target"][min(120, r["step"] + j + 1)] for j in range(HORIZON)]
                )
                previous = rows[r["step"] - 1]["action"] if r["step"] else 0
                for v in r["candidates"]:
                    cost = float(
                        np.mean((np.array(v["prediction"]) - refs) ** 2)
                        + 0.08 * v["action"]
                        + 0.15 * (v["action"] - previous) ** 2
                    )
                    check(
                        name
                        + str(r["step"])
                        + str(v["action"])
                        + " independent K2 objective",
                        abs(cost - v["cost"]) < 1e-9,
                    )
    guarded = {
        c["scenario"]: c for c in d["control"] if c["policy"] == "guarded_residual"
    }
    check(
        "extended actions rejected without executed fallback",
        guarded["extended_power"]["metrics"]["domain_rejections"] > 0
        and guarded["extended_power"]["metrics"]["fallback_executed_count"] == 0,
    )
    check(
        "hot start has executed physical feedback",
        guarded["hot_start"]["metrics"]["fallback_executed_count"] > 0,
    )
    check(
        "hot start separately records interlock overriding fallback",
        guarded["hot_start"]["metrics"]["fallback_overridden_count"] > 0,
    )
    for probe in d["domain_probes"]:
        if probe["case"] == "invalid_observation":
            check(
                "invalid observation zero power",
                probe["result"]["action"] == 0
                and probe["result"]["fallback_kind"] == "zero_power",
            )
        elif probe["case"] != "in_domain":
            check(probe["case"] + " fallback exercised", probe["result"]["fallback"])
    # A fabricated nonfinite network response tests execution recovery, without touching reference dynamics.
    broken = copy.deepcopy(models["residual"])
    broken["biases"][-1][0] = float("nan")
    result = plan(
        broken,
        50.0,
        np.full(HORIZON, 22.0),
        np.full(HORIZON, 60.0),
        0.0,
        np.linspace(0, 1.5, 6),
        bundle["domain"],
        bundle["physics"],
    )
    check(
        "nonfinite prediction produces finite fallback",
        result["fallback"] and np.isfinite(result["action"]),
    )
    check(
        "nonfinite prediction reason retained",
        result["fallback_reason"] == "nonfinite_prediction",
    )
    check(
        "invalid requested power reaches zero",
        execute_action(50.0, float("nan"), 1.5) == (0.0, True),
    )
    out = dict(
        passed=len(checks),
        checks=checks,
        maximum_thermal_balance_tolerance_kJ=2e-8,
        scope="constructed W-H1 experiments and specified faults",
    )
    (source.parent / "verification.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(
        json.dumps({"passed": len(checks), "scope": out["scope"]}, ensure_ascii=False)
    )
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, default=REPO / "results/ch10/experiment.json")
    verify(p.parse_args().source)

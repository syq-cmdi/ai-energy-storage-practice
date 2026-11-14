"""Build an offline interactive replay from reproducible solver trajectories."""

from pathlib import Path
import argparse, json

ROOT = Path(__file__).resolve().parents[2]


def compact(x):
    if isinstance(x, float):
        return round(x, 7)
    if isinstance(x, list):
        return [compact(v) for v in x]
    if isinstance(x, dict):
        return {k: compact(v) for k, v in x.items()}
    return x


def build(source, out):
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    fields = [
        "id",
        "scenario",
        "volume",
        "policy",
        "horizon",
        "bias",
        "config",
        "capacity_kwh",
        "load",
        "temp",
        "price",
        "g",
        "c",
        "d",
        "u",
        "energy",
        "electricity",
        "supply_temp",
        "flow",
        "metrics",
    ]
    runs = []
    for r in data["runs"]:
        q = {k: r[k] for k in fields}
        q["plans"] = [
            {k: p[k] for k in ["k", "forecast", "energy"]} for p in r["plans"]
        ]
        runs.append(q)
    obj = compact(
        {
            "chapter": 5,
            "runs": runs,
            "annual": data["annual"],
            "training": data["forecast_training"],
            "scenarios": {d["key"]: d["name"] for d in data["days"]},
        }
    )
    js = (
        "window.CH05_DATA="
        + json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        + ";\n"
    )
    (out / "data.js").write_text(js, encoding="utf-8")
    template = (out / "index.html").read_text(encoding="utf-8")
    template = template.replace(
        '<link rel="stylesheet" href="style.css">',
        "<style>" + (out / "style.css").read_text(encoding="utf-8") + "</style>",
    )
    for name in ["data.js", "math.js", "app.js"]:
        template = template.replace(
            f'<script src="{name}"></script>',
            "<script>"
            + (out / name).read_text(encoding="utf-8").replace("</script", "<\\/script")
            + "</script>",
        )
    (out / "教学演示.html").write_text(template, encoding="utf-8")
    print(f"Offline replay: {len(runs)} cases, {len(template.encode('utf-8'))} bytes")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=ROOT / "results/ch05/experiment.json")
    p.add_argument("--out", type=Path, default=ROOT / "demo/ch05")
    a = p.parse_args()
    build(a.source, a.out)

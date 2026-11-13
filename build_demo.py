"""Build an offline teaching demo from saved CSV predictions (no refitting)."""

from pathlib import Path
import argparse, csv, hashlib, json

ROOT = Path(__file__).resolve().parent


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def build(results):
    metrics = json.loads((results / "metrics.json").read_text())
    predictions = read_csv(results / "predictions.csv")
    cycles = read_csv(results / "cycles.csv")
    data = {
        "kind": "constructed",
        "selected": metrics["selected_family"],
        "radius": metrics["empirical_interval"]["radius_pp"],
        "metrics": metrics,
        "cells": {},
        "cycles": {},
        "source_sha256": {
            n: hashlib.sha256((results / n).read_bytes()).hexdigest()
            for n in ["predictions.csv", "cycles.csv", "metrics.json"]
        },
    }
    for cell in ["C09", "C10", "C11", "C12"]:
        rows = [r for r in predictions if r["cell_id"] == cell]
        data["cells"][cell] = {
            k: [float(r[k]) for r in rows]
            for k in [
                "target_cycle",
                "target_soh",
                "persistence",
                "ridge",
                "forest",
                "window_mlp",
                "lower_soh",
                "upper_soh",
            ]
        }
    for cell in sorted({r["cell_id"] for r in cycles}):
        data["cycles"][cell] = [
            [
                int(r["cycle"]),
                float(r["capacity_ah"]) / float(r["reference_capacity_ah"]),
                float(r["resistance_ohm"]),
                float(r["temperature_c"]),
            ]
            for r in cycles
            if r["cell_id"] == cell
        ]
    payload = (
        "window.LESSON_DATA = "
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        + ";\n"
    )
    (ROOT / "demo/data.js").write_text(payload, encoding="utf-8")
    html = (ROOT / "demo/index.html").read_text()
    for name in ["data.js", "math.js", "app.js"]:
        html = html.replace(
            f'<script src="{name}"></script>',
            "<script>"
            + (ROOT / "demo" / name).read_text().replace("</script", r"<\/script")
            + "</script>",
        )
    html = html.replace(
        '<link rel="stylesheet" href="style.css">',
        "<style>" + (ROOT / "demo/style.css").read_text() + "</style>",
    )
    (ROOT / "demo/教学演示.html").write_text(html, encoding="utf-8")
    print(
        f"Offline demo: {len(predictions)} frozen predictions; 12 cells; no network dependency"
    )
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results", type=Path, default=ROOT / "chapters/ch02/reference_results"
    )
    build(parser.parse_args().results)

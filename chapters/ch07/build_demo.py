from pathlib import Path
import argparse, json

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--source", type=Path, default=ROOT / "results/ch07/experiment.json"
    )
    a = ap.parse_args()
    ex = json.loads(a.source.read_text())
    out = ROOT / "demo/ch07"
    data = dict(
        config=ex["config"],
        selected_seed=ex["selected_seed"],
        q=ex["selected_q"],
        profiles={
            s: [r["demand_kw"] for r in ex["traces"][s + "/lowpass"]]
            for s in ex["scenarios"]
        },
    )
    (out / "data.js").write_text(
        "const CH07_DATA=" + json.dumps(data, separators=(",", ":")) + ";\n"
    )
    html = (
        (out / "index.html")
        .read_text()
        .replace(
            '<link rel="stylesheet" href="style.css">',
            "<style>" + (out / "style.css").read_text() + "</style>",
        )
    )
    for f in ["data.js", "math.js", "app.js"]:
        html = html.replace(
            f'<script src="{f}"></script>',
            "<script>" + (out / f).read_text() + "</script>",
        )
    (out / "教学演示.html").write_text(html)
    print("offline demo:", out / "教学演示.html")


if __name__ == "__main__":
    main()

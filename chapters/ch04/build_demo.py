"""Build the completely offline teaching demo and Python/JS parity fixtures."""

from pathlib import Path
import json
import argparse
import tempfile
from run import run

ROOT = Path(__file__).resolve().parents[2]


def build(source):
    d = json.loads(source.read_text(encoding="utf-8"))
    demo = ROOT / "demo/ch04"
    episodes = [e for e in d["episodes"] if e["role"] == "test"]
    payload = {
        "summary": {
            k: d["summary"][k] for k in ["physical_fit", "beta_fitted", "chosen_q"]
        },
        "episodes": episodes,
        "expected": {e["id"]: d["results"][e["id"]]["metrics"] for e in episodes},
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    (demo / "data.js").write_text(
        "window.CH04_DATA=" + encoded + ";\n", encoding="utf-8"
    )
    html = (
        (demo / "index.html")
        .read_text(encoding="utf-8")
        .replace(
            '<link rel="stylesheet" href="style.css">',
            "<style>" + (demo / "style.css").read_text(encoding="utf-8") + "</style>",
        )
    )
    for name in ["data.js", "math.js", "app.js"]:
        html = html.replace(
            f'<script src="{name}"></script>',
            "<script>" + (demo / name).read_text(encoding="utf-8") + "</script>",
        )
    (demo / "教学演示.html").write_text(html, encoding="utf-8")
    print(
        f"Offline demo: {len(html.encode())} bytes; {len(episodes)} independent cases"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path)
    a = p.parse_args()
    if a.source:
        build(a.source)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "experiment"
            run(out)
            build(out / "experiment.json")

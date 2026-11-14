"""Build a self-contained, offline lesson from the frozen executed experiment."""

from pathlib import Path
import argparse, hashlib, json

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--results", type=Path, default=ROOT / "results/ch10/experiment.json"
    )
    p.add_argument("--out", type=Path, default=ROOT / "demo/ch10")
    args = p.parse_args()
    data = json.loads(args.results.read_text(encoding="utf-8"))
    # The same record feeds the Python figures, browser weights, and playback ledger.
    encoded = json.dumps(
        data, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    template = (HERE / "demo_template.html").read_text(encoding="utf-8")
    html = template.replace(
        "__ENGINE__", (HERE / "engine.js").read_text(encoding="utf-8")
    ).replace("__DATA__", encoded.replace("</", "<\\/"))
    assert "__ENGINE__" not in html and "__DATA__" not in html
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "index.html").write_text(html, encoding="utf-8")
    (args.out / "lesson.json").write_text(encoded + "\n", encoding="utf-8")
    metadata = dict(
        title="动态学习与模型辅助控制",
        source_sha256=hashlib.sha256(args.results.read_bytes()).hexdigest(),
        html_sha256=hashlib.sha256(html.encode()).hexdigest(),
        episodes=len(data["episodes"]),
        control_runs=len(data["control"]),
        offline=True,
        computation="exported tanh model forward pass; actual Python control replay",
        rights="../../RIGHTS.md",
    )
    (args.out / "build_manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()

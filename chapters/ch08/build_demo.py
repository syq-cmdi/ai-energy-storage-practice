"""Build a self-contained, offline teaching demonstration."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def compact(value):
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, list):
        return [compact(v) for v in value]
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items() if k != "solvers"}
    return value


def main():
    data = json.loads(
        (ROOT / "results/ch08/experiment.json").read_text(encoding="utf-8")
    )
    payload = compact({"cases": data["cases"]})
    template = (HERE / "demo_template.html").read_text(encoding="utf-8")
    html = template.replace(
        "__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    ).replace("__CORE__", (HERE / "demo_core.js").read_text(encoding="utf-8"))
    out = ROOT / "demo/ch08"
    out.mkdir(parents=True, exist_ok=True)
    (out / "教学演示.html").write_text(html, encoding="utf-8")
    print("Built offline chapter 8 demonstration")


if __name__ == "__main__":
    main()

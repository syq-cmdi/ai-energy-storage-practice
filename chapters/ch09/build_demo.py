"""Build a fully offline, live retrieval and calculator lesson."""

import json
from pathlib import Path
from core import ROOT, Index

R = ROOT.parents[1]
data = json.loads((R / "results/ch09/experiment.json").read_text(encoding="utf-8"))
ix = Index(data["config"]["rank"])
index = {
    "chunks": ix.chunks,
    "vocab": ix.vocab,
    "lookup": ix.lookup,
    "idf": ix.idf.tolist(),
    "df": ix.df.tolist(),
    "lengths": ix.lengths.tolist(),
    "avg_length": ix.avg_length,
    "tfidf": ix.tfidf.tolist(),
    "components": ix.components.tolist(),
    "lsa": ix.lsa.tolist(),
    "counts": ix.counts,
}
(R / "demo/ch09").mkdir(exist_ok=True, parents=True)
# Shared JSON allows Node to compare every preset with the independent Python result.
(R / "demo/ch09/lesson.json").write_text(
    json.dumps({"index": index, **data}, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8",
)
engine = (ROOT / "engine.js").read_text(encoding="utf-8")
template = (ROOT / "demo_template.html").read_text(encoding="utf-8")
payload = json.dumps(
    {"index": index, **data}, ensure_ascii=False, separators=(",", ":")
).replace("</", "<\\/")
html = template.replace("__ENGINE__", engine).replace("__DATA__", payload)
(R / "demo/ch09/教学演示.html").write_text(html, encoding="utf-8")
print("Built offline lesson; " + str(len(html.encode("utf-8"))) + " bytes")

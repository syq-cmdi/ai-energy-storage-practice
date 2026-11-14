"""Freeze on development questions, then evaluate the untouched test questions."""

from pathlib import Path
import argparse, copy, json, hashlib
import numpy as np
from core import ROOT, Index, digest
from tools_readonly import execute, example_request

REPO = ROOT.parents[1]


def score(index, questions, labels, method):
    rows = []
    for q in questions:
        hits = index.search(q, method)
        ids = [h["chunk"]["id"] for h in hits]
        gold = labels[q["id"]]
        ev = gold["evidence"]
        answer = index.answer(q, method)
        ranks = [ids.index(x) + 1 for x in ev if x in ids]
        relevant = len(set(ev) & set(ids))
        rows.append(
            {
                "id": q["id"],
                "method": method,
                "hits": [{"id": h["chunk"]["id"], "score": h["score"]} for h in hits],
                "answer": answer,
                "expected": gold["status"],
                "gold": ev,
                "recall": relevant / len(ev) if ev else None,
                "rr": 1 / min(ranks) if ranks else 0,
                "status_correct": answer["status"] == gold["status"],
                "evidence_correct": bool(ev)
                and set(answer["evidence"]).issubset(ev)
                and bool(answer["evidence"]),
                "baseline_supported": bool(ids) and ids[0] in ev,
            }
        )
    positive = [r for r in rows if r["gold"]]
    answered = [r for r in rows if r["answer"]["status"] == "grounded"]
    metrics = {
        "n": len(rows),
        "positive_n": len(positive),
        "recall_at_3": float(np.mean([r["recall"] for r in positive])),
        "mrr_at_3": float(np.mean([r["rr"] for r in positive])),
        "status_accuracy": float(np.mean([r["status_correct"] for r in rows])),
        "answer_coverage": len(answered) / len(rows),
        "supported_answer_precision": sum(r["evidence_correct"] for r in answered)
        / max(1, len(answered)),
        "baseline_top1_support": sum(r["baseline_supported"] for r in rows) / len(rows),
    }
    return rows, metrics


def main(out):
    out.mkdir(parents=True, exist_ok=True)
    frozen = json.loads((ROOT / "data/freeze.json").read_text(encoding="utf-8"))
    for name, h in frozen.items():
        assert digest((ROOT / "data" / name).read_bytes()) == h, (name, h)
    questions = json.loads((ROOT / "data/questions.json").read_text(encoding="utf-8"))
    labels = json.loads(
        (ROOT / "data/reference_labels.json").read_text(encoding="utf-8")
    )
    dev = [q for q in questions if q["split"] == "dev"]
    test = [q for q in questions if q["split"] == "test"]
    tuning = []
    for rank in [4, 8, 12, 20]:
        ix = Index(rank)
        _, m = score(ix, dev, labels, "lsa")
        tuning.append({"rank": rank, **m})
    chosen = max(tuning, key=lambda t: (t["mrr_at_3"], t["recall_at_3"], -t["rank"]))[
        "rank"
    ]
    ix = Index(chosen)
    # Commit selection to disk before any test scoring.
    config = {
        "rank": chosen,
        "top_k": 3,
        "k1": 1.2,
        "b": 0.75,
        "selection": "dev MRR@3, recall@3, smaller rank",
        "freeze": frozen,
    }
    (out / "selected_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    rows = []
    metrics = {}
    for split, qs in [("dev", dev), ("test", test)]:
        metrics[split] = {}
        for method in ["bm25", "tfidf", "lsa"]:
            r, m = score(ix, qs, labels, method)
            rows += r
            metrics[split][method] = m
    faults = []
    for fault in [
        "none",
        "timeout_once",
        "timeout_twice",
        "wrong_unit",
        "wrong_value",
        "extra_action",
        "malformed",
    ]:
        faults.append(
            {
                "case": fault,
                "request": example_request(),
                "response": execute(example_request(), fault),
            }
        )
    thermal = example_request("water_sensible_heat")
    faults.append({"case": "thermal", "request": thermal, "response": execute(thermal)})
    for case in [
        "unit_mismatch",
        "unknown_tool",
        "unknown_argument",
        "bool_number",
        "unit_conversion",
    ]:
        req = example_request()
        if case == "unit_mismatch":
            req["arguments"]["power"]["unit"] = "kWh"
        elif case == "unknown_tool":
            req["tool"] = "set_soc"
        elif case == "unknown_argument":
            req["arguments"]["command"] = "run"
        elif case == "bool_number":
            req["arguments"]["soc"]["value"] = True
        else:
            req["arguments"]["energy"] = {"value": 1000000, "unit": "Wh"}
            req["arguments"]["power"] = {"value": 300000, "unit": "W"}
        faults.append({"case": case, "request": req, "response": execute(req)})
    result = {
        "data_kind": "author-created synthetic teaching corpus",
        "config": config,
        "tuning": tuning,
        "metrics": metrics,
        "rows": rows,
        "tools": faults,
        "questions": questions,
        "chunks": ix.chunks,
    }
    (out / "experiment.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ROOT / "results_reference.json").write_text(
        json.dumps(
            {"config": config, "tuning": tuning, "metrics": metrics},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "selected_rank": chosen,
                "test": metrics["test"],
                "tools": {f["case"]: f["response"]["status"] for f in faults},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=REPO / "results/ch09")
    main(p.parse_args().out)

"""Deterministic retrieval and claim checking. Gold labels are never loaded here."""

from pathlib import Path
from collections import Counter
import hashlib, json, re, math
import numpy as np

ROOT = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def tokens(text):
    s = re.sub(r"\s+", "", text.lower())
    return list(s) + [s[i : i + 2] for i in range(len(s) - 1)]


def eligible(meta, q):
    return (
        meta["authorized"]
        and meta["status"] == "released"
        and meta["asset"] == q["asset"]
        and meta["group"] == q["group"]
        and meta["valid_from"] <= q["as_of"] <= meta["valid_to"]
    )


def load_corpus():
    chunks = []
    for m in json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8")):
        raw = (ROOT / "data" / m["path"]).read_bytes()
        if digest(raw) != m["sha256"]:
            raise ValueError("Corpus hash mismatch: " + m["doc_id"])
        text = raw.decode("utf-8")
        starts = list(re.finditer(r"^## (D\d+-C\d+) (.+)$", text, re.M))
        for i, match in enumerate(starts):
            start = match.start()
            end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
            excerpt = text[start:end].rstrip()
            fact = re.search(r"^事实\|([^|]+)\|([^|]+)\|([^\n]+)", excerpt, re.M)
            chunks.append(
                dict(
                    id=match[1],
                    meta=m,
                    text=excerpt,
                    start=start,
                    end=start + len(excerpt),
                    line_start=text[:start].count("\n") + 1,
                    line_end=text[: start + len(excerpt)].count("\n") + 1,
                    fact=(
                        dict(metric=fact[1], value=fact[2], unit=fact[3])
                        if fact
                        else None
                    ),
                )
            )
    return chunks


class Index:
    def __init__(self, rank=12):
        self.chunks = load_corpus()
        self.counts = [Counter(tokens(c["text"])) for c in self.chunks]
        self.vocab = sorted(set().union(*self.counts))
        self.lookup = {t: i for i, t in enumerate(self.vocab)}
        x = np.array([[c[t] for t in self.vocab] for c in self.counts], dtype=float)
        self.df = (x > 0).sum(axis=0)
        self.idf = np.log((1 + len(x)) / (1 + self.df)) + 1
        self.lengths = x.sum(axis=1)
        self.avg_length = float(self.lengths.mean())
        weighted = x * self.idf
        self.tfidf = weighted / np.maximum(
            np.linalg.norm(weighted, axis=1, keepdims=True), 1e-12
        )
        _, _, vt = np.linalg.svd(self.tfidf, full_matrices=False)
        self.components = vt[:rank]
        z = self.tfidf @ self.components.T
        self.lsa = z / np.maximum(np.linalg.norm(z, axis=1, keepdims=True), 1e-12)
        self.rank = rank

    def search(self, q, method="bm25", k=3):
        ct = Counter(tokens(q["text"]))
        qv = np.array([ct[t] for t in self.vocab], float) * self.idf
        qv /= max(float(np.linalg.norm(qv)), 1e-12)
        if method == "tfidf":
            scores = self.tfidf @ qv
        elif method == "lsa":
            z = qv @ self.components.T
            z /= max(float(np.linalg.norm(z)), 1e-12)
            scores = self.lsa @ z
        elif method == "bm25":
            scores = np.zeros(len(self.chunks))
            for t in ct:
                if t not in self.lookup:
                    continue
                j = self.lookup[t]
                df = self.df[j]
                idf = math.log(1 + (len(scores) - df + 0.5) / (df + 0.5))
                for i, c in enumerate(self.counts):
                    f = c[t]
                    scores[i] += (
                        idf
                        * f
                        * 2.2
                        / (f + 1.2 * (0.25 + 0.75 * self.lengths[i] / self.avg_length))
                    )
        else:
            raise ValueError(method)
        ids = [
            i
            for i, c in enumerate(self.chunks)
            if eligible(c["meta"], q) and scores[i] > 1e-10
        ]
        ids.sort(key=lambda i: (-scores[i], self.chunks[i]["id"]))
        return [dict(chunk=self.chunks[i], score=float(scores[i])) for i in ids[:k]]

    def answer(self, q, method="bm25", k=3):
        hits = self.search(q, method, k)
        chosen = [
            h["chunk"]
            for h in hits
            if h["chunk"]["fact"] and h["chunk"]["fact"]["metric"] == q["metric"]
        ]
        if not chosen:
            return dict(
                status="needs_evidence",
                claims=[],
                evidence=[],
                text="当前对象、日期与授权范围内，前k项未检得目标属性证据。请补充资料或调整检索。",
            )
        # A second attribute audit scans eligible facts. It detects overlap without boosting recall.
        allfacts = [
            c
            for c in self.chunks
            if eligible(c["meta"], q)
            and c["fact"]
            and c["fact"]["metric"] == q["metric"]
        ]
        if len({(c["fact"]["value"], c["fact"]["unit"]) for c in allfacts}) > 1:
            return dict(
                status="conflict",
                claims=[],
                evidence=[c["id"] for c in allfacts],
                text="有效范围内存在同属性数值冲突，请由资料负责人确定采用版本。",
            )
        c = chosen[0]
        claim = dict(
            **c["fact"], chunk_id=c["id"], quote=c["text"], sha256=c["meta"]["sha256"]
        )
        return dict(
            status="grounded",
            claims=[claim],
            evidence=[c["id"]],
            text=f"教学语料记录：{claim['value']} {claim['unit']}。出处：{c['id']}，第{c['line_start']}—{c['line_end']}行。",
        )

    def validate_generated(self, q, payload, retrieved):
        """Optional generator adapter: accepts data claims only, never model tool proposals."""
        if (
            not isinstance(payload, dict)
            or set(payload) != {"claims"}
            or not isinstance(payload["claims"], list)
            or not payload["claims"]
        ):
            return False
        allowed = {h["chunk"]["id"]: h["chunk"] for h in retrieved}
        for c in payload["claims"]:
            if not isinstance(c, dict) or set(c) != {
                "metric",
                "value",
                "unit",
                "chunk_id",
                "quote",
                "sha256",
            }:
                return False
            block = allowed.get(c["chunk_id"])
            if not block or not eligible(block["meta"], q) or not block["fact"]:
                return False
            if c["sha256"] != block["meta"]["sha256"] or c["quote"] != block["text"]:
                return False
            if c["metric"] != q["metric"] or any(
                str(c[k]) != block["fact"][k] for k in ("metric", "value", "unit")
            ):
                return False
        facts = [
            x["fact"]
            for x in self.chunks
            if eligible(x["meta"], q)
            and x["fact"]
            and x["fact"]["metric"] == q["metric"]
        ]
        return len({(x["value"], x["unit"]) for x in facts}) == 1

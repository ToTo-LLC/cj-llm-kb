"""BM25VaultIndex — per-domain BM25 retrieval with a state.sqlite pickle cache.

Contract:
    - Lazy per-session build; cache keyed by per-domain vault content hash.
    - Corpus excludes any .md file whose relative path contains a `chats`
      component — chat threads have their own retrieval path.
    - scope_guard is intentionally NOT called here. Retrieval reads the
      domain's files after callers explicitly ask for that domain; scope
      enforcement is the TOOL layer's job (see Plan 03 Task 6).
    - Pickle is used for the on-disk cache. The blob lives in our own
      state.sqlite; we trust our own cache. On any load failure we
      transparently rebuild.
"""

from __future__ import annotations

import hashlib
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from brain_core.state.db import StateDB
from brain_core.vault.frontmatter import FrontmatterError, parse_frontmatter

# Trimmed to 50 tokens (Plan 03 Task 24 sweep). Modal verbs (would, could,
# may, might, must, shall) and inflected be-forms (been, being, did) carry
# enough topical weight in a personal KB that aggressive filtering hurt
# recall. Keep the list compact and obvious.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "is",
        "are",
        "was",
        "were",
        "be",
        "have",
        "has",
        "had",
        "do",
        "does",
        "will",
        "should",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "about",
        "against",
        "between",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "from",
        "up",
        "down",
        "out",
        "off",
        "over",
        "under",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "as",
    }
)

_TOKEN_RE = re.compile(r"\w+")
_WS_RE = re.compile(r"\s+")


def _tokenize(text: str) -> list[str]:
    """Lowercase, \\w+ split, drop stopwords. Returned list may be empty."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


@dataclass(frozen=True)
class SearchHit:
    """A single BM25 search result. `path` is vault-relative."""

    path: Path
    score: float
    title: str
    snippet: str


_IndexEntry = tuple[BM25Okapi, list[dict[str, Any]]]


class BM25VaultIndex:
    """BM25 retrieval over a vault, cached in state.sqlite per domain."""

    def __init__(self, vault_root: Path, db: StateDB) -> None:
        self.vault_root = vault_root
        self.db = db
        self._indexes: dict[str, _IndexEntry] = {}
        self._last_build_was_cache_hit: dict[str, bool] = {}

    def build(self, domains: tuple[str, ...]) -> None:
        """Build (or load from cache) BM25 indexes for the given domains."""
        for domain in domains:
            vault_hash = self._compute_vault_hash(domain)
            cached = self._load_cache(domain, vault_hash)
            if cached is not None:
                self._indexes[domain] = cached
                self._last_build_was_cache_hit[domain] = True
                continue
            docs = self._read_domain_docs(domain)
            tokenized = [_tokenize(f"{d['title']}\n{d['body']}") for d in docs]
            # rank_bm25 cannot be constructed on an empty corpus; use a
            # single-empty-doc placeholder so search() degrades gracefully
            # (it will simply return no hits since get_scores on an empty
            # token list is short-circuited above).
            bm25 = BM25Okapi(tokenized) if tokenized else BM25Okapi([[""]])
            entry: _IndexEntry = (bm25, docs)
            self._indexes[domain] = entry
            self._save_cache(domain, vault_hash, entry)
            self._last_build_was_cache_hit[domain] = False

    def search(
        self,
        query: str,
        *,
        domains: tuple[str, ...],
        top_k: int = 5,
    ) -> list[SearchHit]:
        """Return the top_k BM25 hits for `query` across `domains`."""
        for d in domains:
            if d not in self._indexes:
                raise RuntimeError(f"index for domain {d!r} not built")
        tokens = _tokenize(query)
        if not tokens:
            return []
        scored: list[tuple[float, dict[str, Any]]] = []
        for d in domains:
            bm25, docs = self._indexes[d]
            if not docs:
                continue
            scores = bm25.get_scores(tokens)
            for score, doc in zip(scores, docs, strict=True):
                if score > 0:
                    scored.append((float(score), doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]
        return [
            SearchHit(
                path=Path(doc["rel_path"]),
                score=score,
                title=doc["title"],
                snippet=self._make_snippet(doc["body"], tokens),
            )
            for score, doc in top
        ]

    def was_cache_hit(self, domain: str) -> bool:
        """True if the last build() call for this domain loaded from cache."""
        return self._last_build_was_cache_hit.get(domain, False)

    # ---- internals ---------------------------------------------------------

    def _iter_domain_files(self, domain: str) -> list[Path]:
        domain_root = self.vault_root / domain
        if not domain_root.exists():
            return []
        out: list[Path] = []
        for md in sorted(domain_root.rglob("*.md")):
            rel = md.relative_to(self.vault_root)
            if "chats" in rel.parts:
                continue
            out.append(md)
        return out

    def _compute_vault_hash(self, domain: str) -> str:
        entries: list[tuple[str, int, int]] = []
        for md in self._iter_domain_files(domain):
            rel = md.relative_to(self.vault_root)
            stat = md.stat()
            # Use forward-slash rel path for cross-platform stable hashing.
            entries.append((rel.as_posix(), stat.st_mtime_ns, stat.st_size))
        entries.sort()
        return hashlib.sha256(repr(entries).encode("utf-8")).hexdigest()

    def _read_domain_docs(self, domain: str) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        for md in self._iter_domain_files(domain):
            rel = md.relative_to(self.vault_root)
            raw = md.read_text(encoding="utf-8")
            try:
                fm, body = parse_frontmatter(raw)
            except FrontmatterError:
                fm, body = {}, raw
            title = str(fm.get("title", rel.stem))
            docs.append(
                {
                    "rel_path": rel.as_posix(),
                    "title": title,
                    "body": body,
                }
            )
        return docs

    def _load_cache(self, domain: str, vault_hash: str) -> _IndexEntry | None:
        cur = self.db.exec(
            "SELECT vault_hash, index_blob FROM bm25_cache WHERE domain = ?",
            (domain,),
        )
        row = cur.fetchone()
        if row is None or row[0] != vault_hash:
            return None
        try:
            result = pickle.loads(row[1])
        except Exception:
            return None
        if not isinstance(result, tuple) or len(result) != 2:
            return None
        bm25, docs = result
        if not isinstance(bm25, BM25Okapi) or not isinstance(docs, list):
            return None
        return bm25, docs

    def _save_cache(self, domain: str, vault_hash: str, payload: _IndexEntry) -> None:
        blob = pickle.dumps(payload)
        self.db.exec(
            "INSERT OR REPLACE INTO bm25_cache(domain, vault_hash, index_blob, built_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            (domain, vault_hash, blob),
        )

    def _make_snippet(self, body: str, tokens: list[str]) -> str:
        lower = body.lower()
        for t in tokens:
            idx = lower.find(t)
            if idx >= 0:
                start = max(0, idx - 100)
                end = min(len(body), idx + 100)
                return _WS_RE.sub(" ", body[start:end]).strip()
        return _WS_RE.sub(" ", body[:200]).strip()

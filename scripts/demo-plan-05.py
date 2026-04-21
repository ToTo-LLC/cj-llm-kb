"""Plan 05 end-to-end demo.

Spins up ``brain_api`` in-process via Starlette's ``TestClient``, exercises
REST + WebSocket against a temp vault with ``FakeLLMProvider``, and asserts
the 14 demo gates from the plan header (tasks/plans/05-api.md § Task 24).
Prints ``PLAN 05 DEMO OK`` on success.

All LLM calls go through :class:`FakeLLMProvider` — no network, no API key
required. All vault I/O runs against a ``tempfile.TemporaryDirectory``.

Known wiring notes:

* ``TestClient`` (vs. ``httpx.ASGITransport`` + ``httpx.AsyncClient``) was
  chosen because it runs the lifespan automatically. With the bare ASGI
  transport, ``app.state.ctx`` is ``None`` until a lifespan-aware wrapper
  (e.g., ``asgi_lifespan.LifespanManager``) drives it. ``TestClient`` keeps
  the demo dependency-free AND works for both REST and WebSocket gates.

* Gate 11 drains the ``patches`` rate-limiter bucket to force 429. The
  ``ToolContext`` dataclass is frozen, so we mutate ``rate_limiter`` via
  ``object.__setattr__`` (same trick Plan 04 Task 24 used). The original
  limiter is restored afterwards so the WS gates don't inherit a drained
  bucket.

* Gate 13's FakeLLM response is queued BEFORE opening the WS. The queue
  is FIFO; ``ChatSession.turn`` drains one entry per turn. ``ChatSession``
  tokenizes queued text into per-character deltas (Plan 03 behavior), so a
  single queued response yields multiple ``delta`` frames.

* ``TestClient.websocket_connect`` hard-codes ``Host: testserver``; we
  pass ``headers={"Host": "localhost"}`` explicitly so
  :class:`OriginHostMiddleware` treats the upgrade as loopback (Task 17).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from brain_api import create_app
from brain_core.rate_limit import RateLimitConfig, RateLimiter
from fastapi.testclient import TestClient

_LOOPBACK_WS_HEADERS = {"Host": "localhost"}


def _check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        raise SystemExit(1)
    print(f"  OK  {msg}")


def _scaffold_vault(root: Path) -> None:
    """Seed a vault matching ``brain_api/tests/conftest.py::seeded_vault``.

    Two in-scope research notes plus an index; one out-of-scope personal
    note used by Gate 10's scope-guard assertion; a BRAIN.md for the
    resource endpoint; all written with LF line endings for cross-platform
    parity with CLAUDE.md principle #8.
    """
    (root / "research" / "notes").mkdir(parents=True)
    (root / "personal" / "notes").mkdir(parents=True)
    (root / "research" / "notes" / "karpathy.md").write_text(
        "---\ntitle: Karpathy\n---\nLLM wiki pattern.\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "research" / "notes" / "rag.md").write_text(
        "---\ntitle: RAG\n---\nRetrieval-augmented generation.\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "research" / "index.md").write_text(
        "# research\n- [[karpathy]]\n- [[rag]]\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "personal" / "notes" / "secret.md").write_text(
        "---\ntitle: Secret\n---\nnever read me\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "BRAIN.md").write_text(
        "# BRAIN\n\nYou are brain.\n",
        encoding="utf-8",
        newline="\n",
    )


def _run_demo() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "vault"
        _scaffold_vault(vault)

        app = create_app(vault_root=vault, allowed_domains=("research",))

        with TestClient(app, base_url="http://localhost") as c:
            token = app.state.ctx.token
            headers_ok = {
                "Origin": "http://localhost:4317",
                "X-Brain-Token": token,
            }

            # ------------------------------------------------------------
            # Gate 1 — /healthz
            # ------------------------------------------------------------
            print("[gate 1] /healthz")
            r = c.get("/healthz")
            _check(
                r.status_code == 200 and r.json() == {"status": "ok"},
                "/healthz -> 200 ok",
            )

            # ------------------------------------------------------------
            # Gate 2 — GET /api/tools lists 18 brain_* tools
            # ------------------------------------------------------------
            print("[gate 2] GET /api/tools")
            r = c.get("/api/tools")
            _check(r.status_code == 200, f"/api/tools -> 200 (got {r.status_code})")
            tools = r.json()["tools"]
            names = {t["name"] for t in tools}
            _check(len(tools) == 18, f"18 tools listed (got {len(tools)})")
            _check(
                all(n.startswith("brain_") for n in names),
                "all tool names start with brain_",
            )

            # ------------------------------------------------------------
            # Gate 3 — POST brain_list_domains with valid token + origin
            # ------------------------------------------------------------
            print("[gate 3] POST brain_list_domains (authed)")
            r = c.post("/api/tools/brain_list_domains", json={}, headers=headers_ok)
            _check(r.status_code == 200, f"200 (got {r.status_code})")
            _check(
                "research" in r.json()["data"]["domains"],
                "research domain listed",
            )

            # ------------------------------------------------------------
            # Gate 4 — POST without token -> 403 refused
            # ------------------------------------------------------------
            print("[gate 4] POST without token -> 403")
            r = c.post(
                "/api/tools/brain_list_domains",
                json={},
                headers={"Origin": "http://localhost:4317"},
            )
            _check(r.status_code == 403, f"403 (got {r.status_code})")
            _check(r.json()["error"] == "refused", "error=refused")

            # ------------------------------------------------------------
            # Gate 5 — POST with evil origin -> 403 refused
            # ------------------------------------------------------------
            print("[gate 5] POST with evil origin -> 403")
            r = c.post(
                "/api/tools/brain_list_domains",
                json={},
                headers={"Origin": "https://evil.example", "X-Brain-Token": token},
            )
            _check(r.status_code == 403, f"403 (got {r.status_code})")
            _check(r.json()["error"] == "refused", "error=refused")

            # ------------------------------------------------------------
            # Gate 6 — brain_search returns scoped hits
            # ------------------------------------------------------------
            print("[gate 6] brain_search scope held")
            r = c.post(
                "/api/tools/brain_search",
                json={"query": "karpathy"},
                headers=headers_ok,
            )
            _check(r.status_code == 200, f"200 (got {r.status_code})")
            hits = r.json()["data"]["hits"]
            _check(len(hits) > 0, f"non-empty hits (got {len(hits)})")
            _check(
                all(h["path"].startswith("research/") for h in hits),
                "all hits inside research/",
            )

            # ------------------------------------------------------------
            # Gate 7 — brain_read_note returns body
            # ------------------------------------------------------------
            print("[gate 7] brain_read_note")
            r = c.post(
                "/api/tools/brain_read_note",
                json={"path": "research/notes/karpathy.md"},
                headers=headers_ok,
            )
            _check(r.status_code == 200, f"200 (got {r.status_code})")
            body = r.json()["data"]["body"]
            _check("LLM wiki pattern" in body, "expected body content returned")

            # ------------------------------------------------------------
            # Gate 8 — brain_propose_note stages a patch
            # ------------------------------------------------------------
            print("[gate 8] brain_propose_note stages patch")
            r = c.post(
                "/api/tools/brain_propose_note",
                json={
                    "path": "research/notes/demo.md",
                    "content": "# demo\n\nbody",
                    "reason": "plan 05 demo gate 8",
                },
                headers=headers_ok,
            )
            _check(r.status_code == 200, f"200 (got {r.status_code})")
            patch_id = r.json()["data"]["patch_id"]
            _check(bool(patch_id), "patch_id present")
            demo_path = vault / "research" / "notes" / "demo.md"
            _check(not demo_path.exists(), "target file NOT on disk yet")

            # ------------------------------------------------------------
            # Gate 9 — brain_apply_patch flushes to vault + returns undo_id
            # ------------------------------------------------------------
            print("[gate 9] brain_apply_patch")
            r = c.post(
                "/api/tools/brain_apply_patch",
                json={"patch_id": patch_id},
                headers=headers_ok,
            )
            _check(r.status_code == 200, f"200 (got {r.status_code})")
            data = r.json()["data"]
            _check(
                data.get("status") == "applied",
                f"status=applied (got {data.get('status')!r})",
            )
            _check("undo_id" in data and bool(data["undo_id"]), "undo_id present")
            _check(demo_path.exists(), "target file now on disk")

            # ------------------------------------------------------------
            # Gate 10 — scope guard refuses personal/ read
            # ------------------------------------------------------------
            print("[gate 10] brain_read_note on personal/ -> 403 scope")
            r = c.post(
                "/api/tools/brain_read_note",
                json={"path": "personal/notes/secret.md"},
                headers=headers_ok,
            )
            _check(r.status_code == 403, f"403 (got {r.status_code})")
            _check(r.json()["error"] == "scope", "error=scope")

            # ------------------------------------------------------------
            # Gate 11 — rate-limited brain_ingest -> 429 + Retry-After
            # ------------------------------------------------------------
            print("[gate 11] brain_ingest rate-limited -> 429 + Retry-After")
            original_limiter = app.state.ctx.tool_ctx.rate_limiter
            drained = RateLimiter(RateLimitConfig(patches_per_minute=1))
            drained.check("patches", cost=1)
            # Frozen dataclass — use object.__setattr__ to swap the limiter.
            object.__setattr__(app.state.ctx.tool_ctx, "rate_limiter", drained)
            try:
                r = c.post(
                    "/api/tools/brain_ingest",
                    json={"source": "text to ingest"},
                    headers=headers_ok,
                )
                _check(r.status_code == 429, f"429 (got {r.status_code})")
                _check(
                    "retry-after" in {k.lower() for k in r.headers}
                    and r.headers["retry-after"].isdigit(),
                    "Retry-After header present + numeric",
                )
                _check(
                    r.json()["detail"]["bucket"] == "patches",
                    f"detail.bucket=patches (got {r.json()['detail'].get('bucket')!r})",
                )
            finally:
                # Restore the live limiter so Gate 13's chat turn isn't
                # rate-limited by the drained bucket we just installed.
                object.__setattr__(app.state.ctx.tool_ctx, "rate_limiter", original_limiter)

            # ------------------------------------------------------------
            # Gates 12 + 13 — WS handshake + turn round-trip
            # ------------------------------------------------------------
            # Queue one FakeLLM response BEFORE opening the WS. ChatSession
            # tokenizes the response into per-char deltas, so a single
            # queued string yields multiple delta frames.
            app.state.ctx.tool_ctx.llm.queue("hello there")

            print("[gate 12] WS handshake (schema_version + thread_loaded)")
            with c.websocket_connect(
                f"/ws/chat/demo-thread?token={token}",
                headers=_LOOPBACK_WS_HEADERS,
            ) as ws:
                first = ws.receive_json()
                _check(first["type"] == "schema_version", "schema_version first")
                _check(first["version"] == "1", f"version=1 (got {first['version']!r})")
                second = ws.receive_json()
                _check(second["type"] == "thread_loaded", "thread_loaded second")
                _check(
                    second["turn_count"] == 0,
                    f"fresh thread turn_count=0 (got {second['turn_count']})",
                )
                _check(
                    second["thread_id"] == "demo-thread",
                    f"thread_id echoed (got {second['thread_id']!r})",
                )

                print("[gate 13] WS turn round-trip (turn_start -> delta+ -> turn_end)")
                ws.send_json({"type": "turn_start", "content": "hi", "mode": "ask"})
                types_seen: list[str] = []
                while True:
                    frame = ws.receive_json()
                    types_seen.append(frame["type"])
                    if frame["type"] in {"turn_end", "error"}:
                        break
                _check(
                    types_seen[0] == "turn_start",
                    f"turn_start first (got {types_seen[0]!r})",
                )
                _check(
                    "delta" in types_seen,
                    f"at least one delta (saw {types_seen})",
                )
                _check(
                    types_seen[-1] == "turn_end",
                    f"turn_end last (got {types_seen[-1]!r})",
                )

            # ------------------------------------------------------------
            # Gate 14 — reconnect same thread_id shows turn_count >= 1
            # ------------------------------------------------------------
            print("[gate 14] WS reconnect shows turn_count >= 1")
            with c.websocket_connect(
                f"/ws/chat/demo-thread?token={token}",
                headers=_LOOPBACK_WS_HEADERS,
            ) as ws:
                _check(
                    ws.receive_json()["type"] == "schema_version",
                    "schema_version on reconnect",
                )
                loaded = ws.receive_json()
                _check(loaded["type"] == "thread_loaded", "thread_loaded on reconnect")
                _check(
                    loaded["thread_id"] == "demo-thread",
                    f"thread_id echoed (got {loaded['thread_id']!r})",
                )
                _check(
                    loaded["turn_count"] >= 1,
                    f"turn_count >= 1 on reconnect (got {loaded['turn_count']})",
                )

        print()
        print("PLAN 05 DEMO OK")
        return 0


def main() -> int:
    return _run_demo()


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main"]

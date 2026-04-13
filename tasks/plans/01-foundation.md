# Plan 01 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the repo scaffolding and implement the pure-Python `brain_core` library — `config`, `vault` (scope_guard, frontmatter, wikilinks, index, log, VaultWriter, undo), `llm` (Provider protocol + FakeLLMProvider + Anthropic impl), and `cost` (ledger + budget) — with full unit test coverage green on Mac and Windows CI.

**Architecture:** A `uv` Python workspace rooted at the repo, with `brain_core` as the first package. `pnpm` workspace scaffolding is laid now so future JS packages slot in cleanly. All business logic lives in `brain_core`; no wrappers yet. Tests use `FakeLLMProvider` — zero live LLM calls in this plan. Cross-platform from line one: `pathlib`, `filelock`, no `shell=True`, no POSIX-only syscalls.

**Tech Stack:** Python 3.12 · `uv` · `pytest` + `pytest-cov` · `mypy` (strict) · `ruff` (lint + format) · `pydantic` v2 · `PyYAML` · `structlog` · `filelock` · `anthropic` SDK · GitHub Actions (Mac + Windows matrix)

**Demo gate:** `uv run pytest packages/brain_core --cov=brain_core` reports all tests passing with ≥85% coverage on Mac and Windows; `scripts/demo-plan-01.py` runs end-to-end without error and prints a success report.

**Owning subagent:** `brain-core-engineer` (with `brain-test-engineer` reviewing tests).

---

## File structure produced by this plan

```
cj-llm-kb/
├── .github/workflows/ci.yml
├── .gitignore
├── .python-version
├── .ruff.toml
├── pyproject.toml                   # uv workspace root
├── package.json                     # pnpm workspace root (empty apps list)
├── pnpm-workspace.yaml
├── README.md                        # stub, details come later
├── scripts/
│   └── demo-plan-01.py
└── packages/
    └── brain_core/
        ├── pyproject.toml
        ├── README.md
        ├── src/brain_core/
        │   ├── __init__.py
        │   ├── config/
        │   │   ├── __init__.py
        │   │   ├── schema.py        # pydantic Config model
        │   │   ├── loader.py        # layered resolution
        │   │   └── secrets.py       # secrets.env file handling
        │   ├── vault/
        │   │   ├── __init__.py
        │   │   ├── types.py         # Note, Patch, PatchSet, Frontmatter
        │   │   ├── paths.py         # scope_guard, path normalization
        │   │   ├── frontmatter.py   # YAML parse/serialize
        │   │   ├── wikilinks.py     # resolver
        │   │   ├── index.py         # index.md parse/write
        │   │   ├── log.py           # log.md append/parse
        │   │   ├── writer.py        # VaultWriter: atomic + filelock + undo
        │   │   └── undo.py          # undo log replay
        │   ├── llm/
        │   │   ├── __init__.py
        │   │   ├── types.py         # LLMRequest, LLMResponse, LLMStreamChunk
        │   │   ├── provider.py      # LLMProvider Protocol
        │   │   ├── fake.py          # FakeLLMProvider
        │   │   └── providers/
        │   │       ├── __init__.py
        │   │       └── anthropic.py # AnthropicProvider
        │   └── cost/
        │       ├── __init__.py
        │       ├── ledger.py        # costs.sqlite writer + query
        │       └── budget.py        # enforcement + pre-call estimation
        └── tests/
            ├── __init__.py
            ├── conftest.py          # ephemeral_vault fixture, fake_llm fixture
            ├── config/
            │   ├── test_schema.py
            │   ├── test_loader.py
            │   └── test_secrets.py
            ├── vault/
            │   ├── test_paths.py
            │   ├── test_frontmatter.py
            │   ├── test_wikilinks.py
            │   ├── test_index.py
            │   ├── test_log.py
            │   ├── test_writer.py
            │   └── test_undo.py
            ├── llm/
            │   ├── test_provider_protocol.py
            │   ├── test_fake.py
            │   └── test_anthropic.py
            ├── cost/
            │   ├── test_ledger.py
            │   └── test_budget.py
            └── test_cross_platform.py
```

---

## Task 1 — Monorepo scaffolding (uv + pnpm workspaces)

**Files:**
- Create: `pyproject.toml`, `package.json`, `pnpm-workspace.yaml`, `.gitignore`, `.python-version`, `.ruff.toml`, `README.md`

- [ ] **Step 1.1: Create the root `pyproject.toml` (uv workspace)**

```toml
[project]
name = "brain"
version = "0.1.0"
description = "LLM-maintained personal knowledge base"
requires-python = ">=3.12"
readme = "README.md"

[tool.uv]
package = false

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
brain_core = { workspace = true }

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-asyncio>=0.23",
    "mypy>=1.11",
    "ruff>=0.6",
    "filelock>=3.15",
]
```

- [ ] **Step 1.2: Create `.python-version`**

```
3.12
```

- [ ] **Step 1.3: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/

# Node
node_modules/
.next/
out/

# Editors
.vscode/
.idea/
*.swp
.DS_Store

# Vault secrets must NEVER land in the repo (defense in depth;
# the real vault is at ~/Documents/brain/, not here)
**/.brain/secrets.env
**/.brain/logs/
**/.brain/run/
**/.brain/costs.sqlite
**/.brain/state.sqlite
```

- [ ] **Step 1.4: Create `.ruff.toml`**

```toml
target-version = "py312"
line-length = 100

[lint]
select = ["E", "F", "I", "N", "UP", "B", "C4", "SIM", "RUF"]
ignore = ["E501"]  # line length handled by formatter

[format]
quote-style = "double"
```

- [ ] **Step 1.5: Create `pnpm-workspace.yaml`**

```yaml
packages:
  - "apps/*"
  - "packages/js/*"
```

- [ ] **Step 1.6: Create root `package.json`**

```json
{
  "name": "brain-monorepo",
  "private": true,
  "version": "0.1.0",
  "packageManager": "pnpm@9.12.0"
}
```

- [ ] **Step 1.7: Create `README.md` stub**

```markdown
# brain

LLM-maintained personal knowledge base. See [`docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md`](docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md) for the full design.

## Status

Early development. Nothing user-facing yet — see [`tasks/todo.md`](tasks/todo.md).
```

- [ ] **Step 1.8: Run `uv sync`**

Run: `uv sync`
Expected: `Resolved N packages` and `.venv/` created at the repo root. No errors.

- [ ] **Step 1.9: Commit**

```bash
git init -b main
git add .
git commit -m "chore: monorepo scaffolding (uv + pnpm workspaces)"
```

---

## Task 2 — `brain_core` package skeleton

**Files:**
- Create: `packages/brain_core/pyproject.toml`, `packages/brain_core/README.md`, `packages/brain_core/src/brain_core/__init__.py`, `packages/brain_core/tests/__init__.py`, `packages/brain_core/tests/conftest.py`

- [ ] **Step 2.1: Create `packages/brain_core/pyproject.toml`**

```toml
[project]
name = "brain_core"
version = "0.1.0"
description = "Pure-Python core library for brain. No web/MCP deps."
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.8",
    "pyyaml>=6.0",
    "structlog>=24.4",
    "filelock>=3.15",
    "anthropic>=0.40",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/brain_core"]

[tool.mypy]
python_version = "3.12"
strict = true
packages = ["brain_core"]
mypy_path = "src"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2.2: Create `packages/brain_core/README.md`**

```markdown
# brain_core

Pure-Python core for `brain`. Zero web or MCP dependencies. Owned by the `brain-core-engineer` subagent.
```

- [ ] **Step 2.3: Create `packages/brain_core/src/brain_core/__init__.py`**

```python
"""brain_core — pure Python core library for brain."""

__version__ = "0.1.0"
```

- [ ] **Step 2.4: Create `packages/brain_core/tests/__init__.py`**

Empty file.

- [ ] **Step 2.5: Create `packages/brain_core/tests/conftest.py`**

```python
"""Shared pytest fixtures for brain_core tests."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Iterator

import pytest


@pytest.fixture
def ephemeral_vault(tmp_path: Path) -> Iterator[Path]:
    """Create a minimal, valid brain vault inside tmp_path and yield its root.

    Layout:
        <tmp>/brain/
            .brain/
            research/  work/  personal/   # each with sources/entities/concepts/synthesis + index.md + log.md
            chats/{research,work,personal}/
            raw/{inbox,failed,archive}/
            BRAIN.md
    """
    root = tmp_path / "brain"
    root.mkdir()
    (root / ".brain").mkdir()
    for domain in ("research", "work", "personal"):
        d = root / domain
        d.mkdir()
        for sub in ("sources", "entities", "concepts", "synthesis"):
            (d / sub).mkdir()
        (d / "index.md").write_text(
            f"# {domain} — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
            encoding="utf-8",
        )
        (d / "log.md").write_text(f"# {domain} — log\n", encoding="utf-8")
        (root / "chats" / domain).mkdir(parents=True)
    for sub in ("inbox", "failed", "archive"):
        (root / "raw" / sub).mkdir(parents=True)
    (root / "BRAIN.md").write_text("# BRAIN\n\nDefault schema doc.\n", encoding="utf-8")
    yield root
```

- [ ] **Step 2.6: Run `uv sync` and collect-only pytest**

Run: `uv sync`
Run: `uv run pytest packages/brain_core --collect-only`
Expected: `collected 0 items` and no errors.

- [ ] **Step 2.7: Commit**

```bash
git add packages/brain_core
git commit -m "chore(brain_core): package skeleton with ephemeral_vault fixture"
```

---

## Task 3 — CI workflow (Mac + Windows matrix)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 3.1: Write the workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [macos-14, windows-2022]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "0.4.*"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Lint
        run: uv run ruff check .

      - name: Type-check brain_core
        run: uv run mypy packages/brain_core/src

      - name: Test
        run: uv run pytest packages/brain_core --cov=brain_core --cov-report=term-missing
```

- [ ] **Step 3.2: Validate the YAML locally**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: no output, exit 0.

- [ ] **Step 3.3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: Mac + Windows matrix with lint, type-check, test"
```

---

## Task 4 — `brain_core.config.schema` (pydantic Config model)

**Files:**
- Create: `packages/brain_core/src/brain_core/config/__init__.py`, `packages/brain_core/src/brain_core/config/schema.py`, `packages/brain_core/tests/config/__init__.py`, `packages/brain_core/tests/config/test_schema.py`

- [ ] **Step 4.1: Write the failing test**

```python
# packages/brain_core/tests/config/test_schema.py
from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.config.schema import Config, LLMConfig


def test_default_config_has_expected_defaults() -> None:
    c = Config()
    assert c.vault_path == Path.home() / "Documents" / "brain"
    assert c.active_domain == "research"
    assert c.autonomous_mode is False
    assert c.llm.provider == "anthropic"
    assert c.llm.default_model == "claude-sonnet-4-6"
    assert c.budget.daily_usd == 5.0
    assert c.budget.monthly_usd == 80.0
    assert c.web_port == 4317


def test_config_rejects_unknown_domain() -> None:
    with pytest.raises(ValueError):
        Config(active_domain="marketing")  # not in allowed set


def test_llm_config_model_change_roundtrips() -> None:
    cfg = LLMConfig(default_model="claude-haiku-4-5-20251001")
    assert cfg.default_model == "claude-haiku-4-5-20251001"
```

- [ ] **Step 4.2: Run the test; verify it fails**

Run: `uv run pytest packages/brain_core/tests/config/test_schema.py -v`
Expected: **FAIL** — `ModuleNotFoundError: No module named 'brain_core.config'`.

- [ ] **Step 4.3: Create `packages/brain_core/src/brain_core/config/__init__.py`**

```python
"""brain_core.config — layered config resolution and secrets handling."""

from brain_core.config.schema import Config, LLMConfig, BudgetConfig

__all__ = ["Config", "LLMConfig", "BudgetConfig"]
```

- [ ] **Step 4.4: Implement `packages/brain_core/src/brain_core/config/schema.py`**

```python
"""Typed Config model. Source of truth for all user-configurable behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Domain = Literal["research", "work", "personal"]
ALLOWED_DOMAINS: tuple[Domain, ...] = ("research", "work", "personal")


class LLMConfig(BaseModel):
    provider: Literal["anthropic"] = "anthropic"
    default_model: str = "claude-sonnet-4-6"
    classify_model: str = "claude-haiku-4-5-20251001"
    max_output_tokens: int = 4096
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)


class BudgetConfig(BaseModel):
    daily_usd: float = Field(default=5.0, ge=0.0)
    monthly_usd: float = Field(default=80.0, ge=0.0)
    alert_threshold_pct: int = Field(default=80, ge=0, le=100)


class Config(BaseModel):
    vault_path: Path = Field(default_factory=lambda: Path.home() / "Documents" / "brain")
    active_domain: Domain = "research"
    autonomous_mode: bool = False
    llm: LLMConfig = Field(default_factory=LLMConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    web_port: int = Field(default=4317, ge=1024, le=65535)
    log_llm_payloads: bool = False

    @field_validator("active_domain")
    @classmethod
    def _check_domain(cls, v: str) -> str:
        if v not in ALLOWED_DOMAINS:
            raise ValueError(f"active_domain must be one of {ALLOWED_DOMAINS}, got {v!r}")
        return v
```

- [ ] **Step 4.5: Run the test; verify it passes**

Run: `uv run pytest packages/brain_core/tests/config/test_schema.py -v`
Expected: **3 passed**.

- [ ] **Step 4.6: Commit**

```bash
git add packages/brain_core/src/brain_core/config packages/brain_core/tests/config
git commit -m "feat(brain_core): config schema with pydantic Config model"
```

---

## Task 5 — `brain_core.config.loader` (layered resolution)

**Files:**
- Create: `packages/brain_core/src/brain_core/config/loader.py`, `packages/brain_core/tests/config/test_loader.py`

**Resolution order** (highest wins): CLI overrides → environment variables → `config.json` → defaults.

- [ ] **Step 5.1: Write failing tests**

```python
# packages/brain_core/tests/config/test_loader.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain_core.config.loader import load_config


def test_defaults_when_no_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_VAULT", raising=False)
    cfg = load_config(config_file=None, env=dict(), cli_overrides=dict())
    assert cfg.active_domain == "research"
    assert cfg.web_port == 4317


def test_env_overrides_defaults() -> None:
    cfg = load_config(config_file=None, env={"BRAIN_WEB_PORT": "5000"}, cli_overrides=dict())
    assert cfg.web_port == 5000


def test_config_file_beats_defaults_but_loses_to_env(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"web_port": 6000, "active_domain": "work"}), encoding="utf-8")
    cfg = load_config(config_file=cfg_path, env={"BRAIN_WEB_PORT": "7000"}, cli_overrides=dict())
    assert cfg.active_domain == "work"   # from file
    assert cfg.web_port == 7000          # env wins


def test_cli_overrides_beat_everything(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"web_port": 6000}), encoding="utf-8")
    cfg = load_config(
        config_file=cfg_path,
        env={"BRAIN_WEB_PORT": "7000"},
        cli_overrides={"web_port": 8000},
    )
    assert cfg.web_port == 8000


def test_invalid_config_file_raises(tmp_path: Path) -> None:
    bad = tmp_path / "config.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="config file"):
        load_config(config_file=bad, env=dict(), cli_overrides=dict())
```

- [ ] **Step 5.2: Run the tests; verify failure**

Run: `uv run pytest packages/brain_core/tests/config/test_loader.py -v`
Expected: **FAIL** — `ImportError`.

- [ ] **Step 5.3: Implement `loader.py`**

```python
"""Layered config resolution: defaults → config.json → env → CLI overrides."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from brain_core.config.schema import Config

ENV_MAP: dict[str, str] = {
    "BRAIN_VAULT": "vault_path",
    "BRAIN_ACTIVE_DOMAIN": "active_domain",
    "BRAIN_AUTONOMOUS": "autonomous_mode",
    "BRAIN_WEB_PORT": "web_port",
    "BRAIN_LOG_LLM_PAYLOADS": "log_llm_payloads",
}


def load_config(
    *,
    config_file: Path | None,
    env: Mapping[str, str],
    cli_overrides: Mapping[str, Any],
) -> Config:
    """Build a Config by merging layers; later layers override earlier ones."""
    data: dict[str, Any] = {}

    if config_file is not None:
        try:
            data.update(json.loads(config_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise ValueError(f"config file {config_file} is not valid JSON: {exc}") from exc

    for env_key, field in ENV_MAP.items():
        if env_key in env:
            data[field] = _coerce(field, env[env_key])

    data.update(cli_overrides)
    return Config(**data)


def _coerce(field: str, raw: str) -> Any:
    if field in {"web_port"}:
        return int(raw)
    if field in {"autonomous_mode", "log_llm_payloads"}:
        return raw.lower() in {"1", "true", "yes", "on"}
    if field == "vault_path":
        return Path(raw).expanduser()
    return raw
```

- [ ] **Step 5.4: Run tests; verify passing**

Run: `uv run pytest packages/brain_core/tests/config/test_loader.py -v`
Expected: **5 passed**.

- [ ] **Step 5.5: Commit**

```bash
git add packages/brain_core/src/brain_core/config/loader.py packages/brain_core/tests/config/test_loader.py
git commit -m "feat(brain_core): layered config loader (defaults→file→env→cli)"
```

---

## Task 6 — `brain_core.config.secrets` (secrets.env handling)

**Files:**
- Create: `packages/brain_core/src/brain_core/config/secrets.py`, `packages/brain_core/tests/config/test_secrets.py`

- [ ] **Step 6.1: Write failing tests**

```python
# packages/brain_core/tests/config/test_secrets.py
from __future__ import annotations

import os
import sys
import stat
from pathlib import Path

import pytest

from brain_core.config.secrets import SecretsStore, SecretNotFoundError


def test_read_existing_secret(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    f.write_text("ANTHROPIC_API_KEY=sk-test-123\n", encoding="utf-8")
    store = SecretsStore(f)
    assert store.get("ANTHROPIC_API_KEY") == "sk-test-123"


def test_missing_secret_raises(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    f.write_text("", encoding="utf-8")
    with pytest.raises(SecretNotFoundError):
        SecretsStore(f).get("NOPE")


def test_set_and_persist(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    store = SecretsStore(f)
    store.set("ANTHROPIC_API_KEY", "sk-abc")
    assert f.exists()
    assert SecretsStore(f).get("ANTHROPIC_API_KEY") == "sk-abc"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only permission check")
def test_set_creates_mode_600(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    SecretsStore(f).set("K", "V")
    mode = stat.S_IMODE(os.stat(f).st_mode)
    assert mode == 0o600


def test_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    f.write_text("# comment\n\nA=1\nB=2\n# B=99\n", encoding="utf-8")
    store = SecretsStore(f)
    assert store.get("A") == "1"
    assert store.get("B") == "2"


def test_values_with_equals_sign(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    f.write_text("TOKEN=abc=def=ghi\n", encoding="utf-8")
    assert SecretsStore(f).get("TOKEN") == "abc=def=ghi"
```

- [ ] **Step 6.2: Run tests; verify failure**

Run: `uv run pytest packages/brain_core/tests/config/test_secrets.py -v`
Expected: **FAIL** — `ImportError`.

- [ ] **Step 6.3: Implement `secrets.py`**

```python
"""Secrets file handling. File-based only; never round-tripped via config.json."""

from __future__ import annotations

import os
import sys
from pathlib import Path


class SecretNotFoundError(KeyError):
    """Raised when a requested secret is not present."""


class SecretsStore:
    """Minimal .env-style key/value store at a fixed path.

    Supports `KEY=VALUE` lines (values may contain `=`), blank lines, and `#` comments.
    On POSIX, writes are chmod 600. On Windows, ACL restriction is handled by caller
    or by the default user profile permissions.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, str] = {}
        if path.exists():
            self._load()

    def _load(self) -> None:
        for raw_line in self._path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            self._data[key.strip()] = value

    def get(self, key: str) -> str:
        try:
            return self._data[key]
        except KeyError as exc:
            raise SecretNotFoundError(key) from exc

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{k}={v}" for k, v in sorted(self._data.items())]
        self._path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if sys.platform != "win32":
            os.chmod(self._path, 0o600)

    def has(self, key: str) -> bool:
        return key in self._data
```

- [ ] **Step 6.4: Run tests; verify passing**

Run: `uv run pytest packages/brain_core/tests/config/test_secrets.py -v`
Expected: **6 passed** (5 on Windows, skipping the chmod test).

- [ ] **Step 6.5: Commit**

```bash
git add packages/brain_core/src/brain_core/config/secrets.py packages/brain_core/tests/config/test_secrets.py
git commit -m "feat(brain_core): secrets.env store with 600-mode writes on POSIX"
```

---

## Task 7 — `brain_core.vault.paths` (scope_guard)

**Files:**
- Create: `packages/brain_core/src/brain_core/vault/__init__.py`, `packages/brain_core/src/brain_core/vault/paths.py`, `packages/brain_core/tests/vault/__init__.py`, `packages/brain_core/tests/vault/test_paths.py`

`scope_guard` is the single function every vault read/write must pass through. It is the domain firewall.

- [ ] **Step 7.1: Write failing tests**

```python
# packages/brain_core/tests/vault/test_paths.py
from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.vault.paths import ScopeError, scope_guard


def test_allows_path_inside_allowed_domain(ephemeral_vault: Path) -> None:
    p = ephemeral_vault / "research" / "sources" / "note.md"
    result = scope_guard(p, vault_root=ephemeral_vault, allowed_domains=("research",))
    assert result == p.resolve()


def test_rejects_path_in_disallowed_domain(ephemeral_vault: Path) -> None:
    p = ephemeral_vault / "personal" / "sources" / "note.md"
    with pytest.raises(ScopeError, match="not in allowed"):
        scope_guard(p, vault_root=ephemeral_vault, allowed_domains=("research",))


def test_rejects_dotdot_escape(ephemeral_vault: Path) -> None:
    p = ephemeral_vault / "research" / ".." / ".." / "etc" / "passwd"
    with pytest.raises(ScopeError):
        scope_guard(p, vault_root=ephemeral_vault, allowed_domains=("research",))


def test_rejects_absolute_outside_vault(ephemeral_vault: Path, tmp_path: Path) -> None:
    p = tmp_path / "outside.md"
    p.write_text("x", encoding="utf-8")
    with pytest.raises(ScopeError):
        scope_guard(p, vault_root=ephemeral_vault, allowed_domains=("research",))


def test_allows_cross_domain_when_all_listed(ephemeral_vault: Path) -> None:
    p = ephemeral_vault / "work" / "sources" / "n.md"
    scope_guard(p, vault_root=ephemeral_vault, allowed_domains=("research", "work", "personal"))


def test_personal_never_matches_wildcard_research_only(ephemeral_vault: Path) -> None:
    p = ephemeral_vault / "personal" / "concepts" / "private.md"
    with pytest.raises(ScopeError):
        scope_guard(p, vault_root=ephemeral_vault, allowed_domains=("research", "work"))
```

- [ ] **Step 7.2: Run tests; verify failure**

Run: `uv run pytest packages/brain_core/tests/vault/test_paths.py -v`
Expected: **FAIL** — import error.

- [ ] **Step 7.3: Create `vault/__init__.py`**

```python
"""brain_core.vault — read/write, scope_guard, frontmatter, wikilinks, index, log, VaultWriter."""
```

- [ ] **Step 7.4: Implement `vault/paths.py`**

```python
"""Path normalization and scope enforcement. The domain firewall lives here."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


class ScopeError(PermissionError):
    """Raised when a path is outside the allowed domain scope."""


def scope_guard(
    path: Path,
    *,
    vault_root: Path,
    allowed_domains: Iterable[str],
) -> Path:
    """Return the resolved path if it is inside an allowed domain, else raise ScopeError.

    Enforcement:
    - Resolves symlinks and `..` segments.
    - Requires the resolved path to be a descendant of vault_root.
    - Requires the first path component under vault_root to be in allowed_domains.
    """
    vault_root = vault_root.resolve()
    resolved = path.resolve()

    try:
        rel = resolved.relative_to(vault_root)
    except ValueError as exc:
        raise ScopeError(f"{path} is not inside vault {vault_root}") from exc

    if not rel.parts:
        raise ScopeError(f"{path} resolves to vault root, not a domain")

    domain = rel.parts[0]
    allowed = tuple(allowed_domains)
    if domain not in allowed:
        raise ScopeError(f"{path} domain {domain!r} not in allowed {allowed}")

    return resolved
```

- [ ] **Step 7.5: Run tests; verify passing**

Run: `uv run pytest packages/brain_core/tests/vault/test_paths.py -v`
Expected: **6 passed**.

- [ ] **Step 7.6: Commit**

```bash
git add packages/brain_core/src/brain_core/vault/__init__.py packages/brain_core/src/brain_core/vault/paths.py packages/brain_core/tests/vault
git commit -m "feat(brain_core): scope_guard domain firewall with full test coverage"
```

---

## Task 8 — `brain_core.vault.frontmatter` (YAML parse/serialize)

**Files:**
- Create: `packages/brain_core/src/brain_core/vault/frontmatter.py`, `packages/brain_core/tests/vault/test_frontmatter.py`

- [ ] **Step 8.1: Write failing tests**

```python
# packages/brain_core/tests/vault/test_frontmatter.py
from __future__ import annotations

import pytest

from brain_core.vault.frontmatter import (
    FrontmatterError,
    parse_frontmatter,
    serialize_with_frontmatter,
)


def test_parse_roundtrip() -> None:
    content = (
        "---\n"
        "title: Example\n"
        "domain: research\n"
        "tags:\n"
        "  - foo\n"
        "  - bar\n"
        "---\n"
        "\n"
        "Body text here.\n"
    )
    data, body = parse_frontmatter(content)
    assert data == {"title": "Example", "domain": "research", "tags": ["foo", "bar"]}
    assert body == "Body text here.\n"


def test_parse_no_frontmatter_raises() -> None:
    with pytest.raises(FrontmatterError, match="missing"):
        parse_frontmatter("Just body, no frontmatter.\n")


def test_parse_unterminated_raises() -> None:
    with pytest.raises(FrontmatterError, match="unterminated"):
        parse_frontmatter("---\ntitle: x\nno-close-marker\n")


def test_parse_invalid_yaml_raises() -> None:
    with pytest.raises(FrontmatterError, match="invalid YAML"):
        parse_frontmatter("---\n: : bad\n---\nbody\n")


def test_serialize_produces_parseable_output() -> None:
    out = serialize_with_frontmatter(
        {"title": "X", "domain": "work"},
        body="Hello.\n",
    )
    data, body = parse_frontmatter(out)
    assert data["title"] == "X"
    assert data["domain"] == "work"
    assert body == "Hello.\n"


def test_serialize_preserves_key_order_stable() -> None:
    out = serialize_with_frontmatter(
        {"title": "a", "domain": "b", "type": "c"}, body=""
    )
    assert out.splitlines()[:5] == ["---", "title: a", "domain: b", "type: c", "---"]
```

- [ ] **Step 8.2: Run tests; verify failure**

Run: `uv run pytest packages/brain_core/tests/vault/test_frontmatter.py -v`
Expected: **FAIL** — import error.

- [ ] **Step 8.3: Implement `vault/frontmatter.py`**

```python
"""YAML frontmatter parse + serialize. Stable key order for diff-friendliness."""

from __future__ import annotations

from typing import Any, Mapping

import yaml


class FrontmatterError(ValueError):
    """Raised for any frontmatter parsing failure."""


_FENCE = "---"


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split frontmatter from body. Raises if no frontmatter or malformed."""
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != _FENCE:
        raise FrontmatterError("missing frontmatter fence at top of file")

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == _FENCE:
            end_idx = i
            break
    if end_idx is None:
        raise FrontmatterError("unterminated frontmatter — no closing ---")

    yaml_src = "".join(lines[1:end_idx])
    try:
        data = yaml.safe_load(yaml_src) or {}
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"invalid YAML in frontmatter: {exc}") from exc
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")

    body = "".join(lines[end_idx + 1 :])
    if body.startswith("\n"):
        body = body[1:]
    return data, body


def serialize_with_frontmatter(data: Mapping[str, Any], *, body: str) -> str:
    """Serialize a note with frontmatter. Key order is preserved from the input mapping."""
    yaml_text = yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=True).rstrip("\n")
    return f"{_FENCE}\n{yaml_text}\n{_FENCE}\n\n{body}"
```

- [ ] **Step 8.4: Run tests; verify passing**

Run: `uv run pytest packages/brain_core/tests/vault/test_frontmatter.py -v`
Expected: **6 passed**.

- [ ] **Step 8.5: Commit**

```bash
git add packages/brain_core/src/brain_core/vault/frontmatter.py packages/brain_core/tests/vault/test_frontmatter.py
git commit -m "feat(brain_core): YAML frontmatter parse/serialize with stable key order"
```

---

## Task 9 — `brain_core.vault.wikilinks` (resolver)

**Files:**
- Create: `packages/brain_core/src/brain_core/vault/wikilinks.py`, `packages/brain_core/tests/vault/test_wikilinks.py`

- [ ] **Step 9.1: Write failing tests**

```python
# packages/brain_core/tests/vault/test_wikilinks.py
from __future__ import annotations

from pathlib import Path

from brain_core.vault.wikilinks import (
    BrokenLink,
    Resolved,
    extract_wikilinks,
    resolve_wikilinks,
)


def test_extract_basic() -> None:
    body = "See [[alpha]] and [[beta|the beta note]] and [[gamma]]."
    assert extract_wikilinks(body) == ["alpha", "beta", "gamma"]


def test_extract_ignores_code_fences() -> None:
    body = "```\n[[notalink]]\n```\nReal: [[yes]]"
    assert extract_wikilinks(body) == ["yes"]


def test_resolve_unique_target(ephemeral_vault: Path) -> None:
    (ephemeral_vault / "research" / "concepts" / "alpha.md").write_text("x", encoding="utf-8")
    out = resolve_wikilinks(
        ["alpha"],
        vault_root=ephemeral_vault,
        active_domain="research",
    )
    assert isinstance(out["alpha"], Resolved)
    assert out["alpha"].path.name == "alpha.md"


def test_resolve_broken(ephemeral_vault: Path) -> None:
    out = resolve_wikilinks(["ghost"], vault_root=ephemeral_vault, active_domain="research")
    assert isinstance(out["ghost"], BrokenLink)


def test_resolve_collision_prefers_active_domain(ephemeral_vault: Path) -> None:
    (ephemeral_vault / "research" / "concepts" / "dup.md").write_text("r", encoding="utf-8")
    (ephemeral_vault / "work" / "concepts" / "dup.md").write_text("w", encoding="utf-8")
    out = resolve_wikilinks(["dup"], vault_root=ephemeral_vault, active_domain="work")
    assert out["dup"].path.parts[-3] == "work"  # type: ignore[union-attr]
```

- [ ] **Step 9.2: Run; verify failure**

Run: `uv run pytest packages/brain_core/tests/vault/test_wikilinks.py -v`
Expected: **FAIL**.

- [ ] **Step 9.3: Implement `vault/wikilinks.py`**

```python
"""Wikilink extraction and resolution. Obsidian-compatible [[target]] syntax."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Matches [[target]] or [[target|alias]] — captures the target portion only.
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)


@dataclass(frozen=True)
class Resolved:
    target: str
    path: Path


@dataclass(frozen=True)
class BrokenLink:
    target: str


Resolution = Resolved | BrokenLink


def extract_wikilinks(body: str) -> list[str]:
    """Return all wikilink targets in body, skipping fenced code blocks."""
    stripped = _CODE_FENCE.sub("", body)
    return [m.group(1).strip() for m in _WIKILINK.finditer(stripped)]


def resolve_wikilinks(
    targets: list[str],
    *,
    vault_root: Path,
    active_domain: str,
) -> dict[str, Resolution]:
    """Resolve each target to a concrete .md path, preferring the active domain on collision."""
    out: dict[str, Resolution] = {}
    for target in targets:
        filename = f"{target}.md"
        # prefer active domain
        matches: list[Path] = []
        for p in (vault_root / active_domain).rglob(filename):
            matches.append(p)
        if not matches:
            for domain_dir in vault_root.iterdir():
                if not domain_dir.is_dir() or domain_dir.name.startswith("."):
                    continue
                if domain_dir.name == active_domain:
                    continue
                matches.extend(domain_dir.rglob(filename))
        out[target] = Resolved(target=target, path=matches[0]) if matches else BrokenLink(target=target)
    return out
```

- [ ] **Step 9.4: Run; verify passing**

Run: `uv run pytest packages/brain_core/tests/vault/test_wikilinks.py -v`
Expected: **5 passed**.

- [ ] **Step 9.5: Commit**

```bash
git add packages/brain_core/src/brain_core/vault/wikilinks.py packages/brain_core/tests/vault/test_wikilinks.py
git commit -m "feat(brain_core): wikilink extraction and collision-aware resolver"
```

---

## Task 10 — `brain_core.vault.index` (index.md parse/write)

**Files:**
- Create: `packages/brain_core/src/brain_core/vault/index.py`, `packages/brain_core/tests/vault/test_index.py`

- [ ] **Step 10.1: Write failing tests**

```python
# packages/brain_core/tests/vault/test_index.py
from __future__ import annotations

from pathlib import Path

from brain_core.vault.index import IndexFile, IndexEntry


def test_parse_and_roundtrip(ephemeral_vault: Path) -> None:
    idx_path = ephemeral_vault / "research" / "index.md"
    idx_path.write_text(
        "# research — index\n\n"
        "## Sources\n"
        "- [[alpha]] — first source\n"
        "- [[beta]] — second\n\n"
        "## Entities\n\n"
        "## Concepts\n"
        "- [[knowledge-compilation]] — core concept\n\n"
        "## Synthesis\n",
        encoding="utf-8",
    )
    idx = IndexFile.load(idx_path)
    assert [e.target for e in idx.sections["Sources"]] == ["alpha", "beta"]
    assert idx.sections["Concepts"][0].summary == "core concept"

    idx.add_entry("Sources", IndexEntry(target="gamma", summary="third"))
    idx.save()

    reloaded = IndexFile.load(idx_path)
    assert [e.target for e in reloaded.sections["Sources"]] == ["alpha", "beta", "gamma"]


def test_remove_entry(ephemeral_vault: Path) -> None:
    idx_path = ephemeral_vault / "research" / "index.md"
    idx_path.write_text(
        "# research — index\n\n## Sources\n- [[alpha]] — x\n- [[beta]] — y\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
        encoding="utf-8",
    )
    idx = IndexFile.load(idx_path)
    idx.remove_entry("Sources", target="alpha")
    idx.save()

    reloaded = IndexFile.load(idx_path)
    assert [e.target for e in reloaded.sections["Sources"]] == ["beta"]
```

- [ ] **Step 10.2: Run; verify failure**

Run: `uv run pytest packages/brain_core/tests/vault/test_index.py -v`
Expected: **FAIL**.

- [ ] **Step 10.3: Implement `vault/index.py`**

```python
"""index.md parser/writer. Four-section layout: Sources, Entities, Concepts, Synthesis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SECTIONS: tuple[str, ...] = ("Sources", "Entities", "Concepts", "Synthesis")
_ENTRY_RE = re.compile(r"^- \[\[([^\]]+)\]\]\s*—\s*(.*)$")


@dataclass(frozen=True)
class IndexEntry:
    target: str
    summary: str

    def render(self) -> str:
        return f"- [[{self.target}]] — {self.summary}"


@dataclass
class IndexFile:
    path: Path
    title: str
    sections: dict[str, list[IndexEntry]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "IndexFile":
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("#") else path.stem
        sections: dict[str, list[IndexEntry]] = {s: [] for s in SECTIONS}
        current: str | None = None
        for line in lines[1:]:
            if line.startswith("## "):
                current = line[3:].strip()
                sections.setdefault(current, [])
                continue
            if current is None:
                continue
            m = _ENTRY_RE.match(line.rstrip())
            if m:
                sections[current].append(IndexEntry(target=m.group(1), summary=m.group(2)))
        return cls(path=path, title=title, sections=sections)

    def add_entry(self, section: str, entry: IndexEntry) -> None:
        self.sections.setdefault(section, []).append(entry)

    def remove_entry(self, section: str, *, target: str) -> None:
        self.sections[section] = [e for e in self.sections.get(section, []) if e.target != target]

    def render(self) -> str:
        parts = [f"# {self.title}", ""]
        for section in SECTIONS:
            parts.append(f"## {section}")
            entries = self.sections.get(section, [])
            for e in entries:
                parts.append(e.render())
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"

    def save(self) -> None:
        self.path.write_text(self.render(), encoding="utf-8")
```

- [ ] **Step 10.4: Run; verify passing**

Run: `uv run pytest packages/brain_core/tests/vault/test_index.py -v`
Expected: **2 passed**.

- [ ] **Step 10.5: Commit**

```bash
git add packages/brain_core/src/brain_core/vault/index.py packages/brain_core/tests/vault/test_index.py
git commit -m "feat(brain_core): index.md parser/writer with 4-section layout"
```

---

## Task 11 — `brain_core.vault.log` (append-only log)

**Files:**
- Create: `packages/brain_core/src/brain_core/vault/log.py`, `packages/brain_core/tests/vault/test_log.py`

- [ ] **Step 11.1: Write failing tests**

```python
# packages/brain_core/tests/vault/test_log.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from brain_core.vault.log import LogFile, LogEntry


def test_append_and_parse(ephemeral_vault: Path) -> None:
    log_path = ephemeral_vault / "research" / "log.md"
    lf = LogFile(log_path)
    ts = datetime(2026, 4, 13, 14, 22, tzinfo=timezone.utc)
    lf.append(LogEntry(timestamp=ts, op="ingest", summary="source | [[alpha]] | touched: index, concepts/x"))
    lf.append(LogEntry(timestamp=ts, op="query", summary='"what is x" | used: alpha'))

    entries = LogFile(log_path).read_all()
    assert len(entries) == 2
    assert entries[0].op == "ingest"
    assert "alpha" in entries[0].summary
    assert entries[1].op == "query"


def test_read_last_n(ephemeral_vault: Path) -> None:
    log_path = ephemeral_vault / "research" / "log.md"
    lf = LogFile(log_path)
    for i in range(10):
        lf.append(LogEntry(timestamp=datetime(2026, 4, 13, tzinfo=timezone.utc), op="ingest", summary=f"n{i}"))
    tail = LogFile(log_path).read_last(3)
    assert [e.summary for e in tail] == ["n7", "n8", "n9"]
```

- [ ] **Step 11.2: Run; verify failure**

Run: `uv run pytest packages/brain_core/tests/vault/test_log.py -v`

- [ ] **Step 11.3: Implement `vault/log.py`**

```python
"""Append-only per-domain log.md. Entry format: ## [YYYY-MM-DD HH:MM] op | summary"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_HEADING = re.compile(r"^##\s*\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s*(\S+)\s*\|\s*(.*)$")


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime
    op: str
    summary: str

    def render(self) -> str:
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M")
        return f"## [{ts}] {self.op} | {self.summary}"


class LogFile:
    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.exists():
            path.write_text(f"# {path.parent.name} — log\n", encoding="utf-8")

    def append(self, entry: LogEntry) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write("\n" + entry.render() + "\n")

    def read_all(self) -> list[LogEntry]:
        out: list[LogEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            m = _HEADING.match(line)
            if m:
                ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                out.append(LogEntry(timestamp=ts, op=m.group(2), summary=m.group(3)))
        return out

    def read_last(self, n: int) -> list[LogEntry]:
        return self.read_all()[-n:]
```

- [ ] **Step 11.4: Run; verify passing**

Run: `uv run pytest packages/brain_core/tests/vault/test_log.py -v`
Expected: **2 passed**.

- [ ] **Step 11.5: Commit**

```bash
git add packages/brain_core/src/brain_core/vault/log.py packages/brain_core/tests/vault/test_log.py
git commit -m "feat(brain_core): append-only log.md with parseable entry format"
```

---

## Task 12 — `brain_core.vault.types` (Patch, PatchSet, Note)

**Files:**
- Create: `packages/brain_core/src/brain_core/vault/types.py`

No tests — these are type definitions used by other modules. Covered transitively by Task 13+ tests.

- [ ] **Step 12.1: Implement `vault/types.py`**

```python
"""Typed data models for vault operations. Patches and notes."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class NewFile(BaseModel):
    path: Path
    content: str


class Edit(BaseModel):
    path: Path
    old: str
    new: str


class IndexEntryPatch(BaseModel):
    section: Literal["Sources", "Entities", "Concepts", "Synthesis"]
    line: str  # e.g. "- [[slug]] — summary"
    domain: str


class PatchSet(BaseModel):
    """The typed output of the integrate step. Every LLM vault mutation is a PatchSet."""

    new_files: list[NewFile] = Field(default_factory=list)
    edits: list[Edit] = Field(default_factory=list)
    index_entries: list[IndexEntryPatch] = Field(default_factory=list)
    log_entry: str | None = None
    reason: str = ""

    def total_size(self) -> int:
        return sum(len(nf.content) for nf in self.new_files) + sum(
            len(e.new) for e in self.edits
        )

    def file_count(self) -> int:
        touched = {nf.path for nf in self.new_files} | {e.path for e in self.edits}
        return len(touched)
```

- [ ] **Step 12.2: Commit**

```bash
git add packages/brain_core/src/brain_core/vault/types.py
git commit -m "feat(brain_core): vault typed models (PatchSet, NewFile, Edit, IndexEntryPatch)"
```

---

## Task 13 — `brain_core.vault.writer` (VaultWriter: atomic writes, filelock, ceilings)

**Files:**
- Create: `packages/brain_core/src/brain_core/vault/writer.py`, `packages/brain_core/tests/vault/test_writer.py`

- [ ] **Step 13.1: Write failing tests**

```python
# packages/brain_core/tests/vault/test_writer.py
from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.vault.paths import ScopeError
from brain_core.vault.types import Edit, NewFile, PatchSet, IndexEntryPatch
from brain_core.vault.writer import (
    PatchTooLargeError,
    TooManyFilesError,
    VaultWriter,
)


def test_apply_new_file(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "research" / "sources" / "a.md",
                content="---\ntitle: A\n---\n\nhi\n",
            )
        ],
        log_entry="## [2026-04-13 10:00] ingest | new | [[a]] | touched: sources",
        reason="test",
    )
    receipt = vw.apply(ps, allowed_domains=("research",))
    assert receipt.applied_files == [ephemeral_vault / "research" / "sources" / "a.md"]
    assert (ephemeral_vault / "research" / "sources" / "a.md").read_text(encoding="utf-8").startswith("---")


def test_apply_edit(ephemeral_vault: Path) -> None:
    target = ephemeral_vault / "research" / "concepts" / "c.md"
    target.write_text("---\ntitle: C\n---\n\nold body\n", encoding="utf-8")
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        edits=[Edit(path=target, old="old body", new="new body")],
        log_entry="## [2026-04-13 10:01] update | [[c]]",
    )
    vw.apply(ps, allowed_domains=("research",))
    assert "new body" in target.read_text(encoding="utf-8")


def test_refuses_patch_outside_scope(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "personal" / "sources" / "x.md",
                content="---\ntitle: X\n---\n",
            )
        ]
    )
    with pytest.raises(ScopeError):
        vw.apply(ps, allowed_domains=("research",))


def test_rejects_oversize_patch(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault, max_patch_bytes=100)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "research" / "sources" / "big.md",
                content="x" * 200,
            )
        ]
    )
    with pytest.raises(PatchTooLargeError):
        vw.apply(ps, allowed_domains=("research",))


def test_rejects_too_many_files(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault, max_files_per_patch=2)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "research" / "sources" / f"n{i}.md",
                content="---\ntitle: n\n---\n",
            )
            for i in range(3)
        ]
    )
    with pytest.raises(TooManyFilesError):
        vw.apply(ps, allowed_domains=("research",))


def test_index_entry_patch_applied(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        index_entries=[
            IndexEntryPatch(section="Sources", line="- [[alpha]] — first", domain="research")
        ],
        log_entry="## [2026-04-13 10:02] ingest | [[alpha]]",
    )
    vw.apply(ps, allowed_domains=("research",))
    idx = (ephemeral_vault / "research" / "index.md").read_text(encoding="utf-8")
    assert "[[alpha]] — first" in idx


def test_atomic_no_partial_state_on_failure(ephemeral_vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If one write in a patch fails, earlier writes are rolled back via undo log."""
    vw = VaultWriter(vault_root=ephemeral_vault)
    good = ephemeral_vault / "research" / "sources" / "good.md"
    ps = PatchSet(
        new_files=[
            NewFile(path=good, content="---\ntitle: G\n---\n"),
            NewFile(path=ephemeral_vault / "personal" / "sources" / "bad.md", content="---\n---\n"),
        ]
    )
    with pytest.raises(ScopeError):
        vw.apply(ps, allowed_domains=("research",))
    assert not good.exists()
```

- [ ] **Step 13.2: Run; verify failure**

Run: `uv run pytest packages/brain_core/tests/vault/test_writer.py -v`

- [ ] **Step 13.3: Implement `vault/writer.py`**

```python
"""VaultWriter — the only path through which the vault is mutated.

Enforces scope_guard on every path, atomic write-and-rename, filelock-based
concurrency, per-operation write ceilings, and an undo log.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

from brain_core.vault.index import IndexEntry, IndexFile
from brain_core.vault.log import LogEntry, LogFile
from brain_core.vault.paths import scope_guard
from brain_core.vault.types import PatchSet


class PatchTooLargeError(ValueError):
    """Raised when a PatchSet exceeds max_patch_bytes."""


class TooManyFilesError(ValueError):
    """Raised when a PatchSet touches more files than allowed."""


@dataclass
class Receipt:
    applied_files: list[Path] = field(default_factory=list)
    undo_id: str | None = None


class VaultWriter:
    def __init__(
        self,
        *,
        vault_root: Path,
        max_patch_bytes: int = 500 * 1024,
        max_files_per_patch: int = 50,
    ) -> None:
        self.vault_root = vault_root.resolve()
        self.max_patch_bytes = max_patch_bytes
        self.max_files_per_patch = max_files_per_patch
        self._locks_dir = self.vault_root / ".brain" / "locks"
        self._locks_dir.mkdir(parents=True, exist_ok=True)
        self._undo_dir = self.vault_root / ".brain" / "undo"
        self._undo_dir.mkdir(parents=True, exist_ok=True)

    # ---- public API ----------------------------------------------------

    def apply(self, patch: PatchSet, *, allowed_domains: tuple[str, ...]) -> Receipt:
        if patch.total_size() > self.max_patch_bytes:
            raise PatchTooLargeError(
                f"patch total size {patch.total_size()} > limit {self.max_patch_bytes}"
            )
        if patch.file_count() > self.max_files_per_patch:
            raise TooManyFilesError(
                f"patch touches {patch.file_count()} files > limit {self.max_files_per_patch}"
            )

        # pre-validate every path before any mutation
        for nf in patch.new_files:
            scope_guard(nf.path, vault_root=self.vault_root, allowed_domains=allowed_domains)
        for e in patch.edits:
            scope_guard(e.path, vault_root=self.vault_root, allowed_domains=allowed_domains)
        for ie in patch.index_entries:
            if ie.domain not in allowed_domains:
                raise PermissionError(
                    f"index entry for domain {ie.domain!r} not in allowed {allowed_domains}"
                )

        receipt = Receipt()
        undo_id = self._new_undo_id()
        undo_records: list[tuple[Path, str | None]] = []  # (path, previous_content or None if new)

        lock = FileLock(str(self._locks_dir / "global.lock"))
        with lock.acquire(timeout=30):
            try:
                for nf in patch.new_files:
                    undo_records.append((nf.path, None))
                    self._atomic_write(nf.path, nf.content)
                    receipt.applied_files.append(nf.path)
                for e in patch.edits:
                    prev = e.path.read_text(encoding="utf-8")
                    if e.old not in prev:
                        raise ValueError(f"edit old-text not found in {e.path}")
                    undo_records.append((e.path, prev))
                    self._atomic_write(e.path, prev.replace(e.old, e.new, 1))
                    receipt.applied_files.append(e.path)
                for ie in patch.index_entries:
                    idx_path = self.vault_root / ie.domain / "index.md"
                    idx = IndexFile.load(idx_path)
                    parsed = _parse_index_line(ie.line)
                    idx.add_entry(ie.section, parsed)
                    idx.save()
                if patch.log_entry:
                    domain = _infer_domain_from_log(patch.log_entry) or allowed_domains[0]
                    log = LogFile(self.vault_root / domain / "log.md")
                    log.append(
                        LogEntry(
                            timestamp=datetime.now(tz=timezone.utc),
                            op="patch",
                            summary=patch.log_entry.lstrip("#").strip() or patch.reason,
                        )
                    )
                self._write_undo_record(undo_id, undo_records)
                receipt.undo_id = undo_id
            except Exception:
                # rollback
                for path, prev in reversed(undo_records):
                    if prev is None:
                        if path.exists():
                            path.unlink()
                    else:
                        self._atomic_write(path, prev)
                raise
        return receipt

    # ---- internals -----------------------------------------------------

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # write to temp in the same dir then rename (atomic on same filesystem)
        fd, tmp = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _new_undo_id(self) -> str:
        return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S%f")

    def _write_undo_record(self, undo_id: str, records: list[tuple[Path, str | None]]) -> None:
        target = self._undo_dir / f"{undo_id}.txt"
        lines: list[str] = []
        for p, prev in records:
            lines.append(f"PATH\t{p}")
            if prev is None:
                lines.append("NEW")
            else:
                lines.append("PREV_LEN\t" + str(len(prev)))
                lines.append(prev)
                lines.append("END_PREV")
        target.write_text("\n".join(lines), encoding="utf-8")


def _parse_index_line(line: str) -> IndexEntry:
    # expected: "- [[target]] — summary"
    import re

    m = re.match(r"^- \[\[([^\]]+)\]\]\s*—\s*(.*)$", line.strip())
    if not m:
        raise ValueError(f"invalid index entry line: {line!r}")
    return IndexEntry(target=m.group(1), summary=m.group(2))


def _infer_domain_from_log(log_entry: str) -> str | None:
    # Currently logs are per-domain; the caller normally knows the domain.
    # This helper is a best-effort fallback for patches that don't specify.
    return None
```

- [ ] **Step 13.4: Run; verify passing**

Run: `uv run pytest packages/brain_core/tests/vault/test_writer.py -v`
Expected: **7 passed**.

- [ ] **Step 13.5: Commit**

```bash
git add packages/brain_core/src/brain_core/vault/writer.py packages/brain_core/tests/vault/test_writer.py
git commit -m "feat(brain_core): VaultWriter with atomic writes, filelock, ceilings, undo log"
```

---

## Task 14 — `brain_core.vault.undo` (undo log replay)

**Files:**
- Create: `packages/brain_core/src/brain_core/vault/undo.py`, `packages/brain_core/tests/vault/test_undo.py`

- [ ] **Step 14.1: Write failing tests**

```python
# packages/brain_core/tests/vault/test_undo.py
from __future__ import annotations

from pathlib import Path

from brain_core.vault.types import NewFile, Edit, PatchSet
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter


def test_undo_new_file(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    target = ephemeral_vault / "research" / "sources" / "x.md"
    ps = PatchSet(new_files=[NewFile(path=target, content="---\ntitle: x\n---\n")])
    r = vw.apply(ps, allowed_domains=("research",))
    assert target.exists()
    UndoLog(vault_root=ephemeral_vault).revert(r.undo_id)  # type: ignore[arg-type]
    assert not target.exists()


def test_undo_edit_restores_prior(ephemeral_vault: Path) -> None:
    target = ephemeral_vault / "research" / "concepts" / "c.md"
    target.write_text("---\ntitle: c\n---\n\nv1\n", encoding="utf-8")
    vw = VaultWriter(vault_root=ephemeral_vault)
    r = vw.apply(
        PatchSet(edits=[Edit(path=target, old="v1", new="v2")]),
        allowed_domains=("research",),
    )
    assert "v2" in target.read_text(encoding="utf-8")
    UndoLog(vault_root=ephemeral_vault).revert(r.undo_id)  # type: ignore[arg-type]
    assert "v1" in target.read_text(encoding="utf-8")
```

- [ ] **Step 14.2: Run; verify failure**

Run: `uv run pytest packages/brain_core/tests/vault/test_undo.py -v`

- [ ] **Step 14.3: Implement `vault/undo.py`**

```python
"""Undo log replay — reverts a previously applied PatchSet."""

from __future__ import annotations

from pathlib import Path


class UndoLog:
    def __init__(self, *, vault_root: Path) -> None:
        self.vault_root = vault_root.resolve()
        self._dir = self.vault_root / ".brain" / "undo"

    def revert(self, undo_id: str) -> None:
        record = (self._dir / f"{undo_id}.txt").read_text(encoding="utf-8")
        lines = record.split("\n")
        i = 0
        while i < len(lines):
            if not lines[i].startswith("PATH\t"):
                i += 1
                continue
            path = Path(lines[i].split("\t", 1)[1])
            i += 1
            if i < len(lines) and lines[i] == "NEW":
                if path.exists():
                    path.unlink()
                i += 1
            elif i < len(lines) and lines[i].startswith("PREV_LEN\t"):
                i += 1
                prev_lines: list[str] = []
                while i < len(lines) and lines[i] != "END_PREV":
                    prev_lines.append(lines[i])
                    i += 1
                i += 1  # skip END_PREV
                path.write_text("\n".join(prev_lines), encoding="utf-8")
```

- [ ] **Step 14.4: Run; verify passing**

Run: `uv run pytest packages/brain_core/tests/vault/test_undo.py -v`
Expected: **2 passed**.

- [ ] **Step 14.5: Commit**

```bash
git add packages/brain_core/src/brain_core/vault/undo.py packages/brain_core/tests/vault/test_undo.py
git commit -m "feat(brain_core): undo log replay for PatchSet reverts"
```

---

## Task 15 — `brain_core.llm.types` (request/response/stream types)

**Files:**
- Create: `packages/brain_core/src/brain_core/llm/__init__.py`, `packages/brain_core/src/brain_core/llm/types.py`

- [ ] **Step 15.1: Create `llm/__init__.py`**

```python
"""brain_core.llm — LLM provider abstraction, types, and concrete providers."""

from brain_core.llm.provider import LLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest, LLMResponse, LLMStreamChunk, TokenUsage

__all__ = [
    "LLMProvider",
    "LLMMessage",
    "LLMRequest",
    "LLMResponse",
    "LLMStreamChunk",
    "TokenUsage",
]
```

- [ ] **Step 15.2: Implement `llm/types.py`**

```python
"""Typed request/response/stream models shared across all providers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class LLMMessage(BaseModel):
    role: Role
    content: str


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class LLMRequest(BaseModel):
    model: str
    messages: list[LLMMessage]
    system: str | None = None
    max_tokens: int = 4096
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)
    stop_sequences: list[str] = Field(default_factory=list)


class LLMResponse(BaseModel):
    model: str
    content: str
    usage: TokenUsage
    stop_reason: str | None = None


class LLMStreamChunk(BaseModel):
    delta: str = ""
    usage: TokenUsage | None = None
    done: bool = False
```

- [ ] **Step 15.3: Commit**

```bash
git add packages/brain_core/src/brain_core/llm/__init__.py packages/brain_core/src/brain_core/llm/types.py
git commit -m "feat(brain_core): llm typed request/response/stream models"
```

---

## Task 16 — `brain_core.llm.provider` (Protocol) + `brain_core.llm.fake` (FakeLLMProvider)

**Files:**
- Create: `packages/brain_core/src/brain_core/llm/provider.py`, `packages/brain_core/src/brain_core/llm/fake.py`, `packages/brain_core/tests/llm/__init__.py`, `packages/brain_core/tests/llm/test_fake.py`, `packages/brain_core/tests/llm/test_provider_protocol.py`

- [ ] **Step 16.1: Write failing tests**

```python
# packages/brain_core/tests/llm/test_fake.py
from __future__ import annotations

import pytest

from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest


@pytest.mark.asyncio
async def test_fake_returns_queued_response() -> None:
    fake = FakeLLMProvider()
    fake.queue("hello world", input_tokens=10, output_tokens=2)
    req = LLMRequest(model="claude-sonnet-4-6", messages=[LLMMessage(role="user", content="hi")])
    resp = await fake.complete(req)
    assert resp.content == "hello world"
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 2


@pytest.mark.asyncio
async def test_fake_raises_when_queue_empty() -> None:
    fake = FakeLLMProvider()
    req = LLMRequest(model="claude-sonnet-4-6", messages=[LLMMessage(role="user", content="hi")])
    with pytest.raises(RuntimeError, match="queue is empty"):
        await fake.complete(req)


@pytest.mark.asyncio
async def test_fake_records_requests() -> None:
    fake = FakeLLMProvider()
    fake.queue("x")
    req = LLMRequest(model="claude-sonnet-4-6", messages=[LLMMessage(role="user", content="q")])
    await fake.complete(req)
    assert len(fake.requests) == 1
    assert fake.requests[0].messages[0].content == "q"
```

```python
# packages/brain_core/tests/llm/test_provider_protocol.py
from __future__ import annotations

from brain_core.llm.provider import LLMProvider
from brain_core.llm.fake import FakeLLMProvider


def test_fake_satisfies_protocol() -> None:
    p: LLMProvider = FakeLLMProvider()
    assert p is not None
```

- [ ] **Step 16.2: Run; verify failure**

Run: `uv run pytest packages/brain_core/tests/llm -v`

- [ ] **Step 16.3: Implement `llm/provider.py`**

```python
"""LLMProvider Protocol — every concrete provider must satisfy this."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from brain_core.llm.types import LLMRequest, LLMResponse, LLMStreamChunk


@runtime_checkable
class LLMProvider(Protocol):
    """Contract every LLM backend must honor."""

    name: str

    async def complete(self, request: LLMRequest) -> LLMResponse: ...

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]: ...
```

- [ ] **Step 16.4: Implement `llm/fake.py`**

```python
"""FakeLLMProvider — queue-based stub for tests. No network calls ever."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from brain_core.llm.types import LLMRequest, LLMResponse, LLMStreamChunk, TokenUsage


@dataclass
class _QueuedResponse:
    content: str
    input_tokens: int
    output_tokens: int


class FakeLLMProvider:
    name = "fake"

    def __init__(self) -> None:
        self._queue: list[_QueuedResponse] = []
        self.requests: list[LLMRequest] = []

    def queue(self, content: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self._queue.append(_QueuedResponse(content=content, input_tokens=input_tokens, output_tokens=output_tokens))

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self._queue:
            raise RuntimeError("FakeLLMProvider queue is empty — call .queue() before .complete()")
        q = self._queue.pop(0)
        return LLMResponse(
            model=request.model,
            content=q.content,
            usage=TokenUsage(input_tokens=q.input_tokens, output_tokens=q.output_tokens),
            stop_reason="end_turn",
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        self.requests.append(request)
        if not self._queue:
            raise RuntimeError("FakeLLMProvider queue is empty — call .queue() before .stream()")
        q = self._queue.pop(0)
        for ch in q.content:
            yield LLMStreamChunk(delta=ch)
        yield LLMStreamChunk(
            usage=TokenUsage(input_tokens=q.input_tokens, output_tokens=q.output_tokens),
            done=True,
        )
```

- [ ] **Step 16.5: Run; verify passing**

Run: `uv run pytest packages/brain_core/tests/llm -v`
Expected: **4 passed**.

- [ ] **Step 16.6: Commit**

```bash
git add packages/brain_core/src/brain_core/llm/provider.py packages/brain_core/src/brain_core/llm/fake.py packages/brain_core/tests/llm
git commit -m "feat(brain_core): LLMProvider Protocol + FakeLLMProvider for tests"
```

---

## Task 17 — `brain_core.llm.providers.anthropic` (Anthropic impl)

**Files:**
- Create: `packages/brain_core/src/brain_core/llm/providers/__init__.py`, `packages/brain_core/src/brain_core/llm/providers/anthropic.py`, `packages/brain_core/tests/llm/test_anthropic.py`

- [ ] **Step 17.1: Write failing tests (mocked Anthropic SDK)**

```python
# packages/brain_core/tests/llm/test_anthropic.py
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from brain_core.llm.providers.anthropic import AnthropicProvider
from brain_core.llm.types import LLMMessage, LLMRequest


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = SimpleNamespace(create=self._create)
        self.last_kwargs: dict[str, Any] | None = None

    async def _create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hello")],
            usage=SimpleNamespace(input_tokens=12, output_tokens=3),
            stop_reason="end_turn",
            model=kwargs["model"],
        )


@pytest.mark.asyncio
async def test_anthropic_complete_translates_request_and_response() -> None:
    client = _FakeAnthropicClient()
    provider = AnthropicProvider(api_key="sk-test", client=client)  # type: ignore[arg-type]
    req = LLMRequest(
        model="claude-sonnet-4-6",
        messages=[LLMMessage(role="user", content="hi")],
        system="you are brain",
    )
    resp = await provider.complete(req)
    assert resp.content == "hello"
    assert resp.usage.input_tokens == 12
    assert resp.usage.output_tokens == 3
    assert client.last_kwargs is not None
    assert client.last_kwargs["system"] == "you are brain"
    assert client.last_kwargs["messages"][0]["role"] == "user"
```

- [ ] **Step 17.2: Run; verify failure**

Run: `uv run pytest packages/brain_core/tests/llm/test_anthropic.py -v`

- [ ] **Step 17.3: Create `llm/providers/__init__.py`**

Empty file.

- [ ] **Step 17.4: Implement `llm/providers/anthropic.py`**

```python
"""AnthropicProvider — production LLMProvider implementation. The ONLY module that imports the anthropic SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from brain_core.llm.types import LLMRequest, LLMResponse, LLMStreamChunk, TokenUsage


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, *, api_key: str, client: Any | None = None) -> None:
        if client is None:
            from anthropic import AsyncAnthropic  # imported lazily — tests use the client= kwarg
            client = AsyncAnthropic(api_key=api_key)
        self._client = client

    async def complete(self, request: LLMRequest) -> LLMResponse:
        raw = await self._client.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system or "",
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            stop_sequences=request.stop_sequences or None,
        )
        text = "".join(block.text for block in raw.content if getattr(block, "type", "") == "text")
        return LLMResponse(
            model=raw.model,
            content=text,
            usage=TokenUsage(
                input_tokens=getattr(raw.usage, "input_tokens", 0),
                output_tokens=getattr(raw.usage, "output_tokens", 0),
            ),
            stop_reason=getattr(raw, "stop_reason", None),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        # Streaming implementation is tested live in plan 02's contract tests;
        # here we provide a minimal async-iter bridge.
        async with self._client.messages.stream(
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system or "",
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
        ) as s:
            async for event in s:
                delta = getattr(event, "delta", None)
                text = getattr(delta, "text", "") if delta else ""
                if text:
                    yield LLMStreamChunk(delta=text)
            final = await s.get_final_message()
            yield LLMStreamChunk(
                usage=TokenUsage(
                    input_tokens=getattr(final.usage, "input_tokens", 0),
                    output_tokens=getattr(final.usage, "output_tokens", 0),
                ),
                done=True,
            )
```

- [ ] **Step 17.5: Run; verify passing**

Run: `uv run pytest packages/brain_core/tests/llm/test_anthropic.py -v`
Expected: **1 passed**.

- [ ] **Step 17.6: Commit**

```bash
git add packages/brain_core/src/brain_core/llm/providers packages/brain_core/tests/llm/test_anthropic.py
git commit -m "feat(brain_core): AnthropicProvider — sole import site for anthropic SDK"
```

---

## Task 18 — `brain_core.cost.ledger` (costs.sqlite writer)

**Files:**
- Create: `packages/brain_core/src/brain_core/cost/__init__.py`, `packages/brain_core/src/brain_core/cost/ledger.py`, `packages/brain_core/tests/cost/__init__.py`, `packages/brain_core/tests/cost/test_ledger.py`

- [ ] **Step 18.1: Write failing tests**

```python
# packages/brain_core/tests/cost/test_ledger.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from brain_core.cost.ledger import CostEntry, CostLedger


def test_write_and_aggregate(tmp_path: Path) -> None:
    db = tmp_path / "costs.sqlite"
    ledger = CostLedger(db_path=db)
    now = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    ledger.record(CostEntry(
        timestamp=now, operation="ingest", model="claude-sonnet-4-6",
        input_tokens=1000, output_tokens=500, cost_usd=0.01, domain="research",
    ))
    ledger.record(CostEntry(
        timestamp=now, operation="chat", model="claude-sonnet-4-6",
        input_tokens=200, output_tokens=400, cost_usd=0.008, domain="work",
    ))
    assert round(ledger.total_for_day(now.date()), 4) == 0.018
    by_domain = ledger.total_by_domain(now.date())
    assert round(by_domain["research"], 4) == 0.01
    assert round(by_domain["work"], 4) == 0.008


def test_persists_across_instances(tmp_path: Path) -> None:
    db = tmp_path / "costs.sqlite"
    l1 = CostLedger(db_path=db)
    now = datetime(2026, 4, 13, tzinfo=timezone.utc)
    l1.record(CostEntry(
        timestamp=now, operation="x", model="claude-sonnet-4-6",
        input_tokens=1, output_tokens=1, cost_usd=0.001, domain="research",
    ))
    assert CostLedger(db_path=db).total_for_day(now.date()) == 0.001
```

- [ ] **Step 18.2: Run; verify failure**

Run: `uv run pytest packages/brain_core/tests/cost/test_ledger.py -v`

- [ ] **Step 18.3: Create `cost/__init__.py`**

```python
"""brain_core.cost — cost ledger and budget enforcement."""

from brain_core.cost.ledger import CostEntry, CostLedger
from brain_core.cost.budget import BudgetEnforcer, BudgetExceededError

__all__ = ["CostEntry", "CostLedger", "BudgetEnforcer", "BudgetExceededError"]
```

- [ ] **Step 18.4: Implement `cost/ledger.py`**

```python
"""costs.sqlite — append-only cost ledger with per-day and per-domain aggregation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class CostEntry:
    timestamp: datetime
    operation: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    domain: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc TEXT NOT NULL,
    day TEXT NOT NULL,
    operation TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    domain TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_costs_day ON costs(day);
CREATE INDEX IF NOT EXISTS idx_costs_domain ON costs(domain);
"""


class CostLedger:
    def __init__(self, *, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def record(self, entry: CostEntry) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO costs (ts_utc, day, operation, model, input_tokens, output_tokens, cost_usd, domain) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.timestamp.astimezone(timezone.utc).isoformat(),
                    entry.timestamp.astimezone(timezone.utc).date().isoformat(),
                    entry.operation,
                    entry.model,
                    entry.input_tokens,
                    entry.output_tokens,
                    entry.cost_usd,
                    entry.domain,
                ),
            )

    def total_for_day(self, d: date) -> float:
        with self._conn() as c:
            row = c.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM costs WHERE day = ?",
                (d.isoformat(),),
            ).fetchone()
        return float(row[0])

    def total_by_domain(self, d: date) -> dict[str, float]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT domain, COALESCE(SUM(cost_usd), 0.0) FROM costs WHERE day = ? GROUP BY domain",
                (d.isoformat(),),
            ).fetchall()
        return {domain: float(total) for domain, total in rows}

    def total_for_month(self, year: int, month: int) -> float:
        prefix = f"{year:04d}-{month:02d}"
        with self._conn() as c:
            row = c.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM costs WHERE day LIKE ?",
                (f"{prefix}%",),
            ).fetchone()
        return float(row[0])
```

- [ ] **Step 18.5: Run; verify passing**

Run: `uv run pytest packages/brain_core/tests/cost/test_ledger.py -v`
Expected: **2 passed**.

- [ ] **Step 18.6: Commit**

```bash
git add packages/brain_core/src/brain_core/cost packages/brain_core/tests/cost
git commit -m "feat(brain_core): costs.sqlite ledger with day/month/domain aggregation"
```

---

## Task 19 — `brain_core.cost.budget` (enforcement + pre-call estimation)

**Files:**
- Create: `packages/brain_core/src/brain_core/cost/budget.py`, `packages/brain_core/tests/cost/test_budget.py`

- [ ] **Step 19.1: Write failing tests**

```python
# packages/brain_core/tests/cost/test_budget.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from brain_core.cost.ledger import CostEntry, CostLedger
from brain_core.cost.budget import BudgetEnforcer, BudgetExceededError


def _fresh(tmp_path: Path) -> tuple[CostLedger, BudgetEnforcer]:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    be = BudgetEnforcer(ledger=ledger, daily_usd=1.0, monthly_usd=10.0)
    return ledger, be


def test_under_budget_allows(tmp_path: Path) -> None:
    _, be = _fresh(tmp_path)
    be.check_can_spend(0.5)  # should not raise


def test_over_daily_budget_raises(tmp_path: Path) -> None:
    ledger, be = _fresh(tmp_path)
    ledger.record(CostEntry(
        timestamp=datetime.now(tz=timezone.utc), operation="x", model="m",
        input_tokens=1, output_tokens=1, cost_usd=0.9, domain="research",
    ))
    with pytest.raises(BudgetExceededError, match="daily"):
        be.check_can_spend(0.2)


def test_estimate_cost_for_request() -> None:
    # claude-sonnet-4-6: $3/Mtok in, $15/Mtok out (plan 01 uses these as placeholder rates)
    _, be = BudgetEnforcer(ledger=None, daily_usd=1e9, monthly_usd=1e9), None  # type: ignore[assignment]
    est = BudgetEnforcer.estimate_cost(
        model="claude-sonnet-4-6", input_tokens=1000, output_tokens=500
    )
    # $3 * 0.001 + $15 * 0.0005 = 0.003 + 0.0075 = 0.0105
    assert round(est, 4) == 0.0105
```

- [ ] **Step 19.2: Run; verify failure**

Run: `uv run pytest packages/brain_core/tests/cost/test_budget.py -v`

- [ ] **Step 19.3: Implement `cost/budget.py`**

```python
"""Budget enforcement + pre-call cost estimation.

Model pricing table is deliberately hard-coded here as a starting baseline. When pricing
changes, update this table — it is also surfaced in the Settings UI so users know the
numbers they see are current. Adding a new model requires a row here.
"""

from __future__ import annotations

from datetime import datetime, timezone

from brain_core.cost.ledger import CostLedger


class BudgetExceededError(RuntimeError):
    """Raised when a projected spend would exceed a configured budget ceiling."""


# USD per million tokens. Update when provider pricing changes.
_PRICING: dict[str, tuple[float, float]] = {
    # model_id -> (input_per_Mtok, output_per_Mtok)
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-6":   (15.0, 75.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
}


class BudgetEnforcer:
    def __init__(self, *, ledger: CostLedger | None, daily_usd: float, monthly_usd: float) -> None:
        self._ledger = ledger
        self._daily = daily_usd
        self._monthly = monthly_usd

    @staticmethod
    def estimate_cost(*, model: str, input_tokens: int, output_tokens: int) -> float:
        if model not in _PRICING:
            raise KeyError(f"no pricing entry for model {model!r}")
        in_rate, out_rate = _PRICING[model]
        return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate

    def check_can_spend(self, projected_usd: float) -> None:
        if self._ledger is None:
            return
        now = datetime.now(tz=timezone.utc)
        day_total = self._ledger.total_for_day(now.date()) + projected_usd
        if day_total > self._daily:
            raise BudgetExceededError(
                f"daily budget exceeded: projected {day_total:.4f} > limit {self._daily:.2f}"
            )
        month_total = self._ledger.total_for_month(now.year, now.month) + projected_usd
        if month_total > self._monthly:
            raise BudgetExceededError(
                f"monthly budget exceeded: projected {month_total:.4f} > limit {self._monthly:.2f}"
            )
```

- [ ] **Step 19.4: Run; verify passing**

Run: `uv run pytest packages/brain_core/tests/cost/test_budget.py -v`
Expected: **3 passed**.

- [ ] **Step 19.5: Commit**

```bash
git add packages/brain_core/src/brain_core/cost/budget.py packages/brain_core/tests/cost/test_budget.py
git commit -m "feat(brain_core): budget enforcer + per-model cost estimation"
```

---

## Task 20 — Cross-platform smoke test

**Files:**
- Create: `packages/brain_core/tests/test_cross_platform.py`

- [ ] **Step 20.1: Write the tests**

```python
# packages/brain_core/tests/test_cross_platform.py
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from brain_core.vault.types import NewFile, PatchSet
from brain_core.vault.writer import VaultWriter


def test_vault_accepts_paths_with_spaces_and_unicode(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    target = ephemeral_vault / "research" / "sources" / "hello world — unicode ✓.md"
    ps = PatchSet(new_files=[NewFile(path=target, content="---\ntitle: hi\n---\n\nbody\n")])
    vw.apply(ps, allowed_domains=("research",))
    assert target.exists()
    assert "body" in target.read_text(encoding="utf-8")


def test_lf_line_endings_on_disk(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    target = ephemeral_vault / "research" / "sources" / "lf.md"
    content = "---\ntitle: lf\n---\n\nline1\nline2\n"
    ps = PatchSet(new_files=[NewFile(path=target, content=content)])
    vw.apply(ps, allowed_domains=("research",))
    # Read raw bytes to confirm no CRLF substitution occurred
    raw = target.read_bytes()
    assert b"\r\n" not in raw
    assert raw.count(b"\n") == content.count("\n")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only reserved-name check")
def test_windows_reserved_name_rejected(ephemeral_vault: Path) -> None:
    # CON, PRN, AUX, NUL, COM1-9, LPT1-9 are reserved on Windows.
    vw = VaultWriter(vault_root=ephemeral_vault)
    target = ephemeral_vault / "research" / "sources" / "CON.md"
    ps = PatchSet(new_files=[NewFile(path=target, content="---\n---\n")])
    with pytest.raises(OSError):
        vw.apply(ps, allowed_domains=("research",))
```

- [ ] **Step 20.2: Run; verify passing on current OS**

Run: `uv run pytest packages/brain_core/tests/test_cross_platform.py -v`
Expected: **2 passed** on Mac (3rd skipped); **3 passed** on Windows.

- [ ] **Step 20.3: Commit**

```bash
git add packages/brain_core/tests/test_cross_platform.py
git commit -m "test(brain_core): cross-platform smoke (spaces, unicode, LF endings, Win reserved names)"
```

---

## Task 21 — Full test sweep + coverage gate

- [ ] **Step 21.1: Run the full suite with coverage**

Run: `uv run pytest packages/brain_core --cov=brain_core --cov-report=term-missing -q`
Expected: **all tests passing**, coverage on `brain_core` ≥ **85%**. If below threshold, write tests for the uncovered lines before proceeding.

- [ ] **Step 21.2: Run mypy strict**

Run: `uv run mypy packages/brain_core/src`
Expected: `Success: no issues found`.

- [ ] **Step 21.3: Run ruff**

Run: `uv run ruff check .`
Run: `uv run ruff format --check .`
Expected: both clean.

- [ ] **Step 21.4: Commit any coverage-gap test additions**

```bash
git add packages/brain_core
git commit -m "test(brain_core): close coverage gaps to >=85%"
```

*(Commit only if Step 21.1 required new tests.)*

---

## Task 22 — Plan 01 demo gate

**Files:**
- Create: `scripts/demo-plan-01.py`

- [ ] **Step 22.1: Write the demo script**

```python
# scripts/demo-plan-01.py
"""Plan 01 end-to-end demo.

Runs in a temp directory, exercises the full brain_core surface with FakeLLMProvider,
and prints a success report. This is the plan 01 demo gate.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from brain_core.config.loader import load_config
from brain_core.cost.budget import BudgetEnforcer
from brain_core.cost.ledger import CostEntry, CostLedger
from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest
from brain_core.vault.index import IndexFile
from brain_core.vault.log import LogEntry, LogFile
from brain_core.vault.types import IndexEntryPatch, NewFile, PatchSet
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter


async def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "brain"
        _scaffold_vault(root)

        # 1. Config layered resolution
        cfg = load_config(
            config_file=None,
            env={"BRAIN_WEB_PORT": "5555"},
            cli_overrides={"vault_path": root},
        )
        assert cfg.web_port == 5555
        assert cfg.vault_path == root
        print(f"✓ config loaded: port={cfg.web_port} vault={cfg.vault_path}")

        # 2. FakeLLMProvider round trip
        fake = FakeLLMProvider()
        fake.queue("ok")
        resp = await fake.complete(
            LLMRequest(
                model="claude-sonnet-4-6", messages=[LLMMessage(role="user", content="hi")]
            )
        )
        assert resp.content == "ok"
        print("✓ FakeLLMProvider round trip")

        # 3. Cost ledger + budget enforcer
        ledger = CostLedger(db_path=root / ".brain" / "costs.sqlite")
        ledger.record(
            CostEntry(
                timestamp=datetime.now(tz=timezone.utc),
                operation="ingest",
                model="claude-sonnet-4-6",
                input_tokens=1000,
                output_tokens=300,
                cost_usd=0.0075,
                domain="research",
            )
        )
        today = datetime.now(tz=timezone.utc).date()
        assert round(ledger.total_for_day(today), 4) == 0.0075
        be = BudgetEnforcer(ledger=ledger, daily_usd=1.0, monthly_usd=10.0)
        be.check_can_spend(0.1)
        print(f"✓ cost ledger + budget enforcer (today=${ledger.total_for_day(today):.4f})")

        # 4. VaultWriter applies a real PatchSet
        vw = VaultWriter(vault_root=root)
        note_path = root / "research" / "sources" / "demo.md"
        patch = PatchSet(
            new_files=[
                NewFile(
                    path=note_path,
                    content=(
                        "---\n"
                        "title: Demo note\n"
                        "domain: research\n"
                        "type: source\n"
                        "---\n\n"
                        "This is a demo note written through VaultWriter.\n"
                    ),
                )
            ],
            index_entries=[
                IndexEntryPatch(section="Sources", line="- [[demo]] — plan 01 demo note", domain="research")
            ],
            log_entry="## [2026-04-13 12:00] ingest | source | [[demo]] | touched: sources, index",
            reason="plan 01 demo",
        )
        receipt = vw.apply(patch, allowed_domains=("research",))
        assert note_path.exists()
        idx = IndexFile.load(root / "research" / "index.md")
        assert any(e.target == "demo" for e in idx.sections["Sources"])
        print(f"✓ VaultWriter applied patch: {receipt.applied_files}")

        # 5. Log appended
        LogFile(root / "research" / "log.md").append(
            LogEntry(
                timestamp=datetime.now(tz=timezone.utc),
                op="ingest",
                summary="demo | source | [[demo]]",
            )
        )
        print("✓ log.md appended")

        # 6. Undo revert
        UndoLog(vault_root=root).revert(receipt.undo_id or "")
        assert not note_path.exists()
        print("✓ undo log reverts the patch")

        print("\nPLAN 01 DEMO OK")
        return 0


def _scaffold_vault(root: Path) -> None:
    root.mkdir(parents=True)
    (root / ".brain").mkdir()
    for domain in ("research", "work", "personal"):
        d = root / domain
        for sub in ("sources", "entities", "concepts", "synthesis"):
            (d / sub).mkdir(parents=True)
        (d / "index.md").write_text(
            f"# {domain} — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
            encoding="utf-8",
        )
        (d / "log.md").write_text(f"# {domain} — log\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 22.2: Run the demo**

Run: `uv run python scripts/demo-plan-01.py`
Expected: prints 6 checkmarks and `PLAN 01 DEMO OK`, exit 0.

- [ ] **Step 22.3: Capture the demo output as a proof artifact**

Save the terminal output (copy-paste or screenshot) into the PR description or the plan-completion review. This is the verification artifact per `CLAUDE.md` "Verification Before Done."

- [ ] **Step 22.4: Update `tasks/todo.md`**

Edit `tasks/todo.md`:
- Change Plan 01 status from `📝 Ready for execution` to `✅ Complete`.
- Append a line under "Plan 01" with the demo date and a link to the proof artifact.

- [ ] **Step 22.5: Update `tasks/lessons.md`**

Add an entry under "Plan 01 — Foundation" with any corrections, gotchas, or cross-platform surprises encountered during execution. If there were none, note `_none encountered_`.

- [ ] **Step 22.6: Final commit and tag**

```bash
git add scripts/demo-plan-01.py tasks/todo.md tasks/lessons.md
git commit -m "feat: plan 01 complete — brain_core foundation with passing demo"
git tag plan-01-foundation
```

---

## Verification checklist (reviewer gate)

Before marking this plan ✅ in `tasks/todo.md`, confirm:

- [ ] `uv run pytest packages/brain_core` — all tests pass
- [ ] `uv run pytest packages/brain_core --cov=brain_core --cov-report=term-missing` — coverage ≥ 85%
- [ ] `uv run mypy packages/brain_core/src` — clean
- [ ] `uv run ruff check .` and `uv run ruff format --check .` — clean
- [ ] `uv run python scripts/demo-plan-01.py` — prints `PLAN 01 DEMO OK`
- [ ] CI green on **Mac AND Windows** after push
- [ ] No file outside `brain-core-engineer`'s ownership was modified (check `git diff` against `ORCHESTRATION_GUIDE.md` ownership table)
- [ ] No Anthropic SDK import outside `brain_core/llm/providers/anthropic.py` (check with `uv run ruff check --select=F401 packages/brain_core` or `grep -rn "from anthropic" packages/brain_core/src | grep -v providers/anthropic.py` — expect no matches)
- [ ] `scope_guard` is referenced by `VaultWriter` for every path write — verify in `writer.py`
- [ ] `tasks/lessons.md` updated with any corrections from this plan

---

## Self-review notes (pre-execution)

- **Spec coverage**: this plan implements §3 (repo layout), §4 partially (vault mechanics — no content yet), §5 partially (config + cost + llm abstraction, not the ingest pipeline), §10 partially (error taxonomy foundations — safety rails are in place). The ingest pipeline, chat loop, prompts, MCP server, API, frontend, install, and UI design are all explicitly deferred to plans 02–09.
- **Type consistency**: `PatchSet`, `NewFile`, `Edit`, `IndexEntryPatch` are defined once in `vault/types.py` and used consistently in `writer.py` tests and the demo script. `LLMRequest/Response/StreamChunk` are defined once in `llm/types.py`.
- **Placeholders**: none. Every step has real code. `_infer_domain_from_log` is a deliberately-simple best-effort helper noted as such, not a TODO.
- **Pricing table**: `_PRICING` in `cost/budget.py` uses hard-coded placeholder rates. These are explicitly called out in a module docstring and must be verified against current Anthropic pricing before plan 01 executes — a 2-minute lookup, not a code change.
- **Scope**: this plan is sized for one subagent-driven-development pass. It produces no user-facing surface, which is intentional — plan 02 will build on the foundation to produce the first demoable user workflow.

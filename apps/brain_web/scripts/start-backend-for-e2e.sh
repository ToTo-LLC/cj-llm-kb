#!/usr/bin/env bash
# Boots brain_api against a freshly seeded temp vault for Playwright e2e.
#
# - Creates a deterministic-but-unique vault under $TMPDIR.
# - Seeds one domain (research/) with a welcome note + index so /browse has
#   content to render and the a11y sweep has something real under test.
# - Deliberately omits BRAIN.md so the /setup redirect fires the first time
#   the setup-wizard spec visits /. Once the wizard seeds BRAIN.md via the
#   real proposeNote + applyPatch path, subsequent specs bypass /setup.
# - Starts uvicorn --factory against the in-tree ``e2e_backend:build_app``
#   shim so brain_api reads vault_root from the environment. FakeLLMProvider
#   is the default inside ``build_app_context`` — no API keys, no network.
#
# The script runs in foreground (uvicorn replaces the shell via exec) so
# Playwright's webServer keep-alive + teardown semantics work correctly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# --- vault root --------------------------------------------------------------
# Honor BRAIN_VAULT_ROOT when set (CI passes it for parity across scripts);
# otherwise mint a fresh temp dir per run so tests don't share state.
if [[ -z "${BRAIN_VAULT_ROOT:-}" ]]; then
  BRAIN_VAULT_ROOT="$(mktemp -d -t brain-e2e-vault-XXXXXX)"
fi
export BRAIN_VAULT_ROOT

mkdir -p "${BRAIN_VAULT_ROOT}/research/notes"
mkdir -p "${BRAIN_VAULT_ROOT}/work/notes"
mkdir -p "${BRAIN_VAULT_ROOT}/.brain/run"

# Seed one research note so the BM25 retrieval index has something to return
# and the Browse screen has a note to render.
cat > "${BRAIN_VAULT_ROOT}/research/notes/welcome.md" <<'NOTE'
---
title: Welcome
---

This is a seeded note for the brain e2e test run.
NOTE

cat > "${BRAIN_VAULT_ROOT}/research/index.md" <<'INDEX'
# research

- [[welcome]]
INDEX

cat > "${BRAIN_VAULT_ROOT}/work/index.md" <<'INDEX'
# work

_Nothing here yet._
INDEX

# NOTE: intentionally no BRAIN.md — the setup-wizard spec needs
# ``detectSetupStatus`` to report isFirstRun=true, which requires the
# BRAIN.md gate to fail. Specs that expect a settled vault seed BRAIN.md
# themselves via proposeNote + applyPatch (i.e. by walking the wizard)
# or the seed helper in tests/e2e/fixtures.ts.

export BRAIN_ALLOWED_DOMAINS="${BRAIN_ALLOWED_DOMAINS:-research,work}"

echo "[e2e-backend] vault=${BRAIN_VAULT_ROOT}" >&2
echo "[e2e-backend] allowed=${BRAIN_ALLOWED_DOMAINS}" >&2

# --- launch uvicorn ----------------------------------------------------------
# --factory gives uvicorn a zero-arg callable it can invoke; our shim reads
# BRAIN_VAULT_ROOT/BRAIN_ALLOWED_DOMAINS from the env. 127.0.0.1 is required
# by OriginHostMiddleware — any non-loopback host is rejected.
cd "${REPO_ROOT}"
exec uv run uvicorn \
  --factory \
  --app-dir apps/brain_web/scripts \
  --host 127.0.0.1 \
  --port 4317 \
  --log-level warning \
  e2e_backend:build_app

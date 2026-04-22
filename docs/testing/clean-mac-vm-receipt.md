# Clean-Mac VM dry run — receipt

**TEMPLATE.** Copy-paste log output into each fenced block. Fill every
`<fill me in>` placeholder. Add Deviations + Findings. Set the Status
line at the bottom.

Related docs:
- Host instructions: [`clean-mac-vm-host-instructions.md`](./clean-mac-vm-host-instructions.md)
- Cross-platform notes: [`cross-platform.md`](./cross-platform.md)
- Full manual QA: [`manual-qa.md`](./manual-qa.md)

---

## Metadata

| Key | Value |
| --- | --- |
| Tester | `<your name>` |
| Dry-run date | `<YYYY-MM-DD>` |
| VM tool | `<Tart / UTM / Parallels>` |
| VM image | `<ghcr.io/cirruslabs/macos-sonoma-base:latest or ...>` |
| macOS version (inside VM) | `<14.x>` |
| VM arch | `<arm64 / x86_64>` |
| Host OS version | `<macOS 14.x>` |
| Host arch | `<arm64 / x86_64>` |
| Host LAN IP used | `<e.g. 10.0.0.42>` |
| Tarball filename | `<brain-dev-<sha>.tar.gz>` |
| Tarball SHA256 | `<64 hex>` |
| Dry run started | `<HH:MM:SS>` |
| Dry run ended | `<HH:MM:SS>` |
| Total elapsed | `<mm:ss>` |

---

## Step 1 — Cut + serve tarball (host)

Command (on host):

```bash
uv run python scripts/serve-local-tarball.py
```

Abbreviated output (paste the "ready to serve" summary only):

```
<fill me in — paste the ======== block printed by serve-local-tarball.py>
```

## Step 2 — Boot fresh Mac VM (host)

Commands:

```bash
tart clone ghcr.io/cirruslabs/macos-sonoma-base:latest brain-mac-dryrun
tart run brain-mac-dryrun
```

Observations:

- VM boot time: `<mm:ss>`
- First network reachability (curl manifest.json from inside VM): `<pass/fail>`

## Step 3 — Verify reachability (VM)

```
<fill me in — paste the `curl manifest.json` output>
```

## Step 4 — Install (VM)

### 4a. Fetch install.sh

Command:

```bash
curl -fsSL "http://${HOST_IP}:9000/install.sh" -o install.sh
```

Exit code: `<0 expected>`

### 4b. install.sh output

```
<fill me in — paste install-output.log contents>
```

### 4c. `brain doctor` output

```
<fill me in — paste doctor-output.log contents>
```

## Step 5 — Setup wizard + `brain start` (VM)

### `brain start` output

```
<fill me in — paste start-output.log contents>
```

### Wizard walkthrough

| Step | OK? | Notes |
| --- | --- | --- |
| Welcome | `<yes/no>` | |
| Vault location | `<yes/no>` | default path worked? |
| API key | `<yes/no>` | FakeLLM or real? |
| Theme | `<yes/no>` | which picked? |
| BRAIN.md seed | `<yes/no>` | which template? |
| Claude Desktop (skip) | `<yes/no>` | |
| Land on /chat | `<yes/no>` | |

## Step 6 — First ingest (VM)

Prompt used (exact string):

```
Please remember: our coffee provider is Blue Bottle, and we order the
Hayes Valley Espresso blend in 1lb bags monthly.
```

- Time to first delta: `<seconds>`
- Time to patch_proposed: `<seconds>`
- Patch approved from /pending: `<yes/no>`
- File on disk after approve (paste the `find` output):

```
<fill me in — paste `find ~/Documents/brain -name "*.md" -mmin -5 -print` output>
```

## Step 7 — Clean shutdown + uninstall (VM)

### `brain stop` output

```
<fill me in — paste stop-output.log contents>
```

### Orphan-process check

```
<fill me in — paste `ps aux | grep brain_api | grep -v grep` output>
```

### `brain uninstall --yes` output

```
<fill me in — paste uninstall-output.log contents>
```

### Verification

| Check | Result |
| --- | --- |
| `~/Applications/brain/` gone | `<yes/no>` |
| `~/Documents/brain/` preserved | `<yes/no>` |
| `which brain` → empty | `<yes/no>` |
| `~/.local/bin/brain` gone | `<yes/no>` |

---

## Timing

| Phase | Elapsed (s) | Target (s) | Pass? |
| --- | --- | --- | --- |
| Host: cut + serve start | `<fill>` | 10 | |
| VM boot + login | `<fill>` | 90 | |
| curl install.sh | `<fill>` | 3 | |
| install.sh end-to-end | `<fill>` | 120 | |
| `brain doctor` | `<fill>` | 5 | |
| `brain start` → browser open | `<fill>` | 5 | |
| Wizard walk-through | `<fill>` | 180 | |
| First ingest (send → approve) | `<fill>` | 30 | |
| `brain stop` | `<fill>` | 5 | |
| `brain uninstall --yes` | `<fill>` | 15 | |
| **Total wall clock** | `<fill>` | ≤2700 | |

---

## Screenshots

Drop each PNG into `docs/testing/screenshots/mac/` with the matching
name. Images render relative to this file.

![01 install complete](./screenshots/mac/01-install-complete.png)

![02 doctor output](./screenshots/mac/02-doctor-output.png)

![03 setup wizard](./screenshots/mac/03-wizard.png)

![04 chat empty state](./screenshots/mac/04-chat-empty.png)

![05 pending approved](./screenshots/mac/05-pending-approved.png)

![06 uninstall complete](./screenshots/mac/06-uninstall-complete.png)

---

## Deviations

Anything unexpected, confusing, or different from this receipt
template. Include: copy that misled you, any prompts the host-
instructions didn't mention, timing blowouts, surprising log output.

- `<fill me in, or write "none">`

## Findings

Bugs discovered during this run. File a GitHub issue for each and
link it here. Use the format: `ISSUE-NNN — <one-line title>`.

- `<fill me in, or write "none">`

## Unanswered questions

Anything the next person running this should know that isn't
captured elsewhere.

- `<fill me in, or write "none">`

---

## Status

Pick one — delete the others:

- **PASS** — every step clean, no deviations, no findings.
- **PASS WITH NOTES** — every step functional, but at least one
  deviation or minor finding documented above.
- **FAIL** — any step blocked, any release-blocker finding.

Signed: `<tester name>`

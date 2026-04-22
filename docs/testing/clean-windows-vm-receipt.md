# Clean-Windows VM dry run — receipt

**TEMPLATE.** Copy-paste log output into each fenced block. Fill every
`<fill me in>` placeholder. Add Deviations + Findings. Set the Status
line at the bottom.

Related docs:
- Host instructions: [`clean-windows-vm-host-instructions.md`](./clean-windows-vm-host-instructions.md)
- Cross-platform notes: [`cross-platform.md`](./cross-platform.md)
- Full manual QA: [`manual-qa.md`](./manual-qa.md)

---

## Metadata

| Key | Value |
| --- | --- |
| Tester | `<your name>` |
| Dry-run date | `<YYYY-MM-DD>` |
| VM tool | `<UTM / Parallels / VMware Fusion>` |
| VM image | `<Windows 11 ARM64 Evaluation / ...>` |
| Windows version (inside VM) | `<11 build ...>` |
| VM arch | `<arm64 / x64>` |
| Host OS version | `<macOS 14.x>` |
| Host arch | `<arm64 / x86_64>` |
| Host LAN IP used | `<e.g. 192.168.64.1>` |
| UTM / VM network mode | `<Shared / Bridged>` |
| PowerShell version (inside VM) | `<5.1.x / 7.x>` |
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

## Step 2 — Boot fresh Windows 11 VM (host)

Snapshot restored: `<clean-install / ...>`

Observations:

- VM boot time: `<mm:ss>`
- Sign-in method: `<local account / Microsoft account>`
- First network reachability (IWR manifest.json from inside VM): `<pass/fail>`

## Step 3 — Verify reachability (VM)

```
<fill me in — paste IWR manifest.json output>
```

## Step 4 — Install (VM)

### 4a. Fetch install.ps1

Command:

```powershell
Invoke-WebRequest -Uri "http://${HOST_IP}:9000/install.ps1" -OutFile install.ps1 -UseBasicParsing
```

- Exit code: `<0 expected>`
- SmartScreen banner shown? `<yes/no — if yes, note exact wording>`
- Execution policy required override? `<yes/no — which path taken>`

### 4b. install.ps1 output

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
| Vault location | `<yes/no>` | default path worked? which separator shown in UI? |
| API key | `<yes/no>` | FakeLLM or real? |
| Theme | `<yes/no>` | which picked? |
| BRAIN.md seed | `<yes/no>` | which template? |
| Claude Desktop (skip) | `<yes/no>` | |
| Land on /chat | `<yes/no>` | |

Which browser auto-opened? `<Edge / Chrome / other>`

## Step 6 — First ingest (VM)

Prompt used (exact string):

```
Please remember: our coffee provider is Blue Bottle, and we order the
Hayes Valley Espresso blend in 1lb bags monthly.
```

- Time to first delta: `<seconds>`
- Time to patch_proposed: `<seconds>`
- Patch approved from /pending: `<yes/no>`
- File on disk after approve (paste the `Get-ChildItem` output):

```
<fill me in>
```

## Step 7 — Clean shutdown + uninstall (VM)

### `brain stop` output

```
<fill me in — paste stop-output.log contents>
```

### Orphan-process check

```
<fill me in — paste `Get-Process | Where-Object ProcessName -like *brain*` output>
```

### `brain uninstall --yes` output

```
<fill me in — paste uninstall-output.log contents>
```

### Verification

| Check | Result |
| --- | --- |
| `$env:LOCALAPPDATA\brain` gone | `<yes/no>` |
| `~/Documents/brain` preserved | `<yes/no>` |
| `Get-Command brain` errors | `<yes/no>` |
| Start Menu `brain` entry gone | `<yes/no>` |
| Desktop shortcut gone (if created) | `<yes/no>` |

---

## Timing

| Phase | Elapsed (s) | Target (s) | Pass? |
| --- | --- | --- | --- |
| Host: cut + serve start | `<fill>` | 10 | |
| VM restore-from-snapshot + login | `<fill>` | 60 | |
| IWR install.ps1 | `<fill>` | 3 | |
| install.ps1 end-to-end | `<fill>` | 180 | |
| `brain doctor` | `<fill>` | 5 | |
| `brain start` → browser open | `<fill>` | 10 | |
| Wizard walk-through | `<fill>` | 180 | |
| First ingest (send → approve) | `<fill>` | 30 | |
| `brain stop` | `<fill>` | 5 | |
| `brain uninstall --yes` | `<fill>` | 20 | |
| **Total wall clock** | `<fill>` | ≤3600 | |

---

## Screenshots

Drop each PNG into `docs/testing/screenshots/windows/` with the
matching name. Images render relative to this file.

![01 install complete](./screenshots/windows/01-install-complete.png)

![02 doctor output](./screenshots/windows/02-doctor-output.png)

![03 setup wizard](./screenshots/windows/03-wizard.png)

![04 chat empty state](./screenshots/windows/04-chat-empty.png)

![05 pending approved](./screenshots/windows/05-pending-approved.png)

![06 uninstall complete](./screenshots/windows/06-uninstall-complete.png)

---

## Windows-specific observations

Record anything that applies — leave blank if not hit.

- **Path separators in logs**: `<any forward slashes where backslashes
  expected? e.g. in install-output.log>`
- **SQLite locking**: `<any "file in use" errors from brain stop /
  uninstall?>`
- **fnm PATH pollution**: `<ran `Get-Command node` after uninstall —
  any node/fnm still on PATH?>`
- **UAC prompts**: `<any at all? should be ZERO — treat any as bug>`
- **Defender SmartScreen**: `<banner wording, which button clicked>`
- **Windows Terminal vs conhost**: `<which shell hosted the install?>`
- **Default browser**: `<Edge/Chrome — did wizard render OK on both?>`

---

## Deviations

Anything unexpected, confusing, or different from this receipt
template.

- `<fill me in, or write "none">`

## Findings

Bugs discovered. File a GitHub issue for each.

- `<fill me in, or write "none">`

## Unanswered questions

- `<fill me in, or write "none">`

---

## Status

Pick one — delete the others:

- **PASS** — every step clean, no deviations, no findings.
- **PASS WITH NOTES** — every step functional, at least one deviation
  or minor finding documented above.
- **FAIL** — any step blocked, any release-blocker finding.

Signed: `<tester name>`

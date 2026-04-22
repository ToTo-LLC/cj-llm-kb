# Clean-Windows VM dry run — host instructions

Plan 08 Task 11. Same install → first-ingest → uninstall round-trip
as the Mac dry run, but on a fresh Windows 11 VM with `install.ps1`.

Time budget: ~60 min (Windows VMs are slower to first boot; install
itself runs in <2 min on a warm network).

All host paths assume the repo is at `~/Code/cj-llm-kb/`. Adjust if
your checkout lives elsewhere.

---

## 0. Prerequisites (one-time)

On the **host Mac**:

```bash
brew install --cask utm
```

Grab a Windows 11 ARM64 ISO from Microsoft's evaluation page (or
Parallels' free-trial image if you prefer). Build a new UTM VM:

- Platform: **Windows 11 ARM64** (for Apple Silicon) or
  **Windows 11 x64** (Intel Mac / Parallels).
- RAM: **8 GB** minimum. CPUs: **4**.
- Disk: **60 GB** dynamic.
- Network: **Shared Network** (NAT — easiest; host reachable at
  `192.168.64.1` or the UTM-assigned gateway).

Take a UTM **snapshot labeled `clean-install`** right after Windows
setup finishes + Windows Update completes but before installing
anything else. Every dry run restores from this snapshot, which is
what makes this a *clean* VM.

Optional: install PowerShell 7 inside the VM (`winget install
Microsoft.PowerShell`). Either PS 5.1 (shipped with Win11) or PS 7
must work — the install.ps1 script is 5.1-compatible.

Inside the host Mac's **firewall settings**, allow incoming
connections on `9000/tcp` from the local subnet (same as the Mac dry
run).

---

## 1. Cut + serve the tarball (on the host)

From the repo root on the host:

```bash
cd ~/Code/cj-llm-kb
uv run python scripts/serve-local-tarball.py
```

Copy the `HOST_IP=` + the "VM copy-paste (Windows PowerShell)" block —
you'll paste it inside the VM in step 4. Leave this terminal running.

---

## 2. Boot the Windows 11 VM

In UTM, open `brain-win-dryrun`. Restore the `clean-install` snapshot
(Right click → Restore Snapshot). Boot.

Sign in with the local admin account you created during setup. Open
**Windows Terminal** (Start → type "terminal"). Pick the
**PowerShell** profile (either 5.1 or 7 — both work).

---

## 3. Verify the VM can reach the host

Inside the VM PowerShell:

```powershell
Invoke-WebRequest -Uri "http://<HOST_IP>:9000/manifest.json" -UseBasicParsing `
    | Select-Object -ExpandProperty Content
```

You should see the JSON manifest. If not:

- `Test-NetConnection -ComputerName <HOST_IP> -Port 9000` — reveals
  whether it's a firewall issue (on the host) vs a routing issue (UTM
  NAT).
- From the host, `arp -a | grep <guessed-vm-ip>` shows you whether
  the VM has picked up a DHCP lease yet.
- If your UTM network is set to **Bridged**, the VM has its own LAN
  IP and the host IP is the same one the host advertises. If **Shared
  Network**, the host IP you pass is typically `192.168.64.1` on Mac.

---

## 4. Run the install inside the VM

Copy-paste this block inside the VM's PowerShell window, with
`<HOST_IP>` filled in. **If you hit an execution-policy prompt**, answer
`A` (Yes to All) or run the fallback command at the bottom of this
section.

```powershell
$HOST_IP = '<HOST_IP>'  # e.g. 192.168.64.1

New-Item -ItemType Directory -Force ~/brain-dryrun | Out-Null
Set-Location ~/brain-dryrun

# 4a. Fetch install.ps1
Invoke-WebRequest -Uri "http://${HOST_IP}:9000/install.ps1" `
    -OutFile install.ps1 -UseBasicParsing

# 4b. Run install.ps1 pointed at the served tarball
$env:BRAIN_RELEASE_URL = "http://${HOST_IP}:9000/brain-dev.tar.gz"
powershell.exe -ExecutionPolicy Bypass -File .\install.ps1 `
    *>&1 | Tee-Object install-output.log

# 4c. Diagnostic
brain doctor *>&1 | Tee-Object doctor-output.log
```

**Execution-policy fallback.** If the `powershell.exe -ExecutionPolicy
Bypass` line is blocked by a corporate policy, run this *before* step 4b:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
```

Then re-run from 4b without the `-ExecutionPolicy Bypass` prefix:

```powershell
.\install.ps1 *>&1 | Tee-Object install-output.log
```

**Defender SmartScreen.** A yellow-banner "Windows protected your PC"
warning on an unsigned script is expected for an unreleased build —
click "More info" → "Run anyway". Document the exact wording you saw in
the receipt's Deviations section so we can flag copy that needs work
for Plan 09 (code signing).

Expected end state:

- `install-output.log` ends with `brain installed.`
- `brain doctor` reports mostly PASS. Token file + config may FAIL
  pre-setup — expected; wizard fixes those.

**Screenshot #1** — terminal with the "brain installed" footer.

**Screenshot #2** — `brain doctor` output.

---

## 5. Walk the setup wizard

Still inside the VM:

```powershell
brain start *>&1 | Tee-Object start-output.log
```

Edge opens at `http://localhost:4317/setup`. If it doesn't, open Edge
manually and navigate.

Walk the wizard exactly as in the Mac dry run (Welcome → Vault path
→ API key → Theme → BRAIN.md seed → Claude Desktop skip → Start).

**Screenshot #3** — browser on any wizard step (step 2 with the vault
path visible is cleanest).

**Screenshot #4** — `/chat` page after wizard completion.

---

## 6. Do one ingest round-trip

Same content as the Mac run — use this exact string so we can diff
against the Mac receipt:

```
Please remember: our coffee provider is Blue Bottle, and we order the
Hayes Valley Espresso blend in 1lb bags monthly.
```

Send. Wait for the response + patch. Open `/pending`. Approve.

Verify in PowerShell:

```powershell
Get-ChildItem -Path ~/Documents/brain -Filter *.md -Recurse `
    | Where-Object { $_.LastWriteTime -gt (Get-Date).AddMinutes(-5) } `
    | Select-Object FullName
```

**Screenshot #5** — `/pending` after approve, or the PowerShell disk
listing.

---

## 7. Clean shutdown + uninstall

Back in PowerShell (a second Terminal tab is fine if `brain start` is
still attached to the first):

```powershell
brain stop *>&1 | Tee-Object stop-output.log

# Sanity: nothing left running.
Get-Process | Where-Object { $_.ProcessName -like "*brain*" } `
    | Select-Object ProcessName, Id

# Uninstall. --yes skips prompts; vault preserved by default.
brain uninstall --yes *>&1 | Tee-Object uninstall-output.log
```

Verify:

- `Get-Item $env:LOCALAPPDATA\brain` — should error (dir gone).
- `Test-Path ~/Documents/brain` — should return `True` (vault sacred).
- Start Menu → no `brain` entry.
- `Get-Command brain` — errors (shim removed from PATH).

**Screenshot #6** — PowerShell showing uninstall output + the vault
dir still present.

---

## 8. Copy logs + screenshots back to the host

UTM supports **SPICE shared folders** (Virtual drive mounted inside
Windows) or plain drag-drop for a few files. `scp` also works if you
enable OpenSSH Server inside Windows (`Settings → Apps → Optional
features → OpenSSH Server`).

Drop all six screenshots into
`~/Code/cj-llm-kb/docs/testing/screenshots/windows/` using the same
filenames as the Mac run:

```
01-install-complete.png
02-doctor-output.png
03-wizard.png
04-chat-empty.png
05-pending-approved.png
06-uninstall-complete.png
```

Watch for these **Windows-specific gotchas** — note anything you see
in the receipt's Deviations section:

- Path separators in log output (everything should use `\` on disk;
  `/` in URLs).
- **SQLite file locking** — Windows holds locks longer than Unix.
  Any errors from `brain stop` that reference a locked `.sqlite` file
  go in Deviations.
- **Edge vs Chrome default browser** — record which browser opened.
- **fnm PATH** — `brain doctor` prints "Node not required at
  runtime"; the install.ps1 build step needed Node but the user
  shouldn't see `PATH` pollution.
- **UAC prompts** — there should be **zero**. Any UAC prompt is a
  **bug**, not a deviation.

---

## 9. Fill in the receipt

Open `docs/testing/clean-windows-vm-receipt.md` and fill every `<fill
me in>` block from the matching log files (same mapping as Mac).

Commit everything together:

```bash
git add docs/testing/clean-windows-vm-receipt.md \
        docs/testing/screenshots/windows/
git commit -m "test(plan-08): clean-Windows VM dry run receipt"
```

---

## 10. Tear down

Inside the VM: Start → Power → Shut down.

On the host: UTM → right-click `brain-win-dryrun` → **Revert to
`clean-install` snapshot**. That's your reset-to-zero. The VM image
itself lives on; next dry run starts from the same pristine state.

Don't delete the `clean-install` snapshot — rebuilding it from a fresh
Windows ISO is a multi-hour job you want to amortize across every
install-flow change.

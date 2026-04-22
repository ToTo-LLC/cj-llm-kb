# Clean-Mac VM dry run — host instructions

Plan 08 Task 10. Walks a human tester through a full install →
first-ingest → uninstall round-trip on a fresh macOS 14 VM, with the
tarball served from the developer's Mac over HTTP on the LAN.

Time budget: ~45 min end to end (VM boot + install + wizard + ingest +
uninstall + receipt fill-in). The `brain install` itself should take
under 90 s on a warm network.

All paths in this doc assume the repo is at
`~/Code/cj-llm-kb/`. Adjust if your checkout lives elsewhere.

---

## 0. Prerequisites (one-time)

On the **host Mac**:

```bash
# Tart — VM manager for Apple Silicon.
brew install cirruslabs/cli/tart

# Verify the clean macOS 14 base image is present (pulls once, ~15 GB).
tart pull ghcr.io/cirruslabs/macos-sonoma-base:latest
```

Inside the host Mac's **firewall settings**, make sure incoming
connections on `9000/tcp` are allowed from the local subnet
(System Settings → Network → Firewall → Options). Without this, the VM
will time out on the first curl.

If Tart is inconvenient, UTM (`brew install --cask utm`) also works;
every step below that runs *inside the VM* is unchanged.

---

## 1. Cut + serve the tarball (on the host)

From the repo root on your host Mac:

```bash
cd ~/Code/cj-llm-kb
uv run python scripts/serve-local-tarball.py
```

Expected output:

```
==> Cut tarball from git HEAD
tarball: /tmp/brain-serve-XXXXX/_cut/brain-dev-<sha>.tar.gz
sha256:  <64-hex-chars>

========================================================================
 brain install harness — ready to serve
========================================================================
  staging dir:     /tmp/brain-serve-XXXXX
  port:            9000
  tarball sha256:  <same-sha>

  reachable URLs (try each from the VM):
    http://<host-lan-ip>:9000/install.sh
    http://<host-lan-ip>:9000/install.ps1
    http://<host-lan-ip>:9000/brain-dev.tar.gz
    ...
    http://127.0.0.1:9000/install.sh
    ...

  VM copy-paste (Mac):
    HOST_IP=<host-lan-ip>
    curl -fsSL "http://${HOST_IP}:9000/install.sh" -o install.sh
    ...
```

**Copy the `HOST_IP=…` + the full "VM copy-paste (Mac)" block** — that's
what you'll paste inside the VM. Leave this terminal running; Ctrl+C
stops the server and wipes the staging dir on exit.

If the "reachable URLs" list doesn't include a LAN-looking IP (10.x,
172.16-31.x, 192.168.x), verify your Mac is actually on a network —
the script falls back to `127.0.0.1` only when there's no default
route, which a VM can't reach.

---

## 2. Boot a fresh Mac VM

New terminal on the host:

```bash
# Clone a fresh, disposable VM from the base image.
tart clone ghcr.io/cirruslabs/macos-sonoma-base:latest brain-mac-dryrun

# Boot. Defaults to a shared-network setup so the VM can reach the host's LAN IP.
tart run brain-mac-dryrun
```

The VM window opens with a signed-in `admin` user. Open **Terminal.app**
inside the VM.

Optional but recommended: toggle the VM's "Sharing" → "File Sharing" so
you can drop screenshots from the VM back onto the host via a shared
folder, or use drag-drop.

---

## 3. Verify the VM can reach the host

Inside the **VM's terminal**:

```bash
curl -fsSL "http://<HOST_IP>:9000/manifest.json" | head -20
```

You should see the JSON manifest printed. If not:

- Try `curl -v http://<HOST_IP>:9000/install.sh` to see the full
  transport error.
- Fall back to Tart's host-only IP: `tart ip brain-mac-dryrun` on the
  host prints the VM's IP; the host is usually reachable at the same
  subnet's `.1`.
- Restart Tart with `tart stop brain-mac-dryrun && tart run
  brain-mac-dryrun` to refresh the network config.

---

## 4. Run the install inside the VM

Copy-paste this block **inside the VM terminal**, replacing `<HOST_IP>`
with the value from step 1. Every command writes a log file — those
go straight into the receipt.

```bash
HOST_IP=<HOST_IP>  # e.g. 10.0.0.42

mkdir -p ~/brain-dryrun && cd ~/brain-dryrun

# 4a. Fetch install.sh
curl -fsSL "http://${HOST_IP}:9000/install.sh" -o install.sh

# 4b. Run install.sh pointed at the served tarball
BRAIN_RELEASE_URL="http://${HOST_IP}:9000/brain-dev.tar.gz" \
  bash install.sh 2>&1 | tee install-output.log

# 4c. Diagnostic
brain doctor 2>&1 | tee doctor-output.log
```

Expected end-state:

- `install-output.log` ends with `brain installed. Run 'brain start'…`
- `brain doctor` reports mostly PASS. **Token file + config checks may
  FAIL pre-setup — that's expected**; they go green after the wizard.

**Screenshot #1** — full terminal with the "brain installed" footer visible.

**Screenshot #2** — `brain doctor` output, whatever colour it lands on.

---

## 5. Walk the setup wizard

Still inside the VM:

```bash
brain start 2>&1 | tee start-output.log &
```

Safari opens at `http://localhost:4317/setup`. If the browser didn't
open, open Safari manually and navigate there.

Walk the wizard:

1. **Welcome** — click Continue.
2. **Vault location** — keep default (`~/Documents/brain`). Continue.
3. **API key** — leave empty (we're running FakeLLM) or paste a real
   Anthropic key. Continue.
4. **Theme** — pick any. Continue.
5. **BRAIN.md seed** — pick the default template. Continue.
6. **Claude Desktop** — skip. Click "Start using brain".

You land on `/chat`.

**Screenshot #3** — the browser with the setup wizard visible (step 1
or 2 is the cleanest shot).

**Screenshot #4** — the `/chat` page after wizard completion.

---

## 6. Do one ingest round-trip

In the `/chat` composer, type:

```
Please remember: our coffee provider is Blue Bottle, and we order the
Hayes Valley Espresso blend in 1lb bags monthly.
```

Send. Wait for the response + the patch to appear in `/pending`.

Open `/pending`. Click Approve on the new patch.

Back in a VM terminal, verify the file landed on disk:

```bash
find ~/Documents/brain -name "*.md" -mmin -5 -print
```

**Screenshot #5** — `/pending` showing the approved patch (or a disk
listing of the newly-written note).

---

## 7. Clean shutdown + uninstall

Inside the VM:

```bash
brain stop 2>&1 | tee stop-output.log

# Sanity: nothing left running.
ps aux | grep -i brain_api | grep -v grep || echo "no orphans"

# Uninstall code + Claude Desktop MCP entry. --yes skips prompts but
# keeps the vault by default.
brain uninstall --yes 2>&1 | tee uninstall-output.log
```

Verify:

- `~/Applications/brain/` is gone.
- `~/Documents/brain/` still exists (vault sacred).
- `which brain` prints nothing (shim removed from PATH).

**Screenshot #6** — terminal showing `brain uninstall` summary + the
vault dir still present.

---

## 8. Copy logs + screenshots back to the host

Any of these paths work:

- **Shared folder** — easiest if you enabled it at VM boot.
- **scp** from host: `scp -r vm-ip:~/brain-dryrun/*.log
  ~/Code/cj-llm-kb/docs/testing/clean-mac-vm-logs/`
- **Drag-drop** — Tart supports file drag from the VM window onto
  Finder on the host.

Drop all six screenshots into
`~/Code/cj-llm-kb/docs/testing/screenshots/mac/` using these names:

```
01-install-complete.png
02-doctor-output.png
03-wizard.png
04-chat-empty.png
05-pending-approved.png
06-uninstall-complete.png
```

---

## 9. Fill in the receipt

Open `docs/testing/clean-mac-vm-receipt.md`. Fill every `<fill me in>`
block using the matching log file:

| Receipt section                   | Source file          |
| --------------------------------- | -------------------- |
| Step 4 — install.sh output        | `install-output.log` |
| Step 4 — doctor output            | `doctor-output.log`  |
| Step 5 — `brain start` output     | `start-output.log`   |
| Step 7 — `brain stop` output      | `stop-output.log`    |
| Step 7 — `brain uninstall` output | `uninstall-output.log` |

Note any deviations + bugs. Set the final Status line at the bottom
(PASS / PASS WITH NOTES / FAIL).

Commit everything together:

```bash
git add docs/testing/clean-mac-vm-receipt.md \
        docs/testing/screenshots/mac/
git commit -m "test(plan-08): clean-Mac VM dry run receipt"
```

---

## 10. Tear down

Inside the VM: shut down with Apple menu → Shut Down, or `sudo
shutdown -h now`.

On the host:

```bash
# Stop the serve script (Ctrl+C in its terminal).
tart delete brain-mac-dryrun   # Only after you've saved the receipt.
```

The `tart delete` discards the VM image — you always start from a
pristine base image next time, which is the whole point of a
clean-VM dry run.

# Dry-run screenshots

Drop PNGs captured during clean-VM dry runs here, under:

- `mac/` — captures from `clean-mac-vm-host-instructions.md`
- `windows/` — captures from `clean-windows-vm-host-instructions.md`

Expected filenames per run:

```
NN-short-name.png
```

where `NN` is the step number from the host-instructions doc and
`short-name` matches the receipt template's image reference.

Current expected set (per OS):

- `01-install-complete.png`
- `02-doctor-output.png`
- `03-wizard.png`
- `04-chat-empty.png`
- `05-pending-approved.png`
- `06-uninstall-complete.png`

Add extras (e.g. `07-ingest-in-progress.png`) as needed; just update
the matching receipt to reference them.

PNG only. Keep individual files ≤1 MB (crop + compress — don't commit
full-screen shots). Never commit real personal content in a
screenshot; use the synthetic prompt from the host instructions.

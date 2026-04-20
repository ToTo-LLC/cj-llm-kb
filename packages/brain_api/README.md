# brain_api

FastAPI REST + WebSocket backend for the brain personal knowledge base. Thin
wrapper around `brain_core` primitives; Plan 05 lands the skeleton, auth,
tool dispatcher, and WebSocket chat. Plan 08 wires `brain start` to launch
this under uvicorn.

## Running manually

For local development you can launch the app directly with uvicorn:

```bash
uv run uvicorn --factory brain_api:create_app --host 127.0.0.1 --port 4317
```

`create_app` takes `vault_root` and `allowed_domains`; to pass those via a
factory wrapper, write a tiny local script or wait for Plan 08 (`brain start`).

Intended entry point once Plan 08 lands: `brain start` (from `brain_cli`).

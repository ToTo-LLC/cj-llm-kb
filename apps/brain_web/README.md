# brain_web

Next.js 15 App Router frontend for the `brain` LLM-maintained personal knowledge base. This is the minimal Task 6 skeleton: a placeholder `/chat` page, strict TypeScript, Tailwind directives, and one Vitest smoke test. Design tokens, shadcn primitives, typed API clients, the chat shell, and auth land in Tasks 7 and beyond.

## Dev

```bash
cd apps/brain_web
pnpm dev
```

Visit `http://localhost:4316`. The root redirects to `/chat`.

## Build

```bash
pnpm build
pnpm start
```

Production server listens on `http://localhost:4316`.

## Notes

- Ports are intentional: `4316` = web, `4317` = `brain_api`. Plan 08 wraps both under `brain start`.
- No design tokens, shadcn, auth proxy, or typed API clients yet — Tasks 7–10 layer those in.
- Tests: `pnpm test` (Vitest + Testing Library). Playwright e2e is owned by `brain-test-engineer`, not this skeleton.

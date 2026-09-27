# Ferry — web

The proof dashboard for Ferry: fixes audited, decisions cited, and every backport proven with
tests, rendered from the real run data in `results/ferry-state/` and `metrics.json`.

## Run locally

```bash
cd web
npm install
npm run dev
```

This starts the Vite dev server (`predev` syncs the latest run data into `src/data/` first).

Other scripts:

```bash
npm run build      # type-checks and builds to dist/
npm run preview    # serves the production build locally
npm run typecheck  # tsc only, no build
npm run lint       # eslint
```

## Data

`scripts/sync-data.mjs` copies `results/ferry-state/{plan,results,audit,try}.json`,
`results/ferry-state/ports/*.json` and the repo-root `metrics.json` into `src/data/` before every
dev/build. If the repo-root data isn't present (e.g. a deploy host that only has `web/` checked
out), the sync step logs a warning and keeps whatever is already in `src/data/` — it never fails
the build.

## Deploy (Vercel)

1. New Project → import this repository.
2. Root Directory: `web`
3. Framework Preset: Vite
4. Build Command: `npm run build`
5. Output Directory: `dist`

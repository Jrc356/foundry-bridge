# Frontend Development

Frontend for Foundry Bridge, built with React, TypeScript, Vite, and React Query.

## Prerequisites

- Node.js and npm
- Running backend API at `http://localhost:8767` for local development

## Install

```bash
cd frontend
npm install
```

## Run

```bash
npm run dev
```

The Vite dev server runs on `http://localhost:5173`.

## API proxy

Vite proxies `/api` requests to `http://localhost:8767` (see `frontend/vite.config.ts`).

## Scripts

|Command|Description|
|---|---|
|`npm run dev`|Start development server|
|`npm run build`|Type-check and build production assets|
|`npm run preview`|Preview built assets locally|
|`npm run lint`|Run ESLint|

## Key frontend paths

|Path|Purpose|
|---|---|
|`frontend/src/pages`|Main page-level views|
|`frontend/src/pages/tabs`|Data tabs for game detail views|
|`frontend/src/components`|Reusable UI components|
|`frontend/src/api.ts`|API client wrappers|
|`frontend/src/types.ts`|Shared API/data types|

## Related docs

- [../docs/how-to/local-development.md](../docs/how-to/local-development.md)
- [../docs/reference/api.md](../docs/reference/api.md)
- [../docs/architecture.md](../docs/architecture.md)

# Blood on the Clocktower AI

This repository combines a deterministic Trouble Brewing rules engine with an isolated AI player and Storyteller bridge.

## Components

- `discord-botc/` — authoritative game rules, role abilities, information resolution, nominations, voting, deaths, and win conditions.
- `clocktower-ai/` — AI player transport and model-facing player interface.
- `bridge/` — local integration runner, isolated player contexts, Storyteller decisions, strategy guidance, semantic memory, logs, and offline fixtures.

The default execution rule is strict majority: `floor(alive / 2) + 1`. With 12 alive players, an execution requires 7 votes.

## Setup

Install dependencies in `discord-botc/` and `clocktower-ai/`, then build both TypeScript projects. Copy `bridge/.env.example` to `bridge/.env` and configure an OpenAI-compatible endpoint only for live model runs. Never commit credentials.

## Verification

From the repository root:

```text
node bridge/test.cjs
node bridge/role-strategy-test.cjs
node bridge/information-generator-test.cjs
node bridge/semantic-test.cjs
./bridge/build.ps1
```

Offline fixture runs use `node bridge/run.cjs --fixture`. Live model runs require explicit `--allow-live-models` and write complete per-run logs under `bridge/runs/` locally.

Each run uses a cryptographically generated random seed by default. Set `BOTC_SEED` explicitly when a role assignment and game need to be reproduced.

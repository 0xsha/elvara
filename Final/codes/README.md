# Elvara Single-Chain Intent PoC

This repo contains the minimal end-to-end PoC for the Elvara paper. It connects the notebook research flow, the offchain intent service, and the onchain registry into one reproducible path.

## Repo Map

- `notebooks/`: research notebook and saved paper-facing outputs
- `contracts/`: Foundry contract, tests, and deploy script
- `offchain/`: extracted optimizer, CLI/API, SQLite store, and relayer

## Use The Right Path

- `sample` / `useSample: true`: exact paper reproduction path
- live fixed-window mode: recompute the historical optimizer path from downloaded data
- `today` / `useToday: true`: exploratory only, not for the paper

## Quick Links

- `notebooks/main.ipynb`: main research notebook
- `notebooks/README.md`: notebook notes
- `contracts/README.md`: build, test, deploy, and query commands
- `offchain/README.md`: install, CLI/API usage, and the full local Anvil demo
- `offchain/examples/sample-intent.json`: canonical deterministic paper artifact

## Results Snapshot

- fixed-window notebook result: `CVaR` remains the main strategy winner
- key comparison: `CVaR` vs `Equal Weight`

| Strategy | Final Value | Total Return | Max Drawdown | Sharpe | Cost Drag |
|---|---:|---:|---:|---:|---:|
| `CVaR` | `$1,637,033` | `63.7%` | `-9.7%` | `1.18` | `0.23%` |
| `Equal Weight` | `$1,553,527` | `55.4%` | `-10.3%` | `1.08` | `0.15%` |

## Fastest Paper Reproduction

From `codes/`:

```bash
cd offchain
uv sync
uv run python -m elvara_offchain.cli generate-intent --strategy CVaR --sample --output examples/sample-intent.json
```

This writes the deterministic paper artifact. For the full local relay/onchain demo, follow `offchain/README.md`. For contract-specific commands, use `contracts/README.md`.

## Reproducibility Notes

- the deterministic paper artifact lives at `offchain/examples/sample-intent.json`
- the notebook's data download window ends at `2026-03-03`
- the reported base out-of-sample evaluation window ends at `2025-12-03`
- live reruns can drift over time if upstream market data changes

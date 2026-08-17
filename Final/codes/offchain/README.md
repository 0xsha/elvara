# Elvara Offchain PoC

This module turns the notebook research into a small single-chain intent service for the Elvara journal PoC.

For the paper itself, use `sample` mode. It is deterministic and is the exact reproducibility path. Use live mode only for exploratory reruns.

## What It Does

- Runs the portfolio optimizer using the notebook's strategy logic.
- Normalizes portfolio weights into `targetBps` that sum to `10_000`.
- Persists each generated intent in SQLite.
- Optionally relays the exact intent payload to `PortfolioIntentRegistry` onchain.
- Supports both `live` mode and a deterministic `sample` mode derived from the notebook's published outputs.

## Layout

- `src/elvara_offchain/optimizer.py`: reusable walk-forward optimizer logic
- `src/elvara_offchain/intents.py`: canonical intent artifact builder
- `src/elvara_offchain/storage.py`: SQLite persistence
- `src/elvara_offchain/relay.py`: onchain submission via Web3
- `src/elvara_offchain/server.py`: FastAPI service
- `src/elvara_offchain/cli.py`: CLI for serving and generating intents

## Environment

`.env` is optional.

For local runs, choose one setup method:

- use shell `export` commands if you are running everything from the same terminal session
- copy `.env.example` to `.env` if you want the settings to persist across new terminals

You do not need both.

The relay variables are only required for onchain submission: `ELVARA_RPC_URL`, `ELVARA_PRIVATE_KEY`, and `ELVARA_CONTRACT_ADDRESS`.

## Install

```bash
cd codes/offchain
uv sync
```

## Tests

```bash
uv run python -m unittest discover -s tests
```

## Run The Server

```bash
uv run python -m elvara_offchain.server
```

## Generate A Deterministic Sample Intent

```bash
uv run python -m elvara_offchain.cli generate-intent --strategy CVaR --sample --output examples/sample-intent.json
```

This is the recommended paper-reproduction command.
It writes the canonical artifact JSON directly to `examples/sample-intent.json`.
The default sample metadata are fixed to `epoch=1`, `createdAt=2026-03-24T00:00:00+00:00`, and `expiry=1893456000`.

## Run A Live Notebook-Derived Intent

```bash
uv run python -m elvara_offchain.cli generate-intent --strategy CVaR --weights-mode last
```

This is not the exact paper artifact path because downloaded market data can drift over time.

## API

- `GET /health`
- `POST /rebalance/run`
- `GET /intents/latest`
- `GET /intents/{epoch}`

Example request:

```bash
curl -X POST http://127.0.0.1:8000/rebalance/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "CVaR",
    "useSample": true,
    "weightsMode": "avg",
    "submitOnchain": false
  }'
```

Live request using today's date as the optimizer end date:

```bash
curl -X POST http://127.0.0.1:8000/rebalance/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "CVaR",
    "useToday": true,
    "weightsMode": "last",
    "submitOnchain": false
  }'
```

`useToday` and `useSample` are mutually exclusive.

On a fresh local chain, the canonical sample can be relayed as epoch `1`.
If you need to replay the same sample on a chain that already has epoch `1`, pass `--epoch <next_epoch>` or restart Anvil.

Only `examples/sample-intent.json` is intentionally kept as a checked-in example artifact.

## Local Paper Demo

Use the default Anvil dev accounts only for local testing.

Start a fresh local chain in `codes/contracts`:

```bash
cd codes/contracts
anvil
```

In a second terminal, deploy `PortfolioIntentRegistry` with Anvil account `0` as the owner and Anvil account `1` as the authorized optimizer:

```bash
cd codes/contracts
export OWNER_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
export OPTIMIZER=0x70997970C51812dc3A010C7d01b50e0d17dc79C8

forge script script/DeployPortfolioIntentRegistry.s.sol:DeployPortfolioIntentRegistry \
  --rpc-url http://127.0.0.1:8545 \
  --private-key "$OWNER_PRIVATE_KEY" \
  --broadcast
```

The deploy output prints the registry address on a line like:

```text
PortfolioIntentRegistry deployed at 0x5FbDB2315678afecb367f032d93F642f64180aa3
```

Copy the `0x...` value from that line.

In `codes/offchain`, choose one relay configuration method. Use either option A or option B, not both.

Option A: use shell exports for the current terminal.

```bash
cd codes/offchain
export ELVARA_RPC_URL=http://127.0.0.1:8545
export ELVARA_PRIVATE_KEY=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
export ELVARA_CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3
```

If your deploy output printed a different registry address, replace the `ELVARA_CONTRACT_ADDRESS` value above with the exact `0x...` address from that output.

Option B: use a `.env` file that will keep working in new terminals.

```bash
cd codes/offchain
cp .env.example .env
```

Then open `.env` and replace:

```text
ELVARA_CONTRACT_ADDRESS=
```

with:

```text
ELVARA_CONTRACT_ADDRESS=0x...
```

using the exact address printed by the deploy command.

Run the deterministic paper artifact path from the CLI:

```bash
uv run python -m elvara_offchain.cli generate-intent \
  --strategy CVaR \
  --sample \
  --output examples/sample-intent.json
```

Relay the same deterministic sample onchain:

```bash
uv run python -m elvara_offchain.cli generate-intent \
  --strategy CVaR \
  --sample \
  --submit-onchain
```

Run the API server:

```bash
uv run python -m elvara_offchain.server
```

In another terminal, create the deterministic sample through the API:

```bash
curl -X POST http://127.0.0.1:8000/rebalance/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "CVaR",
    "useSample": true,
    "weightsMode": "avg",
    "submitOnchain": true
  }'
```

Run a live notebook-derived intent from the CLI:

```bash
uv run python -m elvara_offchain.cli generate-intent \
  --strategy CVaR \
  --weights-mode last
```

Use today's date for the live run from the CLI:

```bash
uv run python -m elvara_offchain.cli generate-intent \
  --strategy CVaR \
  --weights-mode last \
  --today
```

Or use today's date through the API:

```bash
curl -X POST http://127.0.0.1:8000/rebalance/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "CVaR",
    "useToday": true,
    "weightsMode": "last",
    "submitOnchain": false
  }'
```

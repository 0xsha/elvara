## Elvara Intent Registry

This Foundry project contains the minimal onchain component for the single-chain Elvara paper PoC.

## Contracts

- `src/PortfolioIntentRegistry.sol`: authenticated registry for rebalance intents

## What It Validates

- only the owner or configured optimizer can publish an intent
- asset and weight arrays must match
- the portfolio must sum to `10_000` basis points
- the intent must have a future expiry
- each epoch must be strictly greater than the last published epoch

## Commands

### Build

```shell
forge build
```

### Test

```shell
forge test
```

### Run Anvil

```shell
anvil
```

### Deploy Locally

Set an optimizer address first:

```shell
export OPTIMIZER=0xYourOptimizerAddress
forge script script/DeployPortfolioIntentRegistry.s.sol:DeployPortfolioIntentRegistry --rpc-url http://127.0.0.1:8545 --private-key <your_private_key> --broadcast
```

### Query The Latest Epoch

```shell
cast call <registry_address> "latestEpoch()(uint64)" --rpc-url http://127.0.0.1:8545
```

from __future__ import annotations

from dataclasses import dataclass

from eth_abi import encode
from hexbytes import HexBytes
from web3 import Web3

from .config import OffchainSettings
from .models import IntentArtifact


PORTFOLIO_INTENT_REGISTRY_ABI = [
    {
        "type": "function",
        "name": "submitIntent",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "epoch", "type": "uint64"},
            {"name": "assets", "type": "address[]"},
            {"name": "targetBps", "type": "uint16[]"},
            {"name": "expiry", "type": "uint64"},
            {"name": "metadataHash", "type": "bytes32"},
        ],
        "outputs": [{"name": "intentHash", "type": "bytes32"}],
    }
]


@dataclass(slots=True)
class RelayResult:
    tx_hash: str
    intent_hash: str
    contract_address: str


def compute_intent_hash(artifact: IntentArtifact) -> str:
    checksum_assets = [Web3.to_checksum_address(asset.address) for asset in artifact.assets]
    encoded = encode(
        ["uint64", "address[]", "uint16[]", "uint64", "bytes32"],
        [
            artifact.epoch,
            checksum_assets,
            artifact.target_bps,
            artifact.expiry,
            bytes(HexBytes(artifact.metadata_hash)),
        ],
    )
    return Web3.keccak(encoded).to_0x_hex()


class PortfolioIntentRegistryRelay:
    def __init__(self, settings: OffchainSettings) -> None:
        if not settings.relay_enabled:
            raise ValueError(
                "Relay requires ELVARA_RPC_URL, ELVARA_PRIVATE_KEY, and ELVARA_CONTRACT_ADDRESS."
            )

        self.settings = settings
        self.web3 = Web3(Web3.HTTPProvider(settings.rpc_url))
        self.account = self.web3.eth.account.from_key(settings.private_key)
        self.contract_address = Web3.to_checksum_address(settings.contract_address)
        self.contract = self.web3.eth.contract(
            address=self.contract_address,
            abi=PORTFOLIO_INTENT_REGISTRY_ABI,
        )

    def publish(self, artifact: IntentArtifact) -> RelayResult:
        checksum_assets = [Web3.to_checksum_address(asset.address) for asset in artifact.assets]
        intent_hash = compute_intent_hash(artifact)
        nonce = self.web3.eth.get_transaction_count(self.account.address)
        gas_price = self.web3.eth.gas_price

        function_call = self.contract.functions.submitIntent(
            artifact.epoch,
            checksum_assets,
            artifact.target_bps,
            artifact.expiry,
            HexBytes(artifact.metadata_hash),
        )

        gas_estimate = function_call.estimate_gas({"from": self.account.address})
        transaction = function_call.build_transaction(
            {
                "chainId": self.web3.eth.chain_id,
                "from": self.account.address,
                "nonce": nonce,
                "gas": int(gas_estimate * 1.2),
                "gasPrice": gas_price,
            }
        )

        signed = self.account.sign_transaction(transaction)
        tx_hash = self.web3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status != 1:
            raise RuntimeError("Intent submission transaction reverted onchain.")

        artifact.intent_hash = intent_hash
        artifact.contract_address = self.contract_address
        artifact.tx_hash = tx_hash.hex()

        return RelayResult(
            tx_hash=artifact.tx_hash,
            intent_hash=intent_hash,
            contract_address=self.contract_address,
        )

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract PortfolioIntentRegistry {
    uint256 internal constant TOTAL_BPS = 10_000;

    struct IntentRecord {
        bytes32 intentHash;
        bytes32 metadataHash;
        uint64 submittedAt;
        uint64 expiry;
    }

    address public owner;
    address public optimizer;
    uint64 public latestEpoch;
    bytes32 public latestIntentHash;

    mapping(uint64 => IntentRecord) public intents;

    event OptimizerUpdated(address indexed optimizer);
    event IntentSubmitted(
        uint64 indexed epoch,
        address indexed submitter,
        bytes32 indexed intentHash,
        bytes32 metadataHash,
        address[] assets,
        uint16[] targetBps,
        uint64 expiry
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    modifier onlyAuthorized() {
        require(msg.sender == owner || msg.sender == optimizer, "not auth");
        _;
    }

    constructor(address initialOptimizer) {
        require(initialOptimizer != address(0), "zero optimizer");
        owner = msg.sender;
        optimizer = initialOptimizer;
        emit OptimizerUpdated(initialOptimizer);
    }

    function setOptimizer(address newOptimizer) external onlyOwner {
        require(newOptimizer != address(0), "zero optimizer");
        optimizer = newOptimizer;
        emit OptimizerUpdated(newOptimizer);
    }

    function computeIntentHash(
        uint64 epoch,
        address[] calldata assets,
        uint16[] calldata targetBps,
        uint64 expiry,
        bytes32 metadataHash
    ) public pure returns (bytes32) {
        return keccak256(abi.encode(epoch, assets, targetBps, expiry, metadataHash));
    }

    function submitIntent(
        uint64 epoch,
        address[] calldata assets,
        uint16[] calldata targetBps,
        uint64 expiry,
        bytes32 metadataHash
    ) external onlyAuthorized returns (bytes32 intentHash) {
        uint256 length = assets.length;
        require(length != 0, "empty");
        require(length == targetBps.length, "len");
        require(epoch > latestEpoch, "epoch");
        require(expiry > block.timestamp, "expired");

        uint256 total;
        for (uint256 i = 0; i < length; ++i) {
            require(assets[i] != address(0), "zero asset");
            total += targetBps[i];
        }
        require(total == TOTAL_BPS, "sum");

        intentHash = computeIntentHash(epoch, assets, targetBps, expiry, metadataHash);

        latestEpoch = epoch;
        latestIntentHash = intentHash;
        intents[epoch] = IntentRecord({
            intentHash: intentHash,
            metadataHash: metadataHash,
            submittedAt: uint64(block.timestamp),
            expiry: expiry
        });

        emit IntentSubmitted(
            epoch,
            msg.sender,
            intentHash,
            metadataHash,
            assets,
            targetBps,
            expiry
        );
    }
}

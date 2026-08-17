// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";

import {PortfolioIntentRegistry} from "../src/PortfolioIntentRegistry.sol";

contract PortfolioIntentRegistryTest is Test {
    event IntentSubmitted(
        uint64 indexed epoch,
        address indexed submitter,
        bytes32 indexed intentHash,
        bytes32 metadataHash,
        address[] assets,
        uint16[] targetBps,
        uint64 expiry
    );

    PortfolioIntentRegistry internal registry;

    address internal constant OPTIMIZER = address(0xBEEF);
    address internal constant NEW_OPTIMIZER = address(0xCAFE);

    function setUp() public {
        vm.warp(1_700_000_000);
        registry = new PortfolioIntentRegistry(OPTIMIZER);
    }

    function test_submitIntentStoresLatestEpochAndHash() public {
        address[] memory assets = _assets();
        uint16[] memory targetBps = _validWeights();
        bytes32 metadataHash = keccak256("metadata");
        uint64 expiry = uint64(block.timestamp + 1 days);
        bytes32 expectedHash = registry.computeIntentHash(
            1,
            assets,
            targetBps,
            expiry,
            metadataHash
        );

        vm.expectEmit(true, true, true, true);
        emit IntentSubmitted(
            1,
            OPTIMIZER,
            expectedHash,
            metadataHash,
            assets,
            targetBps,
            expiry
        );

        vm.prank(OPTIMIZER);
        bytes32 actualHash = registry.submitIntent(
            1,
            assets,
            targetBps,
            expiry,
            metadataHash
        );

        assertEq(actualHash, expectedHash);
        assertEq(registry.latestEpoch(), 1);
        assertEq(registry.latestIntentHash(), expectedHash);

        (
            bytes32 storedIntentHash,
            bytes32 storedMetadataHash,
            uint64 submittedAt,
            uint64 storedExpiry
        ) = registry.intents(1);

        assertEq(storedIntentHash, expectedHash);
        assertEq(storedMetadataHash, metadataHash);
        assertEq(submittedAt, uint64(block.timestamp));
        assertEq(storedExpiry, expiry);
    }

    function test_submitIntentRejectsUnauthorizedCaller() public {
        vm.prank(address(0x1234));
        vm.expectRevert(bytes("not auth"));
        registry.submitIntent(
            1,
            _assets(),
            _validWeights(),
            uint64(block.timestamp + 1 days),
            keccak256("metadata")
        );
    }

    function test_submitIntentRejectsInvalidWeightSum() public {
        address[] memory assets = _assets();
        uint16[] memory targetBps = new uint16[](3);
        targetBps[0] = 4_000;
        targetBps[1] = 3_000;
        targetBps[2] = 2_000;

        vm.prank(OPTIMIZER);
        vm.expectRevert(bytes("sum"));
        registry.submitIntent(
            1,
            assets,
            targetBps,
            uint64(block.timestamp + 1 days),
            keccak256("metadata")
        );
    }

    function test_submitIntentRejectsExpiredIntent() public {
        vm.prank(OPTIMIZER);
        vm.expectRevert(bytes("expired"));
        registry.submitIntent(
            1,
            _assets(),
            _validWeights(),
            uint64(block.timestamp),
            keccak256("metadata")
        );
    }

    function test_submitIntentRejectsEpochReplay() public {
        address[] memory assets = _assets();
        uint16[] memory targetBps = _validWeights();
        bytes32 metadataHash = keccak256("metadata");
        uint64 expiry = uint64(block.timestamp + 1 days);

        vm.prank(OPTIMIZER);
        registry.submitIntent(1, assets, targetBps, expiry, metadataHash);

        vm.prank(OPTIMIZER);
        vm.expectRevert(bytes("epoch"));
        registry.submitIntent(1, assets, targetBps, expiry, metadataHash);
    }

    function test_onlyOwnerCanUpdateOptimizer() public {
        vm.prank(OPTIMIZER);
        vm.expectRevert(bytes("not owner"));
        registry.setOptimizer(NEW_OPTIMIZER);

        registry.setOptimizer(NEW_OPTIMIZER);
        assertEq(registry.optimizer(), NEW_OPTIMIZER);
    }

    function _assets() internal pure returns (address[] memory assets) {
        assets = new address[](3);
        assets[0] = address(0x1);
        assets[1] = address(0x2);
        assets[2] = address(0x3);
    }

    function _validWeights() internal pure returns (uint16[] memory targetBps) {
        targetBps = new uint16[](3);
        targetBps[0] = 5_000;
        targetBps[1] = 3_000;
        targetBps[2] = 2_000;
    }
}

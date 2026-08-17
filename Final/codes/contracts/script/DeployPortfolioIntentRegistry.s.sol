// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";

import {PortfolioIntentRegistry} from "../src/PortfolioIntentRegistry.sol";

contract DeployPortfolioIntentRegistry is Script {
    function run() external returns (PortfolioIntentRegistry registry) {
        address optimizer = vm.envAddress("OPTIMIZER");

        vm.startBroadcast();
        registry = new PortfolioIntentRegistry(optimizer);
        vm.stopBroadcast();

        console2.log("PortfolioIntentRegistry deployed at", address(registry));
    }
}

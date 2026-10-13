// SPDX-License-Identifier: MIT
// I20-B toy harness (tests_m2/test_i20_refine_unit.py): the generic step harness on the planted Ledger.
// holonDeploy deploys a programmable gate (the dependency) and the real Ledger; init = [fee, allowed callers...].
pragma solidity =0.8.24;

import {HolonStepBase} from "./HolonStepBase.sol";
import {Ledger, IGate} from "../src/Ledger.sol";

contract HolonToyGate is IGate {
    mapping(address => bool) public allowed;
    uint256 public fee;

    function set(address who, bool v) external {
        allowed[who] = v;
    }

    function setFee(uint256 f) external {
        fee = f;
    }
}

contract HolonToyStepTest is HolonStepBase {
    function holonDeploy(uint256, uint256[] memory init) internal override returns (address) {
        HolonToyGate g = new HolonToyGate();
        if (init.length > 0) g.setFee(init[0]);
        for (uint256 i = 1; i < init.length; i++) g.set(address(uint160(init[i])), true);
        return address(new Ledger(g));
    }
}

contract HolonToyLastTest is HolonToyStepTest {
    function setUp() public {
        holonSetUpLast();
    }

    function test_last() public {
        holonRunLast();
    }
}

// SPDX-License-Identifier: MIT
// I27 toy harness (tests_m3/test_undo.py): the generic step harness (HolonStepBase) on the planted ToyUndo, which has no
// constructor argument and no dependency. Both toy bindings (tests_m3/fixtures/undo/fragments_toy.json and
// tests_m3/fixtures/undo/drop/fragments_toy.json) use it: each scratch project holds its own variant under src/.
pragma solidity =0.8.24;

import {HolonStepBase} from "./HolonStepBase.sol";
import {ToyUndo} from "../src/ToyUndo.sol";

contract HolonToyUndoStepTest is HolonStepBase {
    function holonDeploy(uint256, uint256[] memory) internal override returns (address) {
        return address(new ToyUndo());
    }
}

contract HolonToyUndoLastTest is HolonToyUndoStepTest {
    function setUp() public {
        holonSetUpLast();
    }

    function test_last() public {
        holonRunLast();
    }
}

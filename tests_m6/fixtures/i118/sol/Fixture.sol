// SPDX-License-Identifier: UNLICENSED
// I118 planted fixture (tests_m6/test_i118_post_derive_walls.py), compiled by the pinned solc 0.8.24.
//   Counter   well formed for every stage: the neighbour of the cross-document shapes.
//   Guarded   well formed for every stage; its DISCH laws (blocking and revert) are decided. It is the control of
//             every shape, and the planted document of each one:
//               coverage: Guarded's extraction sidecar names a term budget its walk exceeds, so it is not extracted
//                         (the frontend refuses it) while its sidecar stays with the others, as the composed driver
//                         leaves a failed extraction's sidecar;
//               run:      Guarded's entry is taken out of gen/<M>/coverage.json before the run step, so the record
//                         writer refuses every law over it (records.coverage_field), and only over it;
//               bind:     Guarded's typed model is taken out of gen/<M>/sorts/models after the run step, so binding
//                         a law over it fails reading its model (an OSError, not a BindingError), and only over it.
//   Dyn       a dynamic storage array of words: the typed model compiles static arrays only, so holon types makes it
//             opaque (class unsupported, I112's opaque classes): the opaque document coverage skips.
pragma solidity 0.8.24;

contract Counter {
    address public owner;
    uint256 public count;

    constructor() {
        owner = msg.sender;
    }

    function bump() external {
        require(count < 10, "cap");
        count += 1;
    }

    function reset() external {
        require(msg.sender == owner, "owner");
        count = 0;
    }
}

contract Guarded {
    address public owner;
    uint256 public level;

    constructor() {
        owner = msg.sender;
    }

    function raise() external {
        require(level < 5, "top");
        level += 1;
    }

    function clear() external {
        require(msg.sender == owner, "owner");
        level = 0;
    }
}

contract Dyn {
    address public owner;
    uint256 public count;
    uint256[] public items;

    constructor() {
        owner = msg.sender;
    }

    function bump() external {
        require(count < 10, "cap");
        count += 1;
    }

    function push(uint256 v) external {
        require(msg.sender == owner, "owner");
        items.push(v);
    }
}

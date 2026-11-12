// SPDX-License-Identifier: UNLICENSED
// I112 planted fixture (tests_m6/test_i112_run_wall.py), compiled by the pinned solc 0.8.24.
//   Counter     well typed: the typed neighbour of the cross-document shape.
//   Packed      label() hashes abi.encodePacked of a storage string; the typed model takes each packed word's width
//               from its elementary type (holon.extracted_eval._packed_width), and a string is none, so its
//               generation raises holon.extracted_eval.Unsupported: class unsupported.
//   PackedKept  Packed without label(): the constrained-state control.
//   LayoutKept  a struct-valued state variable; tools/i112_fixture.py plants Layout from its compiled document by
//               moving one field's offset off the compiler's member layout: class member_layout.
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

contract Packed {
    address public owner;
    uint256 public count;

    constructor() {
        owner = msg.sender;
    }
    bytes32 public tag;
    string public name;

    function bump() external {
        require(count < 10, "cap");
        count += 1;
    }

    function label() external {
        tag = keccak256(abi.encodePacked(name));
    }

    function reset() external {
        require(msg.sender == owner, "owner");
        count = 0;
    }
}

contract PackedKept {
    address public owner;
    uint256 public count;

    constructor() {
        owner = msg.sender;
    }
    bytes32 public tag;
    string public name;

    function bump() external {
        require(count < 10, "cap");
        count += 1;
    }

    function reset() external {
        require(msg.sender == owner, "owner");
        count = 0;
    }
}

contract LayoutKept {
    address public owner;
    struct Entry {
        bool on;
        uint32 at;
        uint256 amount;
    }

    Entry public entry;
    uint256 public count;

    constructor() {
        owner = msg.sender;
    }

    function set(uint256 a) external {
        require(!entry.on, "set");
        entry.on = true;
        entry.amount = a;
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

// SPDX-License-Identifier: UNLICENSED
// I116 planted fixture (tests_m6/test_i116_per_document_fallbacks.py), compiled by the pinned solc 0.8.24.
//   Counter     well formed for every stage: the neighbour of the cross-document shapes.
//   Twice       two writing actions check the same permission predicate (msg.sender == owner) inline, each at its own
//               span. DISCH's D2 names an inline permission class by its check's span, so the two actions give two
//               classes with one predicate, which D2 refuses (holon.analysis.closure.ClassError): a per-document
//               DISCH refusal.
//   TwiceKept   Twice without its second inline-guarded action (drain): the DISCH control.
//   Listed      a dynamic storage array written by index; E2 over a transitions document maps map and member path
//               segments only (holon.diagram.transitions, rule Z1), so its evidence refuses the document
//               (TransitionsError): a per-document evidence refusal, which derive meets when it rebuilds the set.
//   ListedKept  Listed without the array: the evidence control.
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

contract Twice {
    address public owner;
    uint256 public count;
    uint256 public fee;

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

    function drain() external {
        require(msg.sender == owner, "owner");
        fee = 0;
    }
}

contract TwiceKept {
    address public owner;
    uint256 public count;
    uint256 public fee;

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

contract Listed {
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

    function reset() external {
        require(msg.sender == owner, "owner");
        count = 0;
    }

    function put(uint256 i, uint256 v) external {
        require(i < items.length, "range");
        items[i] = v;
    }
}

contract ListedKept {
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

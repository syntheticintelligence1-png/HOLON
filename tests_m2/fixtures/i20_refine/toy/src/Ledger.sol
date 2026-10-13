// SPDX-License-Identifier: MIT
// Planted fixture for I20-B (tests_m2/test_i20_refine_unit.py): a contract written for the test, with inherited and
// packed storage, an external dependency, an event, a checked accumulator that panics, and a narrowing store.
pragma solidity =0.8.24;

interface IGate {
    function allowed(address who) external view returns (bool);
    function fee() external view returns (uint256);
}

abstract contract Owned {
    address internal _owner;
    bool internal _paused;

    modifier onlyOwner() {
        require(msg.sender == _owner, "not owner");
        _;
    }

    modifier whenNotPaused() {
        require(!_paused, "paused");
        _;
    }
}

contract Ledger is Owned {
    struct Entry {
        uint64 amount;
        address who;
    }

    error NotYours(uint256 id);

    IGate public gate;
    uint64 public total;
    uint256 public count;
    mapping(uint256 => Entry) public entries;

    event Deposited(address indexed who, uint256 indexed id, uint64 amount);
    event Paused(bool on);

    constructor(IGate g) {
        _owner = msg.sender;
        gate = g;
    }

    function deposit(uint64 amount) external payable whenNotPaused returns (uint256 id) {
        require(gate.allowed(msg.sender), "not allowed");
        require(amount > 0, "zero");
        require(msg.value >= gate.fee(), "fee");
        total += amount;
        id = ++count;
        entries[id] = Entry(amount, msg.sender);
        emit Deposited(msg.sender, id, amount);
    }

    function withdraw(uint256 id) external whenNotPaused {
        Entry memory e = entries[id];
        if (e.who != msg.sender) revert NotYours(id);
        total -= e.amount;
        delete entries[id];
    }

    function setPaused(bool on) external onlyOwner {
        _paused = on;
        emit Paused(on);
    }
}

// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

// Planted fixture for I20 builder A (tests_m2/test_i20_model_unit.py): the extracted model's compiler, evaluator,
// window view, width rule and differential are checked on it. Its semantics are known by construction.

interface IGate {
    function allowed(address who) external view returns (bool);
}

contract Owned {
    address internal _owner;
    bool internal _stopped;

    modifier onlyOwner() {
        require(msg.sender == _owner, "not owner");
        _;
    }

    modifier live() {
        require(!_stopped, "stopped");
        _;
    }
}

contract Book is Owned {
    struct Entry {
        uint64 amount;
        address who;
        uint32 tag;
    }

    error NotYours(uint256 id);
    error Empty();

    event Deposited(address indexed who, uint256 indexed id, uint64 amount);
    event Withdrawn(uint256 id);
    event Stopped(bool on);

    uint64 public total;
    address public gate;
    uint256 public count;
    mapping(uint256 => Entry) public entries;
    bytes32 public last;

    function deposit(uint64 amount) external payable live {
        require(amount > 0, "zero");
        require(IGate(gate).allowed(msg.sender), "denied");
        total += amount;
        count += 1;
        entries[count] = Entry(amount, msg.sender, uint32(count));
        emit Deposited(msg.sender, count, amount);
    }

    function withdraw(uint256 id) external live {
        Entry storage e = entries[id];
        if (e.who != msg.sender) revert NotYours(id);
        total -= e.amount;
        delete entries[id];
        emit Withdrawn(id);
    }

    function setStopped(bool on) external onlyOwner {
        _stopped = on;
        emit Stopped(on);
    }

    function share(uint256 a, uint256 b) external view returns (uint256) {
        return a / b + count % b;
    }

    function seal(uint256 n) external onlyOwner {
        uint256 acc = 0;
        for (uint256 i = 0; i < n; i++) {
            acc += i;
        }
        if (acc == 0) revert Empty();
        last = keccak256(abi.encode(acc, count));
    }

    function stamp(uint256 idx) external onlyOwner {
        uint256 p;
        bytes32 h;
        assembly {
            p := mload(0x40)
            mstore(p, shl(192, idx))
            h := keccak256(p, 8)
        }
        last = h;
    }
}

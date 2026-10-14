// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

// Planted fixture for I31 (tests_m3/test_disch.py), variant a: a permissionless step guarded by a register that a
// keeper jams; the admin clears it, and here anyone may unjam it. Extracted by holon's Solidity frontend. Not a target.
contract ToyGate {
    address internal constant ADMIN = address(0xAD);
    mapping(address => bool) public keeper;
    bool public jammed;
    uint256 public count;
    uint256 public last;

    modifier onlyAdmin() {
        require(msg.sender == ADMIN, "admin");
        _;
    }

    modifier onlyKeeper() {
        require(keeper[msg.sender], "keeper");
        _;
    }

    function enroll(address k) external onlyAdmin {
        keeper[k] = true;
    }

    function jam() external onlyKeeper {
        jammed = true;
    }

    function clear() external onlyAdmin {
        jammed = false;
    }

    function step() external {
        require(!jammed, "jammed");
        count += 1;
    }

    function note(uint256 x) external {
        last = x;
    }

    function unjam() external {
        jammed = false;
    }
}

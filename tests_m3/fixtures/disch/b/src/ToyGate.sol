// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

// Planted fixture for I31 (tests_m3/test_disch.py), variant b: variant a with unjam restricted to the admin, so that no
// permissionless action writes the step's guard register. Same lines as variant a. Extracted by holon's frontend.
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

    function unjam() external onlyAdmin {
        jammed = false;
    }
}

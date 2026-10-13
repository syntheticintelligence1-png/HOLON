// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

// Planted fixture for I30 (tests_m3/test_sort_types.py): one ill-sorted sum, Time + Time (whitepaper §7.2), which has no
// typed operation. Extracted by holon's Solidity frontend. Not a real target.
contract ToyClock {
    uint256 public last;

    function stamp() external {
        last = block.timestamp + block.timestamp;
    }
}

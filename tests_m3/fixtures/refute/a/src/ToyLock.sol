// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

// Planted fixture for I40 (tests_m3/test_refute.py), variant a: a checked signed difference (W + start - block.timestamp)
// that can go negative only at the end of a seven-step chain: arm, then s1 to s5, each requiring the stage the previous
// step set, then fire at a block.timestamp later than arm's. No shorter trace reaches the subtraction with a stage of 6.
// Variant b differs on one line only: fire requires W + start >= block.timestamp first. Extracted by holon's Solidity
// frontend at the I40 prereg. Not a target.
contract ToyLock {
    uint256 public W;
    uint256 public start;
    uint256 public stage;
    uint256 public prt;

    function setW(uint256 w) external {
        W = w;
    }

    function arm() external {
        require(stage == 0, "armed");
        stage = 1;
        start = block.timestamp;
    }

    function s1() external {
        require(stage == 1, "s1");
        stage = 2;
    }

    function s2() external {
        require(stage == 2, "s2");
        stage = 3;
    }

    function s3() external {
        require(stage == 3, "s3");
        stage = 4;
    }

    function s4() external {
        require(stage == 4, "s4");
        stage = 5;
    }

    function s5() external {
        require(stage == 5, "s5");
        stage = 6;
    }

    function fire() external {
        require(stage == 6, "fire");

        prt = W + start - block.timestamp;
    }
}

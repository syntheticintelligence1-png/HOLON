// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

interface IExt {
    function ping() external;
    function ok(address who) external view returns (bool);
}

contract Vault {
    struct S {
        uint64 x;
        address y;
    }

    address public owner;
    address public ext;
    uint256 public total;
    mapping(uint256 => bytes32) public h;
    mapping(uint256 => S) public s;
    bool public paused;

    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    modifier onlyOk() {
        require(IExt(ext).ok(msg.sender), "not ok");
        _;
    }

    function put(uint256 k, uint256 n) external onlyOwner {
        require(!paused, "paused");
        require(k > 0, "k zero");
        uint256 acc = 0;
        for (uint256 i = 0; i < n; i++) {
            acc += i;
        }
        total = total + acc;
        h[k] = keccak256(abi.encode(k, acc));
    }

    function poke() external onlyOk {
        IExt(ext).ping();
    }

    function setPaused(bool p) external onlyOwner {
        paused = p;
    }

    function drain(uint256 n) external onlyOwner {
        while (n > 0) {
            delete h[n];
            n--;
        }
    }
}

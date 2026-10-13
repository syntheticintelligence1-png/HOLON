// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

// Planted fixture for I30 (tests_m3/test_sort_types.py), extracted by holon's Solidity frontend: every typed-sort law
// class on a contract small enough to read by hand, with outcomes known by construction. Not a real target.
//   h      a union register (an aggregate digest at version 2, else a versioned hash), recommitted under any version
//   g, vg  the same union, kept only under the version it was written with
//   commitT / elapsed   a checked signed difference that can go negative / one a require keeps non-negative
//   commitQ             a delay guard that reads the finalization cursor and requires what advances the inclusion cursor
//   sweep               writes inside a loop
contract ToyTypes {
    bytes32 internal constant Z = 0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014;

    mapping(uint256 => bytes32) public h;
    mapping(uint256 => uint256) public hv;
    mapping(uint256 => bytes32) public g;
    mapping(uint256 => uint256) public vg;
    uint256 public W;
    uint256 public start;
    bool public inch;
    uint256 public prt;
    uint256 public el;
    mapping(uint256 => uint256) public enqueueTime;
    uint256 public queueLength;
    uint256 public pendingQueueIndex;
    uint256 public totalQueueIndex;
    uint256 public D;
    mapping(uint256 => uint256) public marks;

    function _digest(uint256 v) internal view returns (bytes32 d) {
        if (v == 2) {
            uint256 n;
            assembly {
                let p := mload(0x40)
                let i := 0
                for {} 1 {} {
                    let b := blobhash(i)
                    if iszero(b) {
                        break
                    }
                    mstore(add(p, mul(i, 32)), b)
                    i := add(i, 1)
                }
                n := i
                d := keccak256(p, mul(i, 32))
                mstore(0x40, add(p, mul(i, 32)))
            }
            require(n > 0, "no blob");
        } else {
            d = (blobhash(0) == bytes32(0)) ? Z : blobhash(0);
        }
    }

    function _store(uint256 k, bytes32 x, uint256 v) internal {
        h[k] = x;
        hv[k] = v;
    }

    function _storeg(uint256 k, bytes32 x, uint256 v) internal {
        g[k] = x;
        vg[k] = v;
    }

    function put(uint256 k, uint8 v) external {
        require(h[k] == bytes32(0), "stored");
        _store(k, _digest(v), v);
    }

    function recommit(uint256 k, uint8 v) external {
        require(blobhash(0) == bytes32(0), "blob");
        bytes32 old = h[k];
        require(old != bytes32(0), "none");
        _store(k, old, v);
    }

    function putg(uint256 k, uint8 v) external {
        _storeg(k, _digest(v), v);
    }

    function keepg(uint256 k, uint8 v) external {
        require(blobhash(0) == bytes32(0), "blob");
        bytes32 kept = g[k];
        require(kept != bytes32(0), "none");
        require(v == vg[k], "version");
        _storeg(k, kept, v);
    }

    function setW(uint256 w) external {
        W = w;
    }

    function challenge() external {
        inch = true;
        start = block.timestamp;
    }

    function commitT() external {
        uint256 r = 0;
        if (inch) {
            r = W + start - block.timestamp;
        }
        prt = r;
    }

    function elapsed() external {
        require(block.timestamp >= start, "early");
        el = block.timestamp - start;
        inch = false;
    }

    function send() external {
        enqueueTime[queueLength] = block.timestamp;
        queueLength += 1;
    }

    function setD(uint256 d) external {
        D = d;
    }

    function finalize() external {
        pendingQueueIndex = totalQueueIndex;
    }

    function _firstEnqueueTime() internal view returns (uint256) {
        if (pendingQueueIndex < queueLength && enqueueTime[pendingQueueIndex] != 0) {
            return enqueueTime[pendingQueueIndex];
        }
        return block.timestamp;
    }

    function commitQ(uint256 n) external {
        if (_firstEnqueueTime() + D < block.timestamp) {
            require(n > 0, "delay");
        }
        totalQueueIndex += n;
    }

    function mark(uint256 k) external {
        marks[k] = block.timestamp;
    }

    function sweep(uint256 from, uint256 count) external {
        for (uint256 i = 0; i < count; i++) {
            delete marks[from + i];
        }
    }
}

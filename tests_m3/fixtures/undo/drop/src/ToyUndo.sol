// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

/// @notice I27 planted fixture (tests_m3/test_undo.py): a cursor-indexed commit and its undo. The undo pair, its
/// residues and their static classification are known by construction. The drop variant
/// (tests_m3/fixtures/undo/drop/src/ToyUndo.sol) is this file without the one line that frees pins in revertLast.
contract ToyUndo {
    uint256 public last; // the cursor: commit advances it, revertLast moves it back
    mapping(uint256 => bytes32) internal entries; // allocated by commit (its guard requires it empty), freed by revertLast
    mapping(uint256 => bytes32) internal roots; // a residue read only at the cursor
    mapping(uint256 => uint256) internal stamps; // a residue read only behind entries[i] != 0
    mapping(uint256 => bytes32) internal pins; // allocated by commit (its guard requires it empty), freed by revertLast

    event Committed(uint256 indexed index, bytes32 indexed entry);
    event Reverted(uint256 indexed index, bytes32 indexed entry);
    event Touched(uint256 indexed index, uint256 stamp);

    function commit(bytes32 entry, bytes32 root, bytes32 pin) external {
        require(entry != bytes32(0), "zero entry");
        uint256 i = last + 1;
        require(entries[i] == bytes32(0), "already committed");
        require(pins[i] == bytes32(0), "pinned");
        require(last == 0 || roots[last] != bytes32(0), "no parent root");
        entries[i] = entry;
        roots[i] = root;
        stamps[i] = block.timestamp;
        pins[i] = pin;
        last = i;
        emit Committed(i, entry);
    }

    function revertLast() external {
        uint256 i = last;
        bytes32 e = entries[i];
        require(e != bytes32(0), "not committed");
        delete entries[i];
        last = i - 1;
        emit Reverted(i, e);
    }

    function touch(uint256 i) external {
        require(entries[i] != bytes32(0), "not committed");
        emit Touched(i, stamps[i]);
    }

    function stampOf(uint256 i) external view returns (bool) {
        return entries[i] != bytes32(0) && stamps[i] > 0;
    }
}

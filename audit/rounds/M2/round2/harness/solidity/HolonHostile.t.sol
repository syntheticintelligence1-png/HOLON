// SPDX-License-Identifier: MIT
// HOLON I21 (audit round M2/2, auditor A2) hostile-input harness, Solidity side (holon/audit/hostile.py; surfaces
// sol_loader and sol_encoder). It compares nothing: it runs every item on the real Rollup and writes what happened.
//
// holon audit hostile copies this file, with replay/M1/solidity/HolonTraceReplay.t.sol of the target tree (the M1
// trace harness: the real Rollup and L1MessageQueueWithGasPriceOracle behind proxies, the submitter and verifier
// stand-ins, the genesis batch), into a scratch Foundry project holding the pinned checkout's contracts/, and runs
//   HOLON_HOSTILE_IN=<in> HOLON_HOSTILE_OUT=<out> forge test --match-contract '^HolonHostileTest$' --offline --use <solc>
//
// States (every item runs from a snapshot of its state and is reverted afterwards):
//   bare     the deployment of the M1 harness without the genesis import (finalizedStateRoots[0] == 0)
//   genesis  bare, then importGenesisBatch(G) by the owner, G the M1 harness's genesis header with post state root r0
//   delay    genesis, then the clock moved past the rollup delay period (commitBatchWithProof's timing check passes)
//   stored   genesis, then commitBatch of batch 1 and revertBatch of it: batch 1's blob hash stays stored
//            (commitState's "no stored blob hash" check passes)
// Reverting to a snapshot deletes every snapshot taken after it (Foundry's revertToState), so the items run in one
// pass per state, in this order: each pass reverts to the bare deployment, builds its state, snapshots it and runs
// the items of that state (the input file is re-read from its start). Output lines carry the item's input index.
// Every item is built so that every check before its compared call site passes: the state, the caller (the owner,
// an active submitter, or anyone), msg.value 0 and the blob hashes.
//
// Input ($HOLON_HOSTILE_IN), one "0x" line each, then a line "0x":
//   first   abi.encode(uint256 F, uint256 W, uint256 D, uint256 t0, bytes32 r0, bytes32 r2): the M1 facts' initial
//           parameters, the genesis post state root (r0) and the valid post state root of built inputs (r2)
//   items   abi.encode(uint8 kind, string entry, uint256 line, bytes payload):
//             kind 1  header through the _loadBatchHeader call at Rollup.sol:<line> of <entry>; payload = the header
//             kind 2  encoder input through <entry>: payload = abi.encode(uint8 version, bytes32 prev, bytes32 post)
//             kind 3  a malformed ABI encoding of kind 1's header argument; payload = abi.encode(uint8 how)
//             kind 4  a malformed ABI encoding of kind 2's input (its parentBatchHeader); payload = abi.encode(uint8 how)
//           how: 0 the argument's length word exceeds the calldata that follows it; 1 the argument's offset word points
//           past the end of the calldata; 2 the calldata ends inside the argument. The argument is located by a probe
//           header (unique bytes) in the calldata kind 1 or 2 would send; its offset word is the head word that points
//           at its length word.
// Output ($HOLON_HOSTILE_OUT): "<k> <ok 0|1> <return or revert data>" per item, then "done <n>".
pragma solidity =0.8.24;

import {HolonTraceReplayTest, HolonVerifierOracle} from "./HolonTraceReplay.t.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";
import {IRollup} from "../contracts/l1/rollup/IRollup.sol";
import {L1MessageQueueWithGasPriceOracle} from "../contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import {HolonSubmitterOracle} from "./HolonTraceReplay.t.sol";

interface HolonHostileVm {
    function snapshotState() external returns (uint256);
    function revertToState(uint256) external returns (bool);
    function prank(address) external;
    function warp(uint256) external;
    function deal(address, uint256) external;
    function blobhashes(bytes32[] calldata) external;
    function readLine(string calldata) external returns (string memory);
    function writeLine(string calldata, string calldata) external;
    function envString(string calldata) external view returns (string memory);
    function parseBytes(string calldata) external pure returns (bytes memory);
    function toString(bytes calldata) external pure returns (string memory);
    function toString(uint256) external pure returns (string memory);
    function pauseGasMetering() external;
    function closeFile(string calldata) external;
}

contract HolonHostileTest is HolonTraceReplayTest {
    HolonHostileVm internal constant XV = HolonHostileVm(address(uint160(uint256(keccak256("hevm cheat code")))));

    uint256 internal constant BARE = 0;
    uint256 internal constant GENESIS = 1;
    uint256 internal constant DELAY = 2;
    uint256 internal constant STORED = 3;
    bytes internal genesisHeader;
    bytes32 internal r0;
    bytes32 internal r2;
    string internal outPath;
    string internal inPath;
    uint256 internal delayPeriod;

    struct Call {
        uint256 state;
        address caller;
        bytes32[] blobs;
        bytes data;
    }

    /// The M1 harness's deployment (HolonTraceReplayTest.deploy) without the genesis import.
    function deployBare(uint256 F_, uint256 W_, uint256 D_, uint256 t0) internal {
        HV.warp(EPOCH + t0);
        sub = new HolonSubmitterOracle();
        sub.setActive(who2addr(2), true);
        sub.setActive(who2addr(3), true);
        HolonVerifierOracle ver = new HolonVerifierOracle();
        Rollup impl = new Rollup(53077);
        rollup = Rollup(payable(address(new TransparentUpgradeableProxy(address(impl), PROXY_ADMIN, ""))));
        L1MessageQueueWithGasPriceOracle qimpl = new L1MessageQueueWithGasPriceOracle(MESSENGER, address(rollup), address(0xE7));
        queue = L1MessageQueueWithGasPriceOracle(address(new TransparentUpgradeableProxy(address(qimpl), PROXY_ADMIN, "")));
        queue.initialize(10_000_000, address(0));
        rollup.initialize(address(sub), address(queue), address(ver), F_, W_, 70);
        rollup.updateRollupDelayPeriod(D_);
        rollup.addChallenger(who2addr(4));
        for (uint256 w = 2; w <= 5; w++) HV.deal(who2addr(w), 100 ether);
    }

    function one(bytes32 b) internal pure returns (bytes32[] memory a) {
        a = new bytes32[](1);
        a[0] = b;
    }

    function none() internal pure returns (bytes32[] memory a) {
        a = new bytes32[](0);
    }

    function input(uint8 v, bytes memory parent, bytes32 prev, bytes32 post)
        internal pure returns (IRollup.BatchDataInput memory) {
        return IRollup.BatchDataInput(v, parent, 1, 0, prev, post, bytes32(0));
    }

    /// Builds state st (BARE, GENESIS, DELAY or STORED) from the bare deployment.
    function buildState(uint256 st, uint256 D_) internal {
        genesisHeader = hdr(0, 0, bytes32(uint256(1)), ZVH, r0);
        if (st == BARE) return;
        rollup.importGenesisBatch(genesisHeader);
        hdrs[0][0] = genesisHeader;
        if (st == DELAY) XV.warp(block.timestamp + D_ + 1);
        if (st != STORED) return;
        // batch 1 committed (version 0, one blob) and reverted: its blob hash stays stored
        XV.blobhashes(one(blobEnc(2)));
        XV.prank(who2addr(2));
        rollup.commitBatch(input(0, genesisHeader, r0, r2));
        XV.blobhashes(none());
        uint256[] memory s = new uint256[](12);
        s[0] = 1; s[1] = 2; s[2] = 0; s[3] = 0; s[4] = 0; s[5] = 1; s[6] = uint256(r0); s[7] = uint256(r2);
        s[8] = 1; s[9] = 2;
        bytes memory h1 = newHeader(0, s, 0, rollup.batchBlobVersionedHashes(1));
        require(keccak256(h1) == rollup.committedBatches(1), "holon hostile: batch 1 header");
        rollup.revertBatch(h1, 1);
        require(rollup.batchBlobVersionedHashes(1) != bytes32(0), "holon hostile: no stored blob hash");
    }

    function eq(string memory a, string memory b) internal pure returns (bool) {
        return keccak256(bytes(a)) == keccak256(bytes(b));
    }

    /// A header through the _loadBatchHeader call at Rollup.sol:<line> of <entry>.
    function loaderCall(string memory entry, uint256 line, bytes memory h) internal view returns (Call memory c) {
        bytes memory proof = hex"01";
        if (eq(entry, "importGenesisBatch") && line == 230) {
            c = Call(BARE, address(this), none(), abi.encodeCall(Rollup.importGenesisBatch, (h)));
        } else if (eq(entry, "commitBatch") && line == 259) {
            c = Call(GENESIS, who2addr(2), one(blobEnc(2)), abi.encodeCall(Rollup.commitBatch, (input(0, h, r0, r2))));
        } else if (eq(entry, "commitState") && line == 277) {
            c = Call(GENESIS, who2addr(2), none(), abi.encodeCall(Rollup.commitState, (input(0, h, r0, r2))));
        } else if (eq(entry, "commitBatchWithProof") && line == 402) {
            c = Call(DELAY, who2addr(5), one(blobEnc(2)),
                     abi.encodeCall(Rollup.commitBatchWithProof, (input(0, h, r0, r2), genesisHeader, proof)));
        } else if (eq(entry, "commitBatchWithProof") && line == 414) {
            c = Call(DELAY, who2addr(5), one(blobEnc(2)),
                     abi.encodeCall(Rollup.commitBatchWithProof, (input(0, genesisHeader, r0, r2), h, proof)));
        } else if (eq(entry, "revertBatch") && line == 433) {
            c = Call(GENESIS, address(this), none(), abi.encodeCall(Rollup.revertBatch, (h, 1)));
        } else if (eq(entry, "proveState") && line == 600) {
            c = Call(GENESIS, who2addr(2), none(), abi.encodeCall(Rollup.proveState, (h, proof)));
        } else if (eq(entry, "finalizeBatch") && line == 627) {
            c = Call(GENESIS, who2addr(3), none(), abi.encodeCall(Rollup.finalizeBatch, (h)));
        } else if (eq(entry, "proveCommittedBatchState") && line == 716) {
            c = Call(GENESIS, who2addr(3), none(), abi.encodeCall(Rollup.proveCommittedBatchState, (h, proof)));
        } else {
            revert(string.concat("holon hostile: no call site ", entry, ":", XV.toString(line)));
        }
    }

    /// An encoder input (version, prevStateRoot, postStateRoot) through <entry>; every other field valid.
    function encoderCall(string memory entry, bytes memory parent, uint8 v, bytes32 prev, bytes32 post)
        internal view returns (Call memory c) {
        if (eq(entry, "commitBatch")) {
            c = Call(GENESIS, who2addr(2), one(blobEnc(2)), abi.encodeCall(Rollup.commitBatch, (input(v, parent, prev, post))));
        } else if (eq(entry, "commitState")) {
            c = Call(STORED, who2addr(2), none(), abi.encodeCall(Rollup.commitState, (input(v, parent, prev, post))));
        } else if (eq(entry, "commitBatchWithProof")) {
            c = Call(DELAY, who2addr(5), one(blobEnc(2)),
                     abi.encodeCall(Rollup.commitBatchWithProof, (input(v, parent, prev, post), genesisHeader, hex"01")));
        } else {
            revert(string.concat("holon hostile: no encoder entry ", entry));
        }
    }

    // ------------------------------------------------------------ malformed encodings
    function probe() internal pure returns (bytes memory p) {
        p = abi.encodePacked(keccak256("I21:probe:0"), keccak256("I21:probe:1"));
    }

    function find(bytes memory data, bytes memory p) internal pure returns (uint256) {
        for (uint256 i = 0; i + p.length <= data.length; i++) {
            bool ok = true;
            for (uint256 j = 0; j < p.length; j++) {
                if (data[i + j] != p[j]) {
                    ok = false;
                    break;
                }
            }
            if (ok) return i;
        }
        revert("holon hostile: probe not found");
    }

    function word(bytes memory data, uint256 at) internal pure returns (uint256 w) {
        assembly {
            w := mload(add(add(data, 32), at))
        }
    }

    function setWord(bytes memory data, uint256 at, uint256 w) internal pure {
        assembly {
            mstore(add(add(data, 32), at), w)
        }
    }

    function malform(bytes memory data, uint8 how) internal pure returns (bytes memory) {
        bytes memory p = probe();
        uint256 at = find(data, p);
        uint256 lenpos = at - 32;
        require(word(data, lenpos) == p.length, "holon hostile: no length word");
        if (how == 0) {
            setWord(data, lenpos, data.length);
            return data;
        }
        if (how == 1) {
            // the head word that points at the length word: relative to the arguments (4) or to a tuple's head
            for (uint256 q = 4; q + 32 <= lenpos; q += 32) {
                uint256 v = word(data, q);
                if (4 + v == lenpos) {
                    setWord(data, q, 1 << 32);
                    return data;
                }
                for (uint256 r = 4; r < q; r += 32) {
                    uint256 base = 4 + word(data, r);
                    if (base <= q && base + v == lenpos) {
                        setWord(data, q, 1 << 32);
                        return data;
                    }
                }
            }
            revert("holon hostile: no offset word");
        }
        if (how == 2) {
            bytes memory cut = new bytes(at + p.length / 2);
            for (uint256 i = 0; i < cut.length; i++) cut[i] = data[i];
            return cut;
        }
        revert("holon hostile: unknown malformation");
    }

    function exec(Call memory c, uint256 snap) internal returns (bool ok, bytes memory ret) {
        require(XV.revertToState(snap), "holon hostile: no snapshot");
        XV.blobhashes(c.blobs);
        if (c.caller != address(this)) XV.prank(c.caller);
        (ok, ret) = address(rollup).call(c.data);
        XV.blobhashes(none());
    }

    /// (whether the item's state is st, and then its outcome).
    function item(bytes memory raw, uint256 st, uint256 snap) internal returns (bool, bool, bytes memory) {
        (uint8 kind, string memory entry, uint256 line, bytes memory payload) =
            abi.decode(raw, (uint8, string, uint256, bytes));
        Call memory c;
        if (kind == 1) {
            c = loaderCall(entry, line, payload);
        } else if (kind == 2) {
            (uint8 v, bytes32 prev, bytes32 post) = abi.decode(payload, (uint8, bytes32, bytes32));
            c = encoderCall(entry, genesisHeader, v, prev, post);
        } else if (kind == 3) {
            c = loaderCall(entry, line, probe());
            if (c.state == st) c.data = malform(c.data, abi.decode(payload, (uint8)));
        } else if (kind == 4) {
            c = encoderCall(entry, probe(), 0, r0, r2);
            if (c.state == st) c.data = malform(c.data, abi.decode(payload, (uint8)));
        } else {
            revert("holon hostile: unknown item kind");
        }
        if (c.state != st) return (false, false, "");
        (bool ok, bytes memory ret) = exec(c, snap);
        return (true, ok, ret);
    }

    /// One pass: the items of state st, from a snapshot of st; the number of items run.
    function runPass(uint256 st, uint256 sInit) internal returns (uint256 count) {
        require(XV.revertToState(sInit), "holon hostile: no bare snapshot");
        buildState(st, delayPeriod);
        uint256 snap = XV.snapshotState();
        XV.closeFile(inPath);
        XV.readLine(inPath);
        for (uint256 n = 0; ; n++) {
            // nothing an item allocates outlives it: the free memory pointer is reset after each one, so the
            // harness's memory stays bounded over the whole corpus (the EVM's memory limit)
            uint256 fmp;
            assembly {
                fmp := mload(0x40)
            }
            bytes memory raw = XV.parseBytes(XV.readLine(inPath));
            if (raw.length == 0) break;
            (bool mine, bool ok, bytes memory ret) = item(raw, st, snap);
            if (mine) {
                XV.writeLine(outPath, string.concat(XV.toString(n), ok ? " 1 " : " 0 ", XV.toString(ret)));
                count += 1;
            }
            assembly {
                mstore(0x40, fmp)
            }
        }
    }

    function test_hostile() public {
        XV.pauseGasMetering();
        inPath = XV.envString("HOLON_HOSTILE_IN");
        outPath = XV.envString("HOLON_HOSTILE_OUT");
        (uint256 F_, uint256 W_, uint256 D_, uint256 t0, bytes32 r0_, bytes32 r2_) =
            abi.decode(XV.parseBytes(XV.readLine(inPath)), (uint256, uint256, uint256, uint256, bytes32, bytes32));
        r0 = r0_;
        r2 = r2_;
        delayPeriod = D_;
        deployBare(F_, W_, D_, t0);
        uint256 sInit = XV.snapshotState();
        uint256 total = 0;
        for (uint256 st = BARE; st <= STORED; st++) total += runPass(st, sInit);
        XV.writeLine(outPath, string.concat("done ", XV.toString(total)));
    }
}

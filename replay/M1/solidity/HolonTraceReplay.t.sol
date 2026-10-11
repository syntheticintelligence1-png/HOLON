// SPDX-License-Identifier: MIT
// HOLON M1 trace replay (Solidity side). holon/mreplay.py copies this into a scratch copy of
// morph contracts/ and runs `forge test --match-contract HolonTraceReplay -vv`.
//
// It deploys the REAL Rollup and the REAL L1MessageQueueWithGasPriceOracle (behind
// TransparentUpgradeableProxy), with oracle stand-ins for ISubmitter and IRollupVerifier, then
// executes every model trace from $HOLON_TRACES (fresh deployment per trace) and logs one line per step:
//   HOLON <trace> <step> ok <committedBatches[LCI] after the step>
//   HOLON <trace> <step> rev <reason>          (Error(string) text, or panic:0x.., or raw:0x..)
pragma solidity =0.8.24;

import {Test, console} from "forge-std/Test.sol";
import {stdStorage, StdStorage} from "forge-std/StdStorage.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";
import {IRollup} from "../contracts/l1/rollup/IRollup.sol";
import {L1MessageQueueWithGasPriceOracle} from "../contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";

interface HolonVm {
    function warp(uint256) external;
    function prank(address) external;
    function deal(address, uint256) external;
    function readFile(string calldata) external view returns (string memory);
    function parseJsonUintArray(string calldata, string calldata) external pure returns (uint256[] memory);
    function envString(string calldata) external view returns (string memory);
    function envUint(string calldata) external view returns (uint256);
    function blobhashes(bytes32[] calldata) external;
    function store(address, bytes32, bytes32) external;
    function toString(uint256) external pure returns (string memory);
    function toString(bytes32) external pure returns (string memory);
    function toString(bytes calldata) external pure returns (string memory);
}

/// Oracle: ISubmitter. Active set {A, B}; slash deactivates (as Submitter.slash does).
contract HolonSubmitterOracle {
    mapping(address => bool) public active;
    function setActive(address a, bool v) external { active[a] = v; }
    function isActive(address s) external view returns (bool) { return active[s]; }
    function challengeDeposit() external pure returns (uint256) { return 1; }
    function slash(address s) external returns (uint256) { active[s] = false; return 0; }
}

/// Oracle: IRollupVerifier. Accepts iff the proof's first byte is 0x01 (model proof = 1).
contract HolonVerifierOracle {
    function verifyAggregateProof(uint256, uint256, bytes calldata proof, bytes32) external pure {
        require(proof.length > 0 && proof[0] == 0x01, "invalid proof");
    }
}

contract HolonTraceReplayTest is Test {
    using stdStorage for StdStorage;

    HolonVm internal constant HV = HolonVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    uint256 internal constant EPOCH = 1_700_000_000;
    uint256 internal constant W = 13;   // op + 12 fields
    bytes32 internal constant ZVH = 0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014;
    address internal constant MESSENGER = address(0xBEEF);
    address internal constant PROXY_ADMIN = address(0xAD);

    Rollup internal rollup;
    L1MessageQueueWithGasPriceOracle internal queue;
    HolonSubmitterOracle internal sub;
    mapping(uint256 => mapping(uint256 => bytes)) internal hdrs; // trace -> index -> header bytes

    function who2addr(uint256 who) internal view returns (address) {
        return who == 1 ? address(this) : address(uint160(0x1000 + who));
    }

    function blobEnc(uint256 v) internal pure returns (bytes32) {
        if (v == 0) return bytes32(0);
        if (v == 1) return ZVH;
        return bytes32((uint256(1) << 248) | v);
    }

    struct H {
        uint256 v; uint256 idx; uint256 l1p; uint256 tot; bytes32 dh; bytes32 blob; bytes32 prev; bytes32 post;
        bytes32 parent; uint256 lbn;
    }

    function enc(H memory x) internal pure returns (bytes memory h) {
        h = abi.encodePacked(uint8(x.v), uint64(x.idx), uint64(x.l1p), uint64(x.tot), x.dh, x.blob, x.prev, x.post);
        h = abi.encodePacked(h, bytes32(0), bytes32(0), x.parent);
        if (x.v >= 1) h = abi.encodePacked(h, uint64(x.lbn));
    }

    function hdr(uint256 v, uint256 idx, bytes32 dh, bytes32 blob, bytes32 post) internal pure returns (bytes memory) {
        return enc(H(v, idx, 0, 0, dh, blob, bytes32(0), post, bytes32(0), 0));
    }

    function totOf(bytes memory h) internal pure returns (uint256 t) {
        for (uint256 i = 17; i < 25; i++) t = (t << 8) | uint8(h[i]);
    }

    function deploy(uint256 tid, uint256 F_, uint256 W_, uint256 D_, uint256 t0, uint256 r0) internal {
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
        bytes memory g = hdr(0, 0, bytes32(uint256(1)), ZVH, bytes32(r0));
        rollup.importGenesisBatch(g);
        hdrs[tid][0] = g;
    }

    function reason(bytes memory data) internal view returns (string memory) {
        if (data.length >= 4 && bytes4(data) == 0x08c379a0) {
            bytes memory rest = new bytes(data.length - 4);
            for (uint256 i = 0; i < rest.length; i++) rest[i] = data[i + 4];
            return abi.decode(rest, (string));
        }
        if (data.length == 36 && bytes4(data) == 0x4e487b71) {
            uint256 code;
            assembly { code := mload(add(data, 36)) }
            bytes memory hexs = "0123456789abcdef";
            return string(abi.encodePacked("panic:0x", hexs[(code >> 4) & 15], hexs[code & 15]));
        }
        return string.concat("raw:", HV.toString(data));
    }

    function headerFor(uint256 tid, uint256 idx) internal view returns (bytes memory) {
        if (idx <= rollup.lastCommittedBatchIndex() && hdrs[tid][idx].length > 0) return hdrs[tid][idx];
        return hdr(0, idx, bytes32(0), bytes32(0), bytes32(0)); // fabricated: matches no stored hash
    }

    function dataHash(uint256 lbn, uint256 n, uint256 tot) internal view returns (bytes32) {
        bytes memory b = abi.encodePacked(uint64(lbn), uint16(n));
        if (tot + n > queue.nextCrossDomainMessageIndex()) return bytes32(0);
        for (uint256 i = 0; i < n; i++) b = abi.encodePacked(b, queue.getCrossDomainMessage(tot + i));
        return keccak256(b);
    }

    function newHeader(uint256 tid, uint256[] memory s, uint256 o, bytes32 blob) internal view returns (bytes memory) {
        H memory x;
        bytes memory ph = headerFor(tid, s[o + 3]);
        x.v = s[o + 2];
        x.idx = s[o + 3] + 1;
        x.l1p = s[o + 4];
        x.tot = totOf(ph) + s[o + 4];
        x.dh = dataHash(s[o + 5], s[o + 4], totOf(ph));
        x.blob = blob;
        x.prev = bytes32(s[o + 6]);
        x.post = bytes32(s[o + 7]);
        x.parent = keccak256(ph);
        x.lbn = s[o + 5];
        return enc(x);
    }

    function setBlobs(uint256[] memory s, uint256 o) internal {
        uint256 nb = s[o + 8];
        bytes32[] memory bh = new bytes32[](nb);
        if (nb > 0) bh[0] = blobEnc(s[o + 9]);
        if (nb > 1) bh[1] = blobEnc(s[o + 10]);
        HV.blobhashes(bh);
    }

    function commitInput(uint256 tid, uint256[] memory s, uint256 o) internal view returns (IRollup.BatchDataInput memory) {
        return IRollup.BatchDataInput(uint8(s[o + 2]), headerFor(tid, s[o + 3]), uint64(s[o + 5]), uint16(s[o + 4]),
                                      bytes32(s[o + 6]), bytes32(s[o + 7]), bytes32(0));
    }

    function expectedBlob(uint256[] memory s, uint256 o) internal view returns (bytes32) {
        bytes32 stored = rollup.batchBlobVersionedHashes(s[o + 3] + 1);
        if (stored != bytes32(0)) return stored;
        if (s[o + 2] == 2) {
            bytes memory cat;
            if (s[o + 8] > 0) cat = abi.encodePacked(blobEnc(s[o + 9]));
            if (s[o + 8] > 1) cat = abi.encodePacked(cat, blobEnc(s[o + 10]));
            return keccak256(cat);
        }
        return s[o + 8] == 0 || s[o + 9] == 0 ? ZVH : blobEnc(s[o + 9]);
    }

    function proofBytes(uint256 p) internal pure returns (bytes memory) {
        if (p == 0) return "";
        return abi.encodePacked(uint8(p));
    }

    function callAs(uint256 who, bytes memory cd, uint256 value) internal returns (bool ok, bytes memory ret) {
        if (who != 1) HV.prank(who2addr(who));
        (ok, ret) = address(rollup).call{value: value}(cd);
    }

    function legacyEta2(uint256 root) internal {
        // emulate a pre-reinitializer(2) state: committedStateRoots did not exist (all zero), then run initialize2
        uint256 lci = rollup.lastCommittedBatchIndex();
        for (uint256 i = 0; i <= lci + 4; i++) {
            uint256 slot = stdstore.target(address(rollup)).sig("committedStateRoots(uint256)").with_key(i).find();
            HV.store(address(rollup), bytes32(slot), bytes32(0));
        }
        rollup.initialize2(bytes32(root));
    }

    function step(uint256 tid, uint256 si, uint256[] memory s, uint256 o) internal {
        uint256 op = s[o];
        uint256 who = s[o + 1];
        bool ok;
        bytes memory ret;
        bytes32[] memory none = new bytes32[](0);
        HV.blobhashes(none);
        if (op == 1 || op == 2 || op == 3) {
            setBlobs(s, o);
            if (op == 1) (ok, ret) = callAs(who, abi.encodeCall(Rollup.commitBatch, (commitInput(tid, s, o))), 0);
            else if (op == 2) (ok, ret) = callAs(who, abi.encodeCall(Rollup.commitState, (commitInput(tid, s, o))), 0);
            else {
                bytes memory nh = newHeader(tid, s, o, expectedBlob(s, o));
                (ok, ret) = callAs(who, abi.encodeCall(Rollup.commitBatchWithProof, (commitInput(tid, s, o), nh, proofBytes(s[o + 11]))), 0);
            }
            HV.blobhashes(none);
            if (ok) {
                uint256 idx = s[o + 3] + 1;
                bytes memory h = newHeader(tid, s, o, rollup.batchBlobVersionedHashes(idx));
                hdrs[tid][idx] = h;
                if (keccak256(h) != rollup.committedBatches(idx)) console.log("HOLON harness-mismatch", tid, si);
            }
        } else if (op == 4) {
            (ok, ret) = callAs(who, abi.encodeCall(Rollup.revertBatch, (headerFor(tid, s[o + 2]), s[o + 3])), 0);
        } else if (op == 5) {
            (ok, ret) = callAs(who, abi.encodeCall(Rollup.challengeState, (uint64(s[o + 2]), keccak256(headerFor(tid, s[o + 2])))), s[o + 3]);
        } else if (op == 6) {
            (ok, ret) = callAs(who, abi.encodeCall(Rollup.proveState, (headerFor(tid, s[o + 2]), proofBytes(s[o + 3]))), 0);
        } else if (op == 7) {
            (ok, ret) = callAs(who, abi.encodeCall(Rollup.finalizeBatch, (headerFor(tid, s[o + 2]))), 0);
        } else if (op == 8) {
            (ok, ret) = callAs(who, abi.encodeCall(Rollup.setPause, (s[o + 2] == 1)), 0);
        } else if (op == 9) {
            HV.prank(MESSENGER);
            queue.appendCrossDomainMessage(address(0x7a), 1_000_000, "");
            ok = true;
        } else if (op == 10) {
            HV.warp(block.timestamp + s[o + 1]);
            ok = true;
        } else if (op == 11) {
            legacyEta2(s[o + 1]);
            ok = true;
        }
        if (ok) {
            console.log(string.concat("HOLON ", HV.toString(tid), " ", HV.toString(si), " ok ",
                                      HV.toString(rollup.committedBatches(rollup.lastCommittedBatchIndex()))));
        } else {
            console.log(string.concat("HOLON ", HV.toString(tid), " ", HV.toString(si), " rev ", reason(ret)));
        }
    }

    function test_traces() public {
        uint256[] memory d = HV.parseJsonUintArray(HV.readFile(HV.envString("HOLON_TRACES")), ".data");
        // header: [F, W, D, t0, r0, ntraces], then per trace: nsteps, steps (W words each)
        // traces [HOLON_LO, HOLON_HI) only: the corpus runs in chunks to stay under the block gas limit
        uint256 lo = HV.envUint("HOLON_LO");
        uint256 hi = HV.envUint("HOLON_HI");
        uint256 p = 6;
        for (uint256 tid = 0; tid < d[5] && tid < hi; tid++) {
            uint256 n = d[p++];
            if (tid < lo) {
                p += n * W;
                continue;
            }
            deploy(tid, d[0], d[1], d[2], d[3], d[4]);
            for (uint256 si = 0; si < n; si++) {
                step(tid, si, d, p);
                p += W;
            }
        }
    }
}

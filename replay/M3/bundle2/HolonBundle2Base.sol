// SPDX-License-Identifier: MIT
// HOLON I80 generic multi-member step harness (holon/bundle2/harness.py; rule C2 of tests_m3/test_bundle2_extraction.py).
// It is I20's HolonStepBase (replay/M2/solidity/HolonStepBase.sol) generalized from one target to a member set. It
// compares nothing: it runs steps on the real code and writes what the real code did, one record per line.
//
// A concrete harness inherits HolonBundle2Base and implements b2Deploy (deploy the real members and their
// dependencies; return the members' addresses in the sidecar's member order) and b2Abstract (translate an abstract row
// into a call, with the member slots to set first, or say it is an environment step), b2AbstractEnv and b2After.
//
// Input: the JSON file $HOLON_STEPS_IN:
//   {"lens": [n_0, ...], "steps": ["0x..", ...] (abi.encode(uint8 1, bool false, abi.encode(uint256[] row))),
//    "slot_members": [i, ...], "slots": ["0x<32 bytes>", ...]  (member i's slot, read with vm.load after every step),
//    "init": [uint, ...]}
// Traces [$HOLON_LO, $HOLON_HI) run, each from a fresh deployment. Output: lines appended to $HOLON_STEPS_OUT:
//   T <tid> <harness>                                after the deployment
//   M <tid> <i> <member address>                     the members, in order
//   A <tid> <account>                                every account the deployment created (state diff: Create)
//   K <tid> <member> <runtime code>                  every member's code after the deployment
//   Q <tid> <member> <implementation> <code>         a member that is an EIP-1967 proxy: its implementation and code
//   S <tid> <id> <call|env> <ok> <to> <caller> <value> <timestamp> <number> <blobs> <data> <ret>
//                                                    one per step (id d: the deployment; env steps write - for the call)
//   V <tid> <id> <chainid> <basefee> <prevrandao> <coinbase> <gaslimit> <blobbasefee> <origin> <gasprice> <balances>
//                                                    a call step's environment; balances: addr:wei,... of every member
//                                                    and the caller before the call (its value not yet transferred)
//   P <tid> <id> <member> <slot> <word>              a slot the step set (vm.store) before its call
//   W <tid> <id> <member> <slot> <value> <reverted>  every storage write to a member during the step, in order
//   L <tid> <id> <emitter> <topics> <data>           every log a member emitted (topics comma-separated, or -)
//   F <tid> <id> <depth> <caller> <callee> <selector|-> <value> <reverted>
//                                                    every call frame on a member (Call or StaticCall), in order;
//                                                    reverted is forge's: the frame or an enclosing one reverted
//   C <tid> <id> <from> <to> <data> <value> <ok> <ret>   every call a member made to another account, in order, with
//                                                    its answer: re-run in order from the state before the step, as
//                                                    that member
//   D <tid> <id> <v,v,...>                           vm.load of every input slot after the step (0 for zero)
//   X <tid> <id> <note>                              a note from the concrete harness
//   E <tid> <n>                                      end of a trace;  DONE <lo> <hi>  at the end
// Gas metering is paused. A call step's caller is dealt the call's value only when its balance is below it.
pragma solidity =0.8.24;

import {Test} from "forge-std/Test.sol";

interface HolonB2Vm {
    enum AccountAccessKind { Call, DelegateCall, CallCode, StaticCall, Create, SelfDestruct, Resume, Balance,
                             Extcodesize, Extcodehash, Extcodecopy }
    struct ChainInfo { uint256 forkId; uint256 chainId; }
    struct StorageAccess { address account; bytes32 slot; bool isWrite; bytes32 previousValue; bytes32 newValue;
                           bool reverted; }
    struct AccountAccess { ChainInfo chainInfo; AccountAccessKind kind; address account; address accessor;
                           bool initialized; uint256 oldBalance; uint256 newBalance; bytes deployedCode; uint256 value;
                           bytes data; bool reverted; StorageAccess[] storageAccesses; uint64 depth; }
    struct Log { bytes32[] topics; bytes data; address emitter; }
    function snapshotState() external returns (uint256);
    function revertToState(uint256) external returns (bool);
    function deleteStateSnapshot(uint256) external returns (bool);
    function startStateDiffRecording() external;
    function stopAndReturnStateDiff() external returns (AccountAccess[] memory);
    function recordLogs() external;
    function getRecordedLogs() external returns (Log[] memory);
    function prank(address) external;
    function deal(address, uint256) external;
    function warp(uint256) external;
    function blobhashes(bytes32[] calldata) external;
    function load(address, bytes32) external view returns (bytes32);
    function store(address, bytes32, bytes32) external;
    function pauseGasMetering() external;
    function readFile(string calldata) external view returns (string memory);
    function writeLine(string calldata, string calldata) external;
    function envString(string calldata) external view returns (string memory);
    function envUint(string calldata) external view returns (uint256);
    function parseJsonUintArray(string calldata, string calldata) external pure returns (uint256[] memory);
    function parseJsonBytesArray(string calldata, string calldata) external pure returns (bytes[] memory);
    function parseJsonBytes32Array(string calldata, string calldata) external pure returns (bytes32[] memory);
    function toString(bytes calldata) external pure returns (string memory);
    function toString(uint256) external pure returns (string memory);
}

abstract contract HolonBundle2Base is Test {
    HolonB2Vm internal constant B2 = HolonB2Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    bytes32 internal constant B2_EIP1967_IMPLEMENTATION =
        0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;
    address internal constant B2_CONSOLE = address(0x000000000000000000636F6e736F6c652e6c6f67);

    struct B2Call {
        address caller;
        uint256 value;
        uint256 timestamp;
        bytes32[] blobs;
        address to;
        bytes data;
    }

    struct B2Poke {
        address member;
        bytes32 slot;
        bytes32 word;
    }

    address[] internal b2Members;
    string internal b2Out;
    uint256[] internal b2SlotMembers;
    bytes32[] internal b2Slots;

    /// Deploy the real members and their dependencies for trace tid; return the members' addresses in order.
    function b2Deploy(uint256 tid, uint256[] memory init) internal virtual returns (address[] memory);

    /// Translate an abstract row into a call (isCall) with the slots to set before it, or say it is an environment step.
    function b2Abstract(uint256 tid, uint256[] memory row)
        internal virtual returns (bool isCall, B2Call memory c, B2Poke[] memory pokes);

    /// Run an abstract environment step.
    function b2AbstractEnv(uint256 tid, uint256 id, uint256[] memory row) internal virtual;

    /// Bookkeeping after an abstract row's call ran (ok: whether it returned).
    function b2After(uint256 tid, uint256 id, uint256[] memory row, bool ok) internal virtual {}

    function b2Line(string memory s) internal {
        B2.writeLine(b2Out, s);
    }

    function b2hx(bytes memory b) internal pure returns (string memory) {
        return B2.toString(b);
    }

    function b2ha(address a) internal pure returns (string memory) {
        return B2.toString(abi.encodePacked(a));
    }

    function b2hw(bytes32 w) internal pure returns (string memory) {
        return w == bytes32(0) ? "0" : B2.toString(abi.encodePacked(w));
    }

    function b2dec(uint256 v) internal pure returns (string memory) {
        return B2.toString(v);
    }

    function b2pre(uint256 tid, uint256 id) internal pure returns (string memory) {
        return string.concat(b2dec(tid), " ", id == type(uint256).max ? "d" : b2dec(id), " ");
    }

    function b2IsMember(address a) internal view returns (bool) {
        for (uint256 i = 0; i < b2Members.length; i++) if (b2Members[i] == a) return true;
        return false;
    }

    function b2IsCall(HolonB2Vm.AccountAccess memory a) internal pure returns (bool) {
        return a.kind == HolonB2Vm.AccountAccessKind.Call || a.kind == HolonB2Vm.AccountAccessKind.StaticCall
            || a.kind == HolonB2Vm.AccountAccessKind.CallCode;
    }

    function b2Writes(uint256 tid, uint256 id, HolonB2Vm.AccountAccess[] memory acc) internal {
        for (uint256 i = 0; i < acc.length; i++) {
            HolonB2Vm.StorageAccess[] memory st = acc[i].storageAccesses;
            for (uint256 j = 0; j < st.length; j++) {
                if (!st[j].isWrite || !b2IsMember(st[j].account)) continue;
                b2Line(string.concat("W ", b2pre(tid, id), b2ha(st[j].account), " ",
                                     B2.toString(abi.encodePacked(st[j].slot)), " ",
                                     B2.toString(abi.encodePacked(st[j].newValue)), st[j].reverted ? " 1" : " 0"));
            }
        }
    }

    function b2Frames(uint256 tid, uint256 id, HolonB2Vm.AccountAccess[] memory acc) internal {
        for (uint256 i = 0; i < acc.length; i++) {
            if (!b2IsCall(acc[i]) || !b2IsMember(acc[i].account)) continue;
            bytes memory d = acc[i].data;
            string memory sel = d.length >= 4 ? B2.toString(abi.encodePacked(bytes4(d))) : "-";
            b2Line(string.concat("F ", b2pre(tid, id), b2dec(acc[i].depth), " ", b2ha(acc[i].accessor), " ",
                                 b2ha(acc[i].account), " ", sel, " ", b2dec(acc[i].value),
                                 acc[i].reverted ? " 1" : " 0"));
        }
    }

    function b2Logs(uint256 tid, uint256 id, HolonB2Vm.Log[] memory logs) internal {
        for (uint256 i = 0; i < logs.length; i++) {
            if (!b2IsMember(logs[i].emitter)) continue;
            string memory t = "";
            for (uint256 j = 0; j < logs[i].topics.length; j++) {
                t = string.concat(t, j == 0 ? "" : ",", B2.toString(abi.encodePacked(logs[i].topics[j])));
            }
            b2Line(string.concat("L ", b2pre(tid, id), b2ha(logs[i].emitter), " ", bytes(t).length == 0 ? "-" : t,
                                 " ", b2hx(logs[i].data)));
        }
    }

    function b2IsOutgoing(HolonB2Vm.AccountAccess memory a) internal view returns (bool) {
        return b2IsCall(a) && b2IsMember(a.accessor) && a.account != a.accessor && a.account != address(B2)
            && a.account != B2_CONSOLE;
    }

    /// Calls members made to other accounts during the step: answered again, in order, from the state before it.
    function b2Answers(uint256 tid, uint256 id, uint256 snapPre, HolonB2Vm.AccountAccess[] memory acc) internal {
        uint256 n = 0;
        for (uint256 i = 0; i < acc.length; i++) if (b2IsOutgoing(acc[i])) n++;
        if (n == 0) return;
        uint256 snapPost = B2.snapshotState();
        B2.revertToState(snapPre);
        for (uint256 i = 0; i < acc.length; i++) {
            if (!b2IsOutgoing(acc[i])) continue;
            B2.prank(acc[i].accessor);
            (bool ok, bytes memory ret) = acc[i].account.call{value: acc[i].value}(acc[i].data);
            b2Line(string.concat("C ", b2pre(tid, id), b2ha(acc[i].accessor), " ", b2ha(acc[i].account), " ",
                                 b2hx(acc[i].data), " ", b2dec(acc[i].value), ok ? " 1 " : " 0 ", b2hx(ret)));
        }
        B2.revertToState(snapPost);
        B2.deleteStateSnapshot(snapPost);
    }

    function b2Dump(uint256 tid, uint256 id) internal {
        string memory s = "";
        for (uint256 i = 0; i < b2Slots.length; i++) {
            s = string.concat(s, i == 0 ? "" : ",", b2hw(B2.load(b2Members[b2SlotMembers[i]], b2Slots[i])));
        }
        b2Line(string.concat("D ", b2pre(tid, id), bytes(s).length == 0 ? "-" : s));
    }

    function b2Balances(address caller) internal view returns (string memory s) {
        for (uint256 i = 0; i < b2Members.length; i++) {
            s = string.concat(s, i == 0 ? "" : ",", b2ha(b2Members[i]), ":", b2dec(b2Members[i].balance));
        }
        s = string.concat(s, ",", b2ha(caller), ":", b2dec(caller.balance));
    }

    function b2EnvLine(uint256 tid, uint256 id, string memory bal) internal {
        string memory b = string.concat(b2dec(block.chainid), " ", b2dec(block.basefee), " ", b2dec(block.prevrandao),
                                        " ", b2ha(block.coinbase), " ", b2dec(block.gaslimit), " ");
        string memory t = string.concat(b2dec(block.blobbasefee), " ", b2ha(tx.origin), " ", b2dec(tx.gasprice), " ",
                                        bal);
        b2Line(string.concat("V ", b2pre(tid, id), b, t));
    }

    function b2BlobList(bytes32[] memory b) internal pure returns (string memory s) {
        if (b.length == 0) return "-";
        for (uint256 i = 0; i < b.length; i++) s = string.concat(s, i == 0 ? "" : ",", B2.toString(abi.encodePacked(b[i])));
    }

    /// Run one call and record it.
    function b2Exec(uint256 tid, uint256 id, B2Call memory c, B2Poke[] memory pokes) internal returns (bool ok) {
        for (uint256 i = 0; i < pokes.length; i++) {
            B2.store(pokes[i].member, pokes[i].slot, pokes[i].word);
            b2Line(string.concat("P ", b2pre(tid, id), b2ha(pokes[i].member), " ", b2hw(pokes[i].slot), " ",
                                 b2hw(pokes[i].word)));
        }
        if (c.timestamp != 0) B2.warp(c.timestamp);
        if (c.value > c.caller.balance) B2.deal(c.caller, c.value);
        B2.blobhashes(c.blobs);
        string memory bal = b2Balances(c.caller);
        uint256 snapPre = B2.snapshotState();
        B2.recordLogs();
        B2.startStateDiffRecording();
        if (c.caller != address(this)) B2.prank(c.caller);
        bytes memory ret;
        (ok, ret) = c.to.call{value: c.value}(c.data);
        HolonB2Vm.AccountAccess[] memory acc = B2.stopAndReturnStateDiff();
        HolonB2Vm.Log[] memory logs = B2.getRecordedLogs();
        b2CallLine(tid, id, c, ok, ret);
        b2EnvLine(tid, id, bal);
        b2Writes(tid, id, acc);
        b2Logs(tid, id, logs);
        b2Frames(tid, id, acc);
        b2Answers(tid, id, snapPre, acc);
        B2.deleteStateSnapshot(snapPre);
        b2Dump(tid, id);
        bytes32[] memory none = new bytes32[](0);
        B2.blobhashes(none);
    }

    function b2CallLine(uint256 tid, uint256 id, B2Call memory c, bool ok, bytes memory ret) internal {
        string memory head = string.concat("S ", b2pre(tid, id), "call ", ok ? "1 " : "0 ", b2ha(c.to), " ",
                                           b2ha(c.caller), " ", b2dec(c.value), " ");
        string memory clock = string.concat(b2dec(block.timestamp), " ", b2dec(block.number), " ");
        b2Line(string.concat(head, clock, b2BlobList(c.blobs), " ", b2hx(c.data), " ", b2hx(ret)));
    }

    function b2EnvRecord(uint256 tid, uint256 id, HolonB2Vm.AccountAccess[] memory acc) internal {
        b2Line(string.concat("S ", b2pre(tid, id), "env 1 - - 0 ", b2dec(block.timestamp), " ", b2dec(block.number),
                             " - 0x 0x"));
        b2Writes(tid, id, acc);
        b2Dump(tid, id);
    }

    function b2Step(uint256 tid, uint256 id, bytes memory raw) internal {
        (uint8 kind,, bytes memory payload) = abi.decode(raw, (uint8, bool, bytes));
        require(kind == 1, "HolonBundle2Base: abstract rows only");
        uint256[] memory row = abi.decode(payload, (uint256[]));
        (bool isCall, B2Call memory c, B2Poke[] memory pokes) = b2Abstract(tid, row);
        if (isCall) {
            bool ok = b2Exec(tid, id, c, pokes);
            b2After(tid, id, row, ok);
        } else {
            B2.startStateDiffRecording();
            b2AbstractEnv(tid, id, row);
            b2EnvRecord(tid, id, B2.stopAndReturnStateDiff());
        }
    }

    function b2Begin(uint256 tid, uint256[] memory init) internal {
        B2.startStateDiffRecording();
        address[] memory ms = b2Deploy(tid, init);
        HolonB2Vm.AccountAccess[] memory acc = B2.stopAndReturnStateDiff();
        delete b2Members;
        for (uint256 i = 0; i < ms.length; i++) b2Members.push(ms[i]);
        b2Line(string.concat("T ", b2dec(tid), " ", b2ha(address(this))));
        for (uint256 i = 0; i < ms.length; i++) {
            b2Line(string.concat("M ", b2dec(tid), " ", b2dec(i), " ", b2ha(ms[i])));
        }
        for (uint256 i = 0; i < acc.length; i++) {
            if (acc[i].kind == HolonB2Vm.AccountAccessKind.Create) {
                b2Line(string.concat("A ", b2dec(tid), " ", b2ha(acc[i].account)));
            }
        }
        for (uint256 i = 0; i < ms.length; i++) {
            b2Line(string.concat("K ", b2dec(tid), " ", b2ha(ms[i]), " ", b2hx(ms[i].code)));
            address impl = address(uint160(uint256(B2.load(ms[i], B2_EIP1967_IMPLEMENTATION))));
            if (impl != address(0)) {
                b2Line(string.concat("Q ", b2dec(tid), " ", b2ha(ms[i]), " ", b2ha(impl), " ", b2hx(impl.code)));
            }
        }
        b2EnvRecord(tid, type(uint256).max, acc);
    }

    function test_steps() public {
        B2.pauseGasMetering();
        string memory js = B2.readFile(B2.envString("HOLON_STEPS_IN"));
        b2Out = B2.envString("HOLON_STEPS_OUT");
        uint256[] memory lens = B2.parseJsonUintArray(js, ".lens");
        bytes[] memory steps = B2.parseJsonBytesArray(js, ".steps");
        uint256[] memory sm = B2.parseJsonUintArray(js, ".slot_members");
        bytes32[] memory sl = B2.parseJsonBytes32Array(js, ".slots");
        uint256[] memory init = B2.parseJsonUintArray(js, ".init");
        require(sm.length == sl.length, "HolonBundle2Base: one member per slot");
        for (uint256 i = 0; i < sl.length; i++) {
            b2SlotMembers.push(sm[i]);
            b2Slots.push(sl[i]);
        }
        uint256 lo = B2.envUint("HOLON_LO");
        uint256 hi = B2.envUint("HOLON_HI");
        uint256 p = 0;
        for (uint256 tid = 0; tid < lens.length && tid < hi; tid++) {
            if (tid < lo) {
                p += lens[tid];
                continue;
            }
            uint256 snap0 = B2.snapshotState();
            b2Begin(tid, init);
            for (uint256 si = 0; si < lens[tid]; si++) b2Step(tid, si, steps[p + si]);
            p += lens[tid];
            b2Line(string.concat("E ", b2dec(tid), " ", b2dec(lens[tid])));
            B2.revertToState(snap0);
            B2.deleteStateSnapshot(snap0);
        }
        b2Line(string.concat("DONE ", b2dec(lo), " ", b2dec(hi)));
    }
}

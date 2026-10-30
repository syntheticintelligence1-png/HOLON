// SPDX-License-Identifier: MIT
// HOLON I84 law replay harness (tests_m3/test_bundle2_laws.py rules LD1, LD5, FP4 and RC2; holon/bundle2/laws_forge.py).
// It is I80's generic multi-member step base (HolonBundle2Base, unchanged: the same input file and output lines) over
// the laws' deployment (HolonBundle2LawsBase.lawsDeploy: I80's deployment with the router constructed with
// HOLON_VERSIONS, each mapped to the stand-in Z1), with concrete calls instead of I20's abstract rows.
//
// A step row is [100, caller, value, timestamp, to, data, nblobs, blob_0, .., blob_{nblobs-1}]: caller an address as a
// number, to 1 for the Rollup proxy (member 0) and 2 for the router (member 1), data an index into the input file's
// "calldata" array (the call's calldata, as the model's witness encodes it), and the blob-hash list of the call. A trace
// with no step records the deployment alone (its lines T, M, A, K, Q, S d and W d: the members' storage and code).
pragma solidity =0.8.24;

import {HolonBundle2Base} from "./HolonBundle2Base.sol";
import {HolonBundle2LawsBase} from "./HolonBundle2LawsBase.sol";

contract HolonBundle2LawReplayTest is HolonBundle2Base, HolonBundle2LawsBase {
    bytes[] internal lawData;
    bool internal lawLoaded;

    function b2Deploy(uint256 tid, uint256[] memory init) internal override returns (address[] memory m) {
        if (!lawLoaded) {
            string memory js = B2.readFile(B2.envString("HOLON_STEPS_IN"));
            bytes[] memory ds = B2.parseJsonBytesArray(js, ".calldata");
            for (uint256 i = 0; i < ds.length; i++) lawData.push(ds[i]);
            lawLoaded = true;
        }
        lawsDeploy(tid, init, LV.envUint("HOLON_VERSIONS", ","));
        m = new address[](2);
        m[0] = address(rollup);
        m[1] = address(router);
    }

    function b2Abstract(uint256, uint256[] memory s)
        internal view override returns (bool, B2Call memory c, B2Poke[] memory pokes)
    {
        require(s.length >= 7 && s[0] == 100, "HolonBundle2LawReplay: concrete call rows only");
        pokes = new B2Poke[](0);
        c.caller = address(uint160(s[1]));
        c.value = s[2];
        c.timestamp = s[3];
        c.to = s[4] == 1 ? address(rollup) : address(router);
        c.data = lawData[s[5]];
        uint256 nb = s[6];
        require(s.length == 7 + nb, "HolonBundle2LawReplay: the row's blob list");
        c.blobs = new bytes32[](nb);
        for (uint256 i = 0; i < nb; i++) c.blobs[i] = bytes32(s[7 + i]);
        return (true, c, pokes);
    }

    function b2AbstractEnv(uint256, uint256, uint256[] memory) internal pure override {
        revert("HolonBundle2LawReplay: no environment rows");
    }
}

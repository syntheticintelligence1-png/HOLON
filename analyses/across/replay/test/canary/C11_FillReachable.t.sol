// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { T11_FillOnceInvariant } from "../T11_FillOnceInvariant.t.sol";

// Non-vacuity canary for T11: this invariant MUST FAIL (the fuzzer must reach at least one payout), otherwise the
// handler never exercises the fill pipeline and T11's PASS would be vacuous. run.sh asserts the failure.
contract C11_FillReachable is T11_FillOnceInvariant {
    function invariant_noPayoutEver() public view {
        assertEq(token.balanceOf(h.recipient()), 0);
    }
}

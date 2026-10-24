// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { Test } from "forge-std/Test.sol";
import { Ethereum_SpokePool } from "across/spoke-pools/Ethereum_SpokePool.sol";
import { V3SpokePoolInterface } from "across/interfaces/V3SpokePoolInterface.sol";
import { MintableERC20 } from "across/test/MockERC20.sol";
import { WETH9 } from "across/external/WETH9.sol";
import { AddressToBytes32 } from "across/libraries/AddressConverters.sol";
import { ERC1967Proxy } from "@openzeppelin/contracts-v4/proxy/ERC1967/ERC1967Proxy.sol";

// Handler: every action reachable on the destination for ONE relay hash, with adversarial time (forward AND
// backward warps = relaxation of A_clk) and adversarial root delivery (the same slow root relayed any number of
// times = relaxation of A_V1). Reverting calls are swallowed (a revert is an absent transition).
contract FillHandler is Test {
    using AddressToBytes32 for address;
    Ethereum_SpokePool public spoke;
    MintableERC20 public token;
    V3SpokePoolInterface.V3RelayData public rd;
    address public recipient = makeAddr("recipient");
    address[3] relayers = [makeAddr("r0"), makeAddr("r1"), makeAddr("r2")];
    uint256 public t0;
    uint256 public roots;

    constructor(Ethereum_SpokePool _spoke, MintableERC20 _token) {
        spoke = _spoke;
        token = _token;
        t0 = block.timestamp;
        rd = V3SpokePoolInterface.V3RelayData({
            depositor: makeAddr("depositor").toBytes32(),
            recipient: recipient.toBytes32(),
            exclusiveRelayer: relayers[0].toBytes32(),
            inputToken: address(token).toBytes32(),
            outputToken: address(token).toBytes32(),
            inputAmount: 10 ether,
            outputAmount: 10 ether,
            originChainId: 777,
            depositId: 1,
            fillDeadline: uint32(t0 + 100),
            exclusivityDeadline: uint32(t0 + 10),
            message: ""
        });
        for (uint256 i = 0; i < 3; i++) {
            token.mint(relayers[i], 1000 ether);
            vm.prank(relayers[i]);
            token.approve(address(spoke), type(uint256).max);
        }
    }

    function _slowLeaf() internal view returns (V3SpokePoolInterface.V3SlowFill memory) {
        return V3SpokePoolInterface.V3SlowFill({ relayData: rd, chainId: block.chainid, updatedOutputAmount: 10 ether });
    }

    function warp(uint256 x) external {
        vm.warp(t0 + (x % 200)); // any time in [t0, t0+200), including going backwards
    }

    function fill(uint256 who) external {
        vm.prank(relayers[who % 3]);
        try spoke.fillRelay(rd, 1, relayers[who % 3].toBytes32()) {} catch {}
    }

    function requestSlowFill() external {
        try spoke.requestSlowFill(rd) {} catch {}
    }

    function relaySlowRoot() external {
        vm.prank(spoke.owner());
        spoke.relayRootBundle(bytes32(0), keccak256(abi.encode(_slowLeaf())));
        roots++;
    }

    function executeSlow(uint256 id) external {
        if (roots == 0) return;
        try spoke.executeSlowRelayLeaf(_slowLeaf(), uint32(id % roots), new bytes32[](0)) {} catch {}
    }
}

contract T11_FillOnceInvariant is Test {
    FillHandler internal h;
    MintableERC20 internal token;

    function setUp() public {
        vm.warp(1_790_000_000);
        token = new MintableERC20("T", "T", 18);
        WETH9 weth = new WETH9();
        Ethereum_SpokePool impl = new Ethereum_SpokePool(address(weth), 3600, 21600, address(0));
        Ethereum_SpokePool spoke = Ethereum_SpokePool(
            payable(new ERC1967Proxy(address(impl), abi.encodeCall(Ethereum_SpokePool.initialize, (0, address(this)))))
        );
        token.mint(address(spoke), 1000 ether); // spoke reserves for slow fills
        h = new FillHandler(spoke, token);
        targetContract(address(h));
    }

    /// I_fill_once on the EVM spoke, with A_clk and A_V1 both relaxed: the recipient is paid at most once.
    function invariant_fillOnce() public view {
        assertLe(token.balanceOf(h.recipient()), 10 ether);
    }
}

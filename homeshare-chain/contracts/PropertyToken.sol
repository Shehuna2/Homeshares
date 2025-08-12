// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/// @notice ERC20 shares for a single property
contract PropertyToken is ERC20, Ownable {
    constructor(
        string memory name,
        string memory symbol,
        address initialOwner
    )
        ERC20(name, symbol)
        Ownable(initialOwner)  // pass the owner here per OZ v5+
    {}

    /// @notice Mint new tokens, only callable by owner (the crowdfund contract)
    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }
}

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./PropertyToken.sol";

/// @notice Crowdfund + profit-distribution contract
contract PropertyCrowdfund is Ownable {
    PropertyToken public token;
    uint256       public goal;            // goal in wei
    bool          public closed;          // true once owner withdraws raised funds
    uint256       public returnsPool;     // total proceeds to distribute
    uint256       public returnsPerToken; // scaled by 1e18

    mapping(address => uint256) public raised;   // raised[address(0)] for native MON
    mapping(address => uint256) public claimed;  // how much each investor has claimed

    event Contribution(address indexed investor, uint256 amount);
    event FundsWithdrawn(address indexed to, uint256 amount);
    event ProfitDistributed(uint256 totalProceeds);
    event ReturnClaimed(address indexed investor, uint256 amount);

    /// @param _name       name of the ERC20 share token
    /// @param _symbol     symbol of the ERC20 share token
    /// @param _goalWei    fundraising goal in wei
    /// @param initialOwner owner address (who can withdraw and distribute)
    constructor(
        string memory _name,
        string memory _symbol,
        uint256      _goalWei,
        address      initialOwner
    )
        Ownable(initialOwner)            // set owner here per OZ v5+
    {
        token = new PropertyToken(_name, _symbol, initialOwner);
        token.transferOwnership(address(this));
        goal = _goalWei;
    }

    /// @notice Anyone can contribute native MON while raise is open
    function contribute() external payable {
        require(!closed, "Raising closed");
        require(msg.value > 0, "No funds sent");
        raised[address(0)] += msg.value;
        token.mint(msg.sender, msg.value);
        emit Contribution(msg.sender, msg.value);
    }

    /// @notice Has goal been reached?
    function isGoalReached() public view returns (bool) {
        return raised[address(0)] >= goal;
    }

    /// @notice Owner pulls all raised MON once goal met
    function withdrawRaised() external onlyOwner {
        require(isGoalReached(), "Goal not met");
        require(!closed, "Already withdrawn");
        uint256 bal = address(this).balance;
        require(bal > 0, "Nothing to withdraw");
        closed = true;
        payable(owner()).transfer(bal);
        emit FundsWithdrawn(owner(), bal);
    }

    /// @notice After off-chain sale, owner sends proceeds here
    function distributeReturns() external payable onlyOwner {
        require(closed, "Not closed for raising");
        require(msg.value > 0, "No proceeds sent");
        returnsPool += msg.value;
    }

    /// @notice Finalize distribution: compute per-token payout
    function finalizeDistribution() external onlyOwner {
        uint256 totalSupply = token.totalSupply();
        require(totalSupply > 0, "No tokens minted");
        require(returnsPool   > 0, "No proceeds");
        returnsPerToken = (returnsPool * 1e18) / totalSupply;
        emit ProfitDistributed(returnsPool);
    }

    /// @notice Investors call to claim their share
    function claimReturns() external {
        require(returnsPerToken > 0, "Not finalized");
        uint256 bal = token.balanceOf(msg.sender);
        require(bal > 0, "No shares held");
        uint256 owed = (bal * returnsPerToken) / 1e18 - claimed[msg.sender];
        require(owed > 0, "Nothing to claim");
        claimed[msg.sender] += owed;
        payable(msg.sender).transfer(owed);
        emit ReturnClaimed(msg.sender, owed);
    }
}

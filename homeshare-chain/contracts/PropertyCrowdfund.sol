// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract PropertyToken is ERC20, Ownable {
    constructor(string memory name, string memory symbol) ERC20(name, symbol) Ownable(msg.sender) {}
    
    /// @notice Mint new tokens, only callable by owner (the crowdfund contract)
    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }
}

contract PropertyCrowdfund is Ownable {
    PropertyToken public token;
    uint256 public goal;
    bool public closed;

    // Track contributions per currency (native: address(0))
    mapping(address => uint256) public raised;
    
    // Investors list for profit distribution
    address[] public investors;
    mapping(address => bool) private isInvestor;

    // Accepted ERC20 tokens
    mapping(address => bool) public acceptedTokens;
    address[] public tokenList;

    event Contribution(address indexed investor, uint256 amount);
    event TokenContribution(address indexed investor, address indexed token, uint256 amount);
    event TokenAdded(address indexed token);
    event CampaignClosed(uint256 totalRaised);
    event Withdraw(address indexed to, uint256 amount);
    event ProfitsDistributed(uint256 amount);

    constructor(
        string memory _name,
        string memory _symbol,
        uint256 _goal
    ) Ownable(msg.sender) {
        token = new PropertyToken(_name, _symbol);
        token.transferOwnership(address(this));
        goal = _goal;
        closed = false;
    }

    /// @notice Owner can add new ERC20 tokens to accept
    function addToken(address _token) external onlyOwner {
        require(!acceptedTokens[_token], "Already accepted");
        acceptedTokens[_token] = true;
        tokenList.push(_token);
        emit TokenAdded(_token);
    }

    /// @notice Contribute native MON
    function contribute() external payable {
        require(!closed, "Campaign closed");
        require(msg.value > 0, "No funds sent");
        raised[address(0)] += msg.value;
        _recordInvestor(msg.sender);
        token.mint(msg.sender, msg.value);
        emit Contribution(msg.sender, msg.value);
        _checkGoal();
    }

    /// @notice Contribute using an accepted ERC20 token
    function contributeWithToken(address _token, uint256 _amount) external {
        require(!closed, "Campaign closed");
        require(acceptedTokens[_token], "Token not accepted");
        require(_amount > 0, "Amount must be >0");

        IERC20(_token).transferFrom(msg.sender, address(this), _amount);
        raised[_token] += _amount;
        _recordInvestor(msg.sender);
        token.mint(msg.sender, _amount);
        emit TokenContribution(msg.sender, _token, _amount);
        _checkGoal();
    }

    /// @notice Get list of accepted tokens
    function getAcceptedTokens() external view returns (address[] memory) {
        return tokenList;
    }

    /// @notice Close campaign when goal reached
    function _checkGoal() internal {
        uint256 totalNative = raised[address(0)];
        if (totalNative >= goal) {
            closed = true;
            emit CampaignClosed(totalNative);
        }
    }

    /// @notice Owner withdraws native funds after close
    function withdraw() external onlyOwner {
        require(closed, "Campaign not closed");
        uint256 balance = address(this).balance;
        require(balance > 0, "Nothing to withdraw");
        payable(owner()).transfer(balance);
        emit Withdraw(owner(), balance);
    }

    /// @notice Distribute profits proportionally to token holders (native MON profits)
    function distributeProfits() external payable onlyOwner {
        uint256 profit = msg.value;
        require(profit > 0, "No profits sent");

        uint256 totalSupply = token.totalSupply();
        for (uint i = 0; i < investors.length; i++) {
            address inv = investors[i];
            uint256 balance = token.balanceOf(inv);
            if (balance > 0) {
                uint256 share = (profit * balance) / totalSupply;
                payable(inv).transfer(share);
            }
        }
        emit ProfitsDistributed(profit);
    }

    /// @notice Helper to record unique investors
    function _recordInvestor(address _inv) internal {
        if (!isInvestor[_inv]) {
            isInvestor[_inv] = true;
            investors.push(_inv);
        }
    }
}




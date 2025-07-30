const { ethers } = require("hardhat");
const assert = require("assert");

describe("PropertyCrowdfund", function() {
  let Crowdfund, crowdfund, owner, addr1, addr2;
  const NAME   = "Test Property";
  const SYMBOL = "TPROP";
  const GOAL   = ethers.utils.parseEther("5");  // 5 ETH goal

  beforeEach(async function() {
    [owner, addr1, addr2] = await ethers.getSigners();
    Crowdfund = await ethers.getContractFactory("PropertyCrowdfund");
    crowdfund = await Crowdfund.deploy(NAME, SYMBOL, GOAL);
    await crowdfund.deployed();
  });

  it("initializes correctly", async function() {
    const goal   = await crowdfund.goal();
    const raised = await crowdfund.raised();
    const closed = await crowdfund.isClosed();
    assert(goal.eq(GOAL), "Goal should match");
    assert(raised.isZero(), "Raised should start at zero");
    assert.strictEqual(closed, false, "Campaign should start open");
  });

  it("accepts contributions and mints tokens", async function() {
    const oneEth = ethers.utils.parseEther("1");
    await crowdfund.connect(addr1).contribute({ value: oneEth });

    const raised = await crowdfund.raised();
    assert(raised.eq(oneEth), "Raised should increase by contribution");

    const tokenAddr = await crowdfund.token();
    const Token     = await ethers.getContractFactory("PropertyToken");
    const token     = Token.attach(tokenAddr);
    const balance   = await token.balanceOf(addr1.address);
    assert(balance.eq(oneEth), "Token balance should equal contribution");
  });

  it("closes campaign when goal reached", async function() {
    await crowdfund.connect(addr1).contribute({ value: GOAL });
    const closed = await crowdfund.isClosed();
    assert.strictEqual(closed, true, "Campaign should close at goal");

    let reverted = false;
    try {
      await crowdfund.connect(addr2).contribute({ value: ethers.utils.parseEther("1") });
    } catch (e) {
      reverted = true;
    }
    assert(reverted, "Contribution should revert after campaign close");
  });

  it("only owner can withdraw after close", async function() {
    // Fund and close
    await crowdfund.connect(addr1).contribute({ value: GOAL });

    // Non-owner withdraw should revert
    let nonOwnerReverted = false;
    try {
      await crowdfund.connect(addr1).withdrawFunds(addr1.address);
    } catch (_) {
      nonOwnerReverted = true;
    }
    assert(nonOwnerReverted, "Non-owner withdrawFunds should revert");

    // Owner withdraw
    const balanceBefore = await ethers.provider.getBalance(owner.address);
    const tx            = await crowdfund.withdrawFunds(owner.address);
    const receipt       = await tx.wait();
    const gasCost       = receipt.gasUsed.mul(receipt.effectiveGasPrice);
    const balanceAfter  = await ethers.provider.getBalance(owner.address);

    assert(
      balanceAfter.eq(balanceBefore.add(GOAL).sub(gasCost)),
      "Owner should receive the full campaign balance"
    );
  });

  it("allows profit distribution (logs event)", async function() {
    await crowdfund.connect(addr1).contribute({ value: GOAL });

    const profit = ethers.utils.parseEther("2");
    const tx     = await crowdfund.connect(owner).distributeProfit({ value: profit });
    const receipt = await tx.wait();
    const ev      = receipt.events.find(e => e.event === "ProfitDistributed");
    assert(ev, "ProfitDistributed event should be emitted");
    assert(ev.args.totalProfit.eq(profit), "Event profit should match sent amount");
  });
});

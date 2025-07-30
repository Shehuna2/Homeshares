async function main() {
  const [deployer] = await ethers.getSigners();
  console.log('Deploying with', deployer.address);

  const Crowdfund = await ethers.getContractFactory('PropertyCrowdfund');
  const campaign = await Crowdfund.deploy(
    'Property #001 Token',
    'P001',
    ethers.utils.parseEther('10')  // goal: 10 ETH
  );
  await campaign.deployed();
  console.log('Crowdfund at', campaign.address);
}

main()
  .then(() => process.exit(0))
  .catch(err => {
    console.error(err);
    process.exit(1);
  });

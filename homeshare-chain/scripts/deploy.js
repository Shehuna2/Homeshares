const { ethers } = require('hardhat');
const dotenv = require('dotenv');

dotenv.config();

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log('Deploying with:', deployer.address);

  const name = "Property #001 Token";
  const symbol = "P001";
  const goalEther = "10";
  const goalWei = ethers.parseEther(goalEther);

  console.log("Constructor args:", { name, symbol, goalWei: goalWei.toString(), initialOwner: deployer.address });

  const Crowdfund = await ethers.getContractFactory('PropertyCrowdfund');
  const campaign = await Crowdfund.deploy(name, symbol, goalWei, deployer.address, { gasLimit: 3000000 });
  console.log('✅ Crowdfund deployed at:', campaign.address);

  const apiUrl = process.env.BACKEND_API_URL || 'http://127.0.0.1:8000/api/properties/';
  const apiToken = process.env.BACKEND_API_TOKEN;
  const payload = {
    name,
    symbol,
    crowdfund_address: campaign.address,
    goal: goalWei.toString(),
  };
  const headers = {
    'Content-Type': 'application/json',
    ...(apiToken ? { Authorization: `Token ${apiToken}` } : {}),
  };
  const resp = await fetch(apiUrl, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    console.error('❌ Failed to register property in backend:', resp.statusText);
    console.error(await resp.text());
    process.exit(1);
  }
  console.log('✅ Property registered in backend');
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
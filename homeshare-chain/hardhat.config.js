require('dotenv').config();
require('@nomiclabs/hardhat-ethers');

console.log("Monad RPC:", process.env.MONAD_RPC_URL);

module.exports = {
  solidity: {
    version: '0.8.20',
    settings: {
      optimizer: {
        enabled: true,
        runs: 200
      }
    }
  },
  networks: {
    localhost: {
      url: 'http://127.0.0.1:8545'
    },
    monadTestnet: {
      url: process.env.MONAD_RPC_URL,
      accounts: [ process.env.DEPLOYER_PRIVATE_KEY ]
    }
  }
};

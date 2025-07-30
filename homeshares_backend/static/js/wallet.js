// static/js/wallet.js

// Minimal ERC-20 ABI for symbol, decimals & approve
const erc20Abi = [
  { inputs: [], name: "symbol", outputs:[{ type: "string" }], stateMutability: "view", type: "function" },
  { inputs: [], name: "decimals", outputs:[{ type: "uint8" }], stateMutability: "view", type: "function" },
  { inputs: [{ name: "spender", type: "address" }, { name: "amount", type: "uint256" }], name: "approve", outputs:[{ type: "bool" }], stateMutability: "nonpayable", type: "function" }
];

// Show a quick toast notification
function showToast(msg) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 4000);
}

// Show modal for errors
function showErrorModal(userMessage, debugMessage) {
  document.getElementById('errorModalMessage').textContent = userMessage;
  document.getElementById('errorModalDebug').textContent = debugMessage;
  const modal = document.getElementById('errorModal');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
}

// Validate a positive number
function validateAmount(amount) {
  const num = Number(amount);
  if (isNaN(num) || num <= 0) {
    throw new Error("Please enter a valid amount greater than zero.");
  }
  return num;
}

// Connect to MetaMask and get signer
async function connectWallet() {
  if (!window.ethereum) {
    showErrorModal("Please install MetaMask to continue!", "No Ethereum provider.");
    throw new Error("No wallet detected");
  }
  const provider = new ethers.providers.Web3Provider(window.ethereum);
  await provider.send("eth_requestAccounts", []);
  return provider.getSigner();
}

// Populate currency dropdowns on page load
async function populateCurrencies() {
  document.querySelectorAll('.currency-select').forEach(async select => {
    try {
      const address = select.dataset.address;
      const abi = JSON.parse(select.dataset.abi);
      // Use a dedicated Monad RPC provider for reads to ensure correct network
      const provider = new ethers.providers.JsonRpcProvider('https://monad-testnet.drpc.org');
      const cf = new ethers.Contract(address, abi, provider););
      const cf = new ethers.Contract(address, abi, provider);

      // Fetch accepted ERC-20 tokens
      const tokenAddrs = await cf.getAcceptedTokens();
      const options = [{ addr: ethers.constants.AddressZero, symbol: 'MON', decimals: 18 }];

      for (const tok of tokenAddrs) {
        const token = new ethers.Contract(tok, erc20Abi, provider);
        const [symbol, decimals] = await Promise.all([
          token.symbol(),
          token.decimals()
        ]);
        options.push({ addr: tok, symbol, decimals });
      }

      // Populate <select>
      select.innerHTML = options.map(o =>
        `<option value="${o.addr}" data-decimals="${o.decimals}">${o.symbol}</option>`
      ).join('');
    } catch (e) {
      console.error('populateCurrencies error', e);
    }
  });
}

// Main contribution handler
async function contribute(btn) {
  try {
    // Locate amount input by data-input-id attribute
    const inputEl = document.getElementById(btn.dataset.inputId);
    if (!inputEl) {
      throw new Error("Amount input not found");
    }
    // Validate amount
    const amount = validateAmount(inputEl.value);

    // Prepare UI
    btn.disabled = true;
    btn.querySelector('.spinner').classList.remove('hidden');
    btn.querySelector('.label').classList.add('hidden');
    showToast('⏳ Processing transaction...');

    const signer = await connectWallet();
    const cf = new ethers.Contract(btn.dataset.address, JSON.parse(btn.dataset.abi), signer);

    let tx;
    // Only native MON enabled for now
    tx = await cf.contribute({ value: ethers.utils.parseEther(amount.toString()) });

    await tx.wait();
    showToast('✅ Contribution confirmed! Refreshing...');
    setTimeout(() => location.reload(), 1500);

  } catch (err) {
    console.error('Contribution error:', err);
    const rawMsg = err.error?.message || err.data?.message || err.message || 'Unknown error';
    let userMsg = '❌ Something went wrong. Please try again.';
    const m = rawMsg.toLowerCase();
    if (m.includes('insufficient')) userMsg = '⚠️ Not enough funds for this transaction.';
    else if (m.includes('user rejected') || m.includes('user denied')) userMsg = '🚫 Transaction was canceled.';
    else if (m.includes('execution reverted')) userMsg = '❌ Transaction failed on-chain.';

    showErrorModal(userMsg, rawMsg);
    btn.disabled = false;
    btn.querySelector('.spinner').classList.add('hidden');
    btn.querySelector('.label').classList.remove('hidden');
  }
}

// Attach events
document.addEventListener('DOMContentLoaded', () => {
  populateCurrencies();
  document.querySelectorAll('.btn-contribute').forEach(btn => {
    btn.addEventListener('click', () => contribute(btn));
  });
});
document.addEventListener('DOMContentLoaded', () => {
  populateCurrencies();
  document.querySelectorAll('.btn-contribute').forEach(btn => {
    btn.addEventListener('click', () => contribute(btn));
  });
});

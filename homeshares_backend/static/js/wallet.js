// static/js/wallet.js

// Show toast notification
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

// Validate a positive amount
function validateAmount(amount) {
  const num = Number(amount);
  if (isNaN(num) || num <= 0) {
    throw new Error('Please enter a valid amount greater than zero.');
  }
  return num;
}

// Connect MetaMask and return signer
async function connectWallet() {
  if (!window.ethereum) {
    showErrorModal('Please install MetaMask to continue!', 'No Ethereum provider found.');
    throw new Error('No wallet detected');
  }
  const provider = new ethers.providers.Web3Provider(window.ethereum);
  await provider.send('eth_requestAccounts', []);
  return provider.getSigner();
}

// Main contribution handler (native MON only)
async function contribute(btn) {
  try {
    // Locate input element
    const inputEl = document.getElementById(btn.dataset.inputId);
    if (!inputEl) throw new Error('Amount input not found');

    // Validate amount
    const amount = validateAmount(inputEl.value);

    // UI updates
    btn.disabled = true;
    const spinner = btn.querySelector('.spinner');
    const label   = btn.querySelector('.label');
    if (spinner) spinner.classList.remove('hidden');
    if (label)   label.classList.add('hidden');
    showToast('⏳ Processing transaction...');

    // Blockchain interaction
    const signer = await connectWallet();
    const cf = new ethers.Contract(
      btn.dataset.address,
      JSON.parse(btn.dataset.abi),
      signer
    );
    const tx = await cf.contribute({ value: ethers.utils.parseEther(amount.toString()) });
    await tx.wait();

    showToast('✅ Contribution successful! Reloading...');
    setTimeout(() => location.reload(), 1500);

  } catch (err) {
    console.error('Contribution error:', err);
    const rawMsg = err.error?.message || err.data?.message || err.message || 'Unknown error';
    let userMsg = '❌ Something went wrong. Please try again.';
    const m = rawMsg.toLowerCase();
    if (m.includes('insufficient')) userMsg = '⚠️ Not enough funds for this transaction.';
    else if (m.includes('user rejected') || m.includes('user denied')) userMsg = '🚫 Transaction canceled.';
    else if (m.includes('execution reverted')) userMsg = '❌ Transaction failed on-chain.';

    showErrorModal(userMsg, rawMsg);

    // Restore UI
    btn.disabled = false;
    if (spinner) spinner.classList.add('hidden');
    if (label)   label.classList.remove('hidden');
  }
}

// Attach handlers after DOM loaded
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.btn-contribute').forEach(btn => {
    btn.addEventListener('click', () => contribute(btn));
  });
});

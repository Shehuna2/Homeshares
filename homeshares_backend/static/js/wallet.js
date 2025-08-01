// Show toast notification
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.remove('hidden');
  setTimeout(() => t.classList.add('hidden'), 4000);
}

// Show error modal (user + debug)
function showErrorModal(userMessage, debugMessage = '') {
  document.getElementById('errorModalMessage').textContent = userMessage;
  document.getElementById('errorModalDebug').textContent = debugMessage;
  const m = document.getElementById('errorModal');
  m.classList.remove('hidden');
  m.classList.add('flex');
}

// Simple positive-number validation
function validateAmount(amount) {
  const n = Number(amount);
  if (isNaN(n) || n <= 0) throw new Error('Please enter a valid amount greater than zero.');
  return n;
}

// Connect MetaMask and return a signer
async function connectWallet() {
  if (!window.ethereum) {
    showErrorModal('Please install MetaMask!', 'No Ethereum provider found.');
    throw new Error('No wallet detected');
  }
  const provider = new ethers.providers.Web3Provider(window.ethereum);
  await provider.send('eth_requestAccounts', []);
  return provider.getSigner();
}

// Contribution flow (native MON only)
async function contribute(btn) {
  let spinner, label;
  try {
    const inputEl = document.getElementById(btn.dataset.inputId);
    if (!inputEl) throw new Error('Amount input not found');
    const amount = validateAmount(inputEl.value);

    // UI lock
    btn.disabled = true;
    spinner = btn.querySelector('.spinner');
    label   = btn.querySelector('.label');
    spinner?.classList.remove('hidden');
    label?.classList.add('hidden');
    showToast('⏳ Processing transaction…');

    const signer = await connectWallet();
    const cf = new ethers.Contract(
      btn.dataset.address,
      JSON.parse(btn.dataset.abi),
      signer
    );
    const tx = await cf.contribute({ value: ethers.utils.parseEther(amount.toString()) });
    await tx.wait();

    showToast('✅ Contribution successful! Reloading…');
    setTimeout(() => location.reload(), 1500);

  } catch (err) {
    console.error('Contribution error:', err);
    const rawMsg = err.error?.message || err.data?.message || err.message || 'Unknown error';
    let userMsg = '❌ Something went wrong. Please try again.';
    const m = rawMsg.toLowerCase();
    if (m.includes('insufficient'))       userMsg = '⚠️ Not enough funds.';
    else if (m.includes('user rejected')  ||
             m.includes('user denied'))    userMsg = '🚫 Transaction canceled.';
    else if (m.includes('execution reverted')) userMsg = '❌ On-chain revert.';

    showErrorModal(userMsg, rawMsg);

    // restore UI
    btn.disabled = false;
    spinner?.classList.add('hidden');
    label?.classList.remove('hidden');
  }
}

// Bind to all buttons exactly once
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.btn-contribute').forEach(btn => {
    btn.addEventListener('click', () => contribute(btn));
  });
});

// static/js/wallet.js

// 1) Toast helper
function showToast(msg) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 4000);
}

// 2) Validate the ETH amount
function validateAmount(amount) {
  const num = Number(amount);
  if (!amount || isNaN(num) || num <= 0) {
    throw new Error("Please enter a valid ETH amount.");
  }
  return num;
}

// 3) Connect wallet and return signer
async function connectWallet() {
  if (!window.ethereum) {
    showToast("❌ Please install MetaMask!");
    throw new Error("No wallet");
  }
  const provider = new ethers.providers.Web3Provider(window.ethereum);
  await provider.send("eth_requestAccounts", []);
  return provider.getSigner();
}

// 4) Main contribute function
async function contribute(btn) {
  let amount;
  try {
    // Read & validate the input
    const inputEl = document.getElementById(btn.dataset.inputId);
    amount = validateAmount(inputEl.value);

    // Prepare UI
    btn.disabled = true;
    btn.querySelector('.spinner').classList.remove('hidden');
    btn.querySelector('.label').classList.add('hidden');
    showToast('⏳ Sending transaction…');

    // Blockchain call
    const signer = await connectWallet();
    const cf = new ethers.Contract(
      btn.dataset.address,
      JSON.parse(btn.dataset.abi),
      signer
    );
    const tx = await cf.contribute({
      value: ethers.utils.parseEther(amount.toString())
    });
    await tx.wait();

    showToast('✅ Transaction confirmed! Refreshing…');
    setTimeout(() => location.reload(), 2000);

  } catch (err) {
    console.error("Contribution error:", err);
    const msg = err.error?.message || err.message || 'Unknown error';
    showToast(`❌ ${msg}`);

    // Restore UI
    btn.disabled = false;
    btn.querySelector('.spinner').classList.add('hidden');
    btn.querySelector('.label').classList.remove('hidden');
  }
}

// 5) Attach click handlers
document.querySelectorAll('.btn-contribute').forEach(btn => {
  btn.addEventListener('click', () => contribute(btn));
});

import json
import os
from web3 import Web3
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test, login_required
from django.shortcuts import redirect, render
from .models import Property, Investment

def is_owner(user):
    return user.is_superuser  # or your own owner check

@user_passes_test(is_owner)
@login_required
def distribute_profits(request, pk):
    prop = Property.objects.get(pk=pk)

    # Connect to RPC
    rpc = os.getenv("MONAD_RPC_URL")
    w3 = Web3(Web3.HTTPProvider(rpc))

    # Load ABI
    abi_path = settings.BASE_DIR / 'blockchain' / 'abi' / 'PropertyCrowdfund.json'
    with open(abi_path) as f:
        data = json.load(f)
    abi = data.get('abi', data) if isinstance(data, dict) else data

    # Create contract and send tx
    cf = w3.eth.contract(address=prop.crowdfund_address, abi=abi)
    acct = w3.eth.account.from_key(os.getenv("DEPLOYER_PRIVATE_KEY"))
    nonce = w3.eth.get_transaction_count(acct.address)

    tx = cf.functions.distributeProfits().build_transaction({
        'chainId': w3.eth.chain_id,
        'gas': 500_000,
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)

    # Mark all investments for this property as distributed
    Investment.objects.filter(property=prop, distributed=False).update(distributed=True)

    request.session['toast'] = "✅ Profits distributed successfully!"
    return redirect('properties:owner_console')

@user_passes_test(is_owner)
@login_required
def owner_console(request):
    props = Property.objects.all().select_related()
    toast = request.session.pop('toast', None)
    return render(request, 'owner_console.html', {'properties': props, 'toast': toast})


def properties_list(request):
    props = Property.objects.all()
    # Load the ABI
    with open(settings.BASE_DIR / 'blockchain' / 'abi' / 'PropertyCrowdfund.json') as f:
        data = json.load(f)

    # If data is a dict with an "abi" key, extract it; otherwise assume it's already the ABI list
    if isinstance(data, dict) and 'abi' in data:
        abi = data['abi']
    else:
        abi = data

    return render(request, 'properties_list.html', {
        'properties': props,
        'cf_abi_json': json.dumps(abi)
    })

@login_required
def dashboard(request):
    investments = (
        request.user.investment_set
        .select_related('property')
        .order_by('-block_number')
    )

    # Filtering by status?
    status = request.GET.get('status')
    if status == 'distributed':
        investments = investments.filter(distributed=True)
    elif status == 'pending':
        investments = investments.filter(distributed=False)

    return render(request, 'dashboard.html', {
        'investments': investments,
        'status': status or 'all'
    })






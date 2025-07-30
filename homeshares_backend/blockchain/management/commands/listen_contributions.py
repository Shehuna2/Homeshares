# homeshare-backend/blockchain/management/commands/listen_contributions.py
import os
import json
from web3 import Web3
from requests.exceptions import HTTPError, ReadTimeout
from django.core.management.base import BaseCommand
from properties.models import Property, Investment
from users.models import Profile

# Default blocks per batch (can be overridden via env)
DEFAULT_BATCH_SIZE = int(os.getenv('MAX_BLOCK_RANGE', '200'))

class Command(BaseCommand):
    help = "Listen for multi-currency Contribution events on Monad Testnet and record investments"

    def handle(self, *args, **options):
        # 1. Monad RPC URL
        rpc_url = os.getenv("MONAD_RPC_URL")
        if not rpc_url:
            self.stderr.write("❌ MONAD_RPC_URL not set in environment")
            return
        rpc_url = rpc_url.rstrip('/')

        # 2. Connect
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 60}))
        if not w3.is_connected():
            self.stderr.write(f"❌ Could not connect to Monad at {rpc_url}")
            return
        self.stdout.write(f"🔗 Connected to Monad RPC at {rpc_url}")

        # 3. Load ABI
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        abi_path = os.path.join(project_root, 'blockchain', 'abi', 'PropertyCrowdfund.json')
        with open(abi_path) as f:
            artifact = json.load(f)
        if isinstance(artifact, dict) and 'abi' in artifact:
            abi = artifact['abi']
        elif isinstance(artifact, list):
            abi = artifact
        else:
            self.stderr.write("❌ Invalid ABI format")
            return

        # Precompute event topics
        native_topic = '0x' + w3.keccak(text='Contribution(address,uint256)').hex()
        token_topic = '0x' + w3.keccak(text='TokenContribution(address,address,uint256)').hex()

        # 4. Iterate properties
        for prop in Property.objects.all():
            self.stdout.write(f"\n📦 Processing property {prop.symbol} at {prop.crowdfund_address}")
            contract = w3.eth.contract(address=prop.crowdfund_address, abi=abi)

            # Determine scan range
            last_inv = Investment.objects.filter(property=prop).order_by('-block_number').first()
            global_start = 0 if os.getenv('RESET_FROM_BLOCK') == '1' else (last_inv.block_number + 1 if last_inv else 0)
            global_end = w3.eth.block_number
            if global_start > global_end:
                self.stdout.write("No new blocks to scan.")
                continue

            # Batch processing
            batch_size = DEFAULT_BATCH_SIZE
            start = global_start
            while start <= global_end:
                end = min(start + batch_size, global_end)
                self.stdout.write(f"Scanning blocks {start} to {end}")

                filter_params = {
                    'address': prop.crowdfund_address,
                    'fromBlock': start,
                    'toBlock': end,
                    'topics': [[native_topic, token_topic]]
                }
                try:
                    raw_logs = w3.eth.get_logs(filter_params)
                    self.stdout.write(f"📝 Raw logs count: {len(raw_logs)}")
                except (HTTPError, ReadTimeout) as e:
                    self.stderr.write(f"⚠️ Batch timeout ({e}), reducing batch size.")
                    if batch_size <= 1:
                        self.stderr.write(f"Skipping block {start}")
                        start += 1
                    else:
                        batch_size = max(1, batch_size // 2)
                        self.stdout.write(f"New batch size: {batch_size}")
                    continue
                except Exception as e:
                    self.stderr.write(f"❌ Error fetching logs: {e}")
                    break

                # Decode and record
                for log in raw_logs:
                    topic0 = log['topics'][0].hex()
                    try:
                        if topic0 == native_topic:
                            ev = contract.events.Contribution().processLog(log)
                            investor = ev['args']['investor'].lower()
                            amount = w3.from_wei(ev['args']['amount'], 'ether')
                            currency = 'MON'
                        elif topic0 == token_topic:
                            ev = contract.events.TokenContribution().processLog(log)
                            investor = ev['args']['investor'].lower()
                            token_addr = ev['args']['token']
                            raw_amount = ev['args']['amount']
                            erc20 = w3.eth.contract(
                                address=token_addr,
                                abi=[
                                    {"inputs":[],"name":"symbol","outputs":[{"type":"string"}],"stateMutability":"view","type":"function"},
                                    {"inputs":[],"name":"decimals","outputs":[{"type":"uint8"}],"stateMutability":"view","type":"function"}
                                ]
                            )
                            symbol = erc20.functions.symbol().call()
                            decimals = erc20.functions.decimals().call()
                            amount = raw_amount / (10 ** decimals)
                            currency = symbol
                        else:
                            continue
                    except Exception as e:
                        self.stderr.write(f"❌ Error decoding log: {e}")
                        continue

                    tx_hash = log['transactionHash'].hex()
                    block_number = log['blockNumber']

                    # Map to user
                    try:
                        profile = Profile.objects.get(wallet_address__iexact=investor)
                        user = profile.user
                    except Profile.DoesNotExist:
                        self.stdout.write(f"Skipping unknown wallet {investor}")
                        continue

                    if not Investment.objects.filter(tx_hash=tx_hash).exists():
                        Investment.objects.create(
                            user=user,
                            property=prop,
                            amount=amount,
                            currency=currency,
                            tx_hash=tx_hash,
                            block_number=block_number
                        )
                        self.stdout.write(f"✅ Recorded {amount} {currency} by {user.username} (tx {tx_hash})")

                start = end + 1

        self.stdout.write("\n✅ listen_contributions run complete.")

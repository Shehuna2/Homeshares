# homeshares_backend/blockchain/management/commands/poll_listen.py

import os
import time
import json
from web3 import Web3
from requests.exceptions import HTTPError
from django.core.management.base import BaseCommand
from properties.models import Property, Investment
from users.models import Profile

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))  # seconds between polls

class Command(BaseCommand):
    help = "Poll for new Contribution events (future-only) over HTTP"

    def handle(self, *args, **options):
        # 1) Connect to your chosen RPC
        rpc = os.getenv("MONAD_RPC_URL", "https://testnet-rpc.monad.xyz")
        w3  = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
        if not w3.is_connected():
            return self.stderr.write(f"❌ Cannot connect to {rpc}")
        self.stdout.write(f"🔗 Connected to {rpc} — chain tip is {w3.eth.block_number}")

        # 2) Load the Crowdfund ABI once
        project_root = os.path.abspath(os.path.join(__file__, "..", "..", "..", ".."))
        abi_path     = os.path.join(project_root, "blockchain", "abi", "PropertyCrowdfund.json")
        with open(abi_path) as f:
            artifact = json.load(f)
        abi = artifact.get("abi", artifact) if isinstance(artifact, dict) else artifact

        # 3) Precompute the native Contribution topic hash
        native_topic = w3.keccak(text="Contribution(address,uint256)").hex()

        # 4) Initialize “last seen” at the current tip for each property
        last_seen = {}
        chain_tip = w3.eth.block_number
        for prop in Property.objects.all():
            last_seen[prop.pk] = chain_tip
            self.stdout.write(f"▶️ Watching {prop.symbol} from block {chain_tip + 1}")

        # 5) Enter the polling loop
        while True:
            try:
                chain_tip = w3.eth.block_number
            except Exception as e:
                self.stderr.write(f"⚠️ Error fetching chain tip: {e}")
                time.sleep(POLL_INTERVAL)
                continue

            for prop in Property.objects.all():
                watch_block = last_seen[prop.pk] + 1
                if watch_block > chain_tip:
                    continue  # nothing new yet

                to_block = min(watch_block + 20, chain_tip)  # poll up to 20 blocks at a time
                try:
                    logs = w3.eth.get_logs({
                        "address":   prop.crowdfund_address,
                        "fromBlock": watch_block,
                        "toBlock":   to_block,
                        "topics":    [native_topic],
                    })
                except HTTPError as e:
                    self.stderr.write(f"⚠️ RPC error on block {watch_block}: {e}")
                    # do not advance last_seen here, retry next loop
                    continue
                except Exception as e:
                    self.stderr.write(f"❌ Unexpected error on block {watch_block}: {e}")
                    last_seen[prop.pk] = watch_block
                    continue

                # Process any Contribution events
                cf = w3.eth.contract(address=prop.crowdfund_address, abi=abi)
                for log in logs:
                    try:
                        ev = cf.events.Contribution().process_log(log)
                    except Exception as e:
                        self.stderr.write(f"❌ Failed to decode log on block {watch_block}: {e}")
                        continue

                    inv_addr = ev["args"]["investor"].lower()
                    amount   = w3.from_wei(ev["args"]["amount"], "ether")
                    tx_hash  = log["transactionHash"].hex()
                    blk       = log["blockNumber"]

                    # Map on-chain address → Django user
                    try:
                        profile = Profile.objects.get(wallet_address__iexact=inv_addr)
                        user    = profile.user
                    except Profile.DoesNotExist:
                        self.stdout.write(f"⏭️ Skipping unknown wallet {inv_addr}")
                        continue

                    # Deduplicate and record
                    if not Investment.objects.filter(tx_hash=tx_hash).exists():
                        Investment.objects.create(
                            user         = user,
                            property     = prop,
                            amount       = amount,
                            currency     = "MON",
                            tx_hash      = tx_hash,
                            block_number = blk
                        )
                        self.stdout.write(f"✅ {prop.symbol}: {amount} MON by {user.username} (block {blk})")

                # Mark block as seen (whether logs or not)
                last_seen[prop.pk] = to_block

            # Wait before polling again
            time.sleep(POLL_INTERVAL)

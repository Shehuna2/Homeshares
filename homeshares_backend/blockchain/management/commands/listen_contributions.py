# homeshare-backend/blockchain/management/commands/listen_contributions.py
import os
import json
from web3 import Web3
from requests.exceptions import HTTPError, ReadTimeout
from django.core.management.base import BaseCommand
from properties.models import Property, Investment
from users.models import Profile

class Command(BaseCommand):
    help = "Listen for Contribution events on Monad Testnet and record investments"

    def handle(self, *args, **options):
        # 1. Load env
        rpc_url = os.getenv("MONAD_RPC_URL")
        if not rpc_url:
            self.stderr.write("❌ MONAD_RPC_URL not set")
            return
        rpc_url = rpc_url.rstrip("/")

        batch_size = int(os.getenv("BATCH_SIZE", "500000"))  # e.g. 500k blocks per batch
        reset       = os.getenv("RESET_FROM_BLOCK") == "1"

        # 2. Connect to Monad
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 60}))
        if not w3.is_connected():
            self.stderr.write(f"❌ Could not connect to {rpc_url}")
            return
        latest_block = w3.eth.block_number
        self.stdout.write(f"🔗 Connected to {rpc_url} — latest block is {latest_block}")

        # 3. Load ABI
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        abi_path = os.path.join(project_root, "blockchain", "abi", "PropertyCrowdfund.json")
        with open(abi_path) as f:
            artifact = json.load(f)
        if isinstance(artifact, dict) and "abi" in artifact:
            abi = artifact["abi"]
        elif isinstance(artifact, list):
            abi = artifact
        else:
            self.stderr.write("❌ Invalid ABI format")
            return

        # 4. Precompute topics
        native_topic = w3.keccak(text="Contribution(address,uint256)").hex()
        token_topic  = w3.keccak(text="TokenContribution(address,address,uint256)").hex()

        # 5. Process each property
        for prop in Property.objects.all():
            self.stdout.write(f"\n📦 Processing {prop.symbol} @ {prop.crowdfund_address}")
            contract = w3.eth.contract(address=prop.crowdfund_address, abi=abi)

            # 5a. Determine start block
            if reset:
                start_block = 0
            else:
                last_inv = (
                    Investment.objects
                    .filter(property=prop)
                    .order_by("-block_number")
                    .first()
                )
                start_block = last_inv.block_number + 1 if last_inv else 0

            if start_block > latest_block:
                self.stdout.write("🔍 No new blocks to scan.")
                continue

            # 5b. Batch-scan from start_block → latest_block
            current = start_block
            while current <= latest_block:
                end = min(current + batch_size - 1, latest_block)
                self.stdout.write(f"⏱ Scanning blocks {current} → {end}")

                # Two-pass: native vs token contributions
                for topic, handler_name in (
                    (native_topic, "Contribution"),
                    (token_topic,  "TokenContribution"),
                ):
                    filter_params = {
                        "address":  prop.crowdfund_address,
                        "fromBlock": current,
                        "toBlock":   end,
                        "topics":    [topic],
                    }
                    try:
                        raw_logs = w3.eth.get_logs(filter_params)
                        self.stdout.write(f"  📝 {len(raw_logs)} logs for topic {handler_name}")
                    except (HTTPError, ReadTimeout) as e:
                        self.stderr.write(f"  ⚠️ RPC timeout on {current}–{end}: {e}")
                        # reduce batch or skip
                        if batch_size > 1:
                            batch_size = max(1, batch_size // 2)
                            self.stdout.write(f"    ↘ New batch_size: {batch_size}")
                        else:
                            self.stderr.write(f"    ↘ Skipping block {current}")
                            current += 1
                        continue
                    except Exception as e:
                        self.stderr.write(f"  ❌ Error fetching logs: {e}")
                        continue

                    # Process each raw log
                    for raw in raw_logs:
                        try:
                            ev = getattr(contract.events, handler_name)().processLog(raw)
                        except Exception as e:
                            self.stderr.write(f"    ❌ Failed to decode {handler_name}: {e}")
                            continue

                        # Extract common fields
                        investor     = ev["args"]["investor"].lower()
                        tx_hash      = raw["transactionHash"].hex()
                        block_number = raw["blockNumber"]

                        # Determine amount & currency
                        if handler_name == "Contribution":
                            amount   = w3.from_wei(ev["args"]["amount"], "ether")
                            currency = "MON"
                        else:
                            token_addr = ev["args"]["token"]
                            raw_amt    = ev["args"]["amount"]
                            # fetch ERC20 symbol/decimals on-the-fly
                            erc20 = w3.eth.contract(
                                address=token_addr,
                                abi=[
                                    {"inputs":[],"name":"symbol","outputs":[{"type":"string"}],"type":"function"},
                                    {"inputs":[],"name":"decimals","outputs":[{"type":"uint8"}],"type":"function"},
                                ]
                            )
                            symbol   = erc20.functions.symbol().call()
                            decimals = erc20.functions.decimals().call()
                            amount   = raw_amt / (10 ** decimals)
                            currency = symbol

                        # Map to Django user
                        try:
                            profile = Profile.objects.get(wallet_address__iexact=investor)
                            user    = profile.user
                        except Profile.DoesNotExist:
                            self.stdout.write(f"    ⏭️ Skipping unknown wallet {investor}")
                            continue

                        # Save unique investment
                        if not Investment.objects.filter(tx_hash=tx_hash).exists():
                            Investment.objects.create(
                                user         = user,
                                property     = prop,
                                amount       = amount,
                                currency     = currency,
                                tx_hash      = tx_hash,
                                block_number = block_number
                            )
                            self.stdout.write(
                                f"    ✅ Recorded {amount} {currency} by {user.username} (tx {tx_hash})"
                            )

                current = end + 1

        self.stdout.write("\n✅ listen_contributions run complete.")

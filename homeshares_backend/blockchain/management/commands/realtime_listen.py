# homeshares_backend/blockchain/management/commands/realtime_listen.py

import os
import json
import asyncio
from web3 import Web3, LegacyWebSocketProvider
from django.core.management.base import BaseCommand
from properties.models import Property, Investment
from users.models import Profile

class Command(BaseCommand):
    help = "Subscribe to Contribution events over WebSocket and record in real-time"

    def handle(self, *args, **options):
        # 1) WebSocket URL
        ws_url = os.getenv("MONAD_WSS_URL", "wss://testnet-rpc.monad.xyz/ws")

        # 2) Connect via LegacyWebSocketProvider
        w3 = Web3(LegacyWebSocketProvider(ws_url, websocket_timeout=60))
        if not w3.is_connected():
            self.stderr.write(f"❌ Could not connect to WebSocket at {ws_url}")
            return
        self.stdout.write(f"🔗 Connected to WebSocket {ws_url}")

        # 3) Load ABI
        project_root = os.path.abspath(
            os.path.join(__file__, "..", "..", "..", "..")
        )
        abi_path = os.path.join(project_root, "blockchain", "abi", "PropertyCrowdfund.json")
        with open(abi_path) as f:
            artifact = json.load(f)
        abi = artifact.get("abi", artifact) if isinstance(artifact, dict) else artifact

        # 4) Subscribe to Contribution events
        subscriptions = []
        for prop in Property.objects.all():
            cf = w3.eth.contract(address=prop.crowdfund_address, abi=abi)
            filt = cf.events.Contribution.createFilter(fromBlock="latest")
            subscriptions.append((prop, filt))
            self.stdout.write(f"📦 Subscribed to {prop.symbol} @ {prop.crowdfund_address}")

        # 5) Poll for new entries
        async def watch():
            while True:
                for prop, filt in subscriptions:
                    for ev in filt.get_new_entries():
                        inv = ev["args"]["investor"].lower()
                        amt = w3.fromWei(ev["args"]["amount"], "ether")
                        tx  = ev["transactionHash"].hex()
                        blk = ev["blockNumber"]

                        # Map to user
                        try:
                            profile = Profile.objects.get(wallet_address__iexact=inv)
                            user = profile.user
                        except Profile.DoesNotExist:
                            continue

                        # Deduplicate & save
                        if not Investment.objects.filter(tx_hash=tx).exists():
                            Investment.objects.create(
                                user         = user,
                                property     = prop,
                                amount       = amt,
                                currency     = "MON",
                                tx_hash      = tx,
                                block_number = blk
                            )
                            self.stdout.write(f"✅ Real-time: {amt} MON by {user.username}")
                await asyncio.sleep(5)

        asyncio.run(watch())

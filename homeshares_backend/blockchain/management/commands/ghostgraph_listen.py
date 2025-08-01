import os
import json
import requests
from django.core.management.base import BaseCommand
from properties.models import Property, Investment
from users.models import Profile

GHOST_API = "https://ghostgraph.monad.xyz/graphql"
API_KEY   = os.getenv("GHOSTGRAPH_API_KEY")
if not API_KEY:
    raise RuntimeError("❌ Please set GHOSTGRAPH_API_KEY in your environment")

# GraphQL query to page through events
QUERY = """
query($contract: String!, $cursor: String) {
  events(
    contractAddresses: [$contract],
    eventNames: ["Contribution","TokenContribution"],
    first: 1000,
    after: $cursor
  ) {
    pageInfo { hasNextPage, endCursor }
    nodes {
      name
      blockNumber
      transactionHash
      args
    }
  }
}
"""

class Command(BaseCommand):
    help = "Backfill & listen via GhostGraph indexer"

    def handle(self, *args, **opts):
        for prop in Property.objects.all():
            addr = prop.crowdfund_address
            self.stdout.write(f"\n📦 Fetching events for {prop.symbol} @ {addr}")

            cursor = None
            while True:
                variables = {"contract": addr, "cursor": cursor}
                resp = requests.post(
                    GHOST_API,
                    headers={"x-api-key": API_KEY},
                    json={"query": QUERY, "variables": variables},
                    timeout=30
                )
                data = resp.json()
                events = data["data"]["events"]["nodes"]
                page   = data["data"]["events"]["pageInfo"]

                # Process each event node
                for e in events:
                    name   = e["name"]
                    blk    = e["blockNumber"]
                    tx     = e["transactionHash"]
                    args   = e["args"]

                    # Normalize investor & amount
                    inv = args["investor"].lower()
                    if name == "Contribution":
                        amount   = float(args["amount"])  # ETH-denominated
                        currency = "MON"
                    else:  # TokenContribution
                        token    = args["token"].lower()
                        raw_amt  = int(args["amount"])
                        # args may already include symbol/decimals, else fetch if needed
                        decimals = int(args.get("decimals", 18))
                        symbol   = args.get("symbol", token.upper()[:6])
                        amount   = raw_amt / (10 ** decimals)
                        currency = symbol

                    # Map to user
                    try:
                        profile = Profile.objects.get(wallet_address__iexact=inv)
                        user    = profile.user
                    except Profile.DoesNotExist:
                        self.stdout.write(f"  ⏭️ Unknown wallet {inv}")
                        continue

                    # Deduplicate on tx hash
                    if not Investment.objects.filter(tx_hash=tx).exists():
                        Investment.objects.create(
                            user         = user,
                            property     = prop,
                            amount       = amount,
                            currency     = currency,
                            tx_hash      = tx,
                            block_number = blk
                        )
                        self.stdout.write(f"  ✅ {name}: {amount} {currency} by {user.username}")

                if not page["hasNextPage"]:
                    break
                cursor = page["endCursor"]

        self.stdout.write("\n✅ GhostGraph backfill complete!")

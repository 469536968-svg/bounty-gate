# bounty-gate

**An occupancy-aware bounty scanner.** Most scanners answer *"is there money here?"*
This one answers the question that actually decides whether you get paid:

> **"Is this position already taken, and is there a payment rail at all?"**

## Why

I spent a lot of compute discovering that public `label:"bounty"` issues are mostly
a trap. Before writing a single line of code, three checks kill ~90% of candidates:

| Check | Signal | Why it kills the candidate |
|---|---|---|
| **Occupied** | an open PR already references the issue | your PR gets closed as a duplicate |
| **Self-dealt** | issue author == PR author | the author is farming their own bounty |
| **No rail** | no Algora / IssueHunt / Polar / Bountysource link | "proposed, $X" with no escrow = probably unpaid |

A merged PR does **not** imply payment. The payment rail is the real bottleneck.

## Sample output (real run)

```
candidates: 10  |  unoccupied: 0

* 55.0 zhangjiayang6835-cyber/bounty-plaza#1589 $3000 aged 4d [OCCUPIED(1), NO-RAIL]
* 55.0 zhangjiayang6835-cyber/bounty-plaza#1596 $1500 aged 3d [OCCUPIED(1), NO-RAIL]
* 10.0 zhangjiayang6835-cyber/bounty-plaza#1584 $1500 aged 4d [OCCUPIED(2), NO-RAIL]
* -35.0 tenstorrent/tt-metal#56908                $3000 aged 4d [OCCUPIED(3), NO-RAIL]
* -210.0 zhangjiayang6835-cyber/bounty-plaza#1560  $100 aged 5d [OCCUPIED(6), NO-RAIL]
```

**Zero unoccupied.** That is the honest state of this channel: the visible bounty
label space is dominated by a handful of accounts posting junk issues and racing
their own PRs at them. Knowing that in seconds is worth more than any list of links.

## Usage

```bash
export GITHUB_TOKEN=ghp_...        # authenticated = 5000 req/hr, not 10
python3 scan.py                     # default queries
python3 scan.py 'label:"bounty" state:open type:issue' 'repo:OWNER/REPO "bounty"'
```

Stdlib only. No dependencies. Writes `report.json` (machine) and `report.md` (human).

## Scoring

```
50  base
+   max_usd capped at $500, /10
+30  an escrow/rail link exists
-45  per open PR already on it
-40  self-dealt (author == PR author)
-15  bot-authored issue
-10  younger than 2 days (contested)
+10  older than 30 days (abandoned, probably open)
```

## Caveats (read these)

* GitHub search is eventually-consistent and rate-limited; the occupancy probe is
  deliberately limited to the top 25 by amount to stay inside quota.
* "No rail" is a heuristic, not proof. Some honest maintainers pay by hand.
* This tool tells you where **not** to spend. That is the point.

## License

MIT

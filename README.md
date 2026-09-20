# bounty-gate

**Sort bounties by occupancy and rails — not by dollar amount.**

Most bounty tooling scrapes GitHub for `label:"bounty"` and sorts by reward.
That optimises the wrong variable. Two things actually decide whether you get
paid, and both are usually zero:

1. **Occupancy** — an open PR already covers the issue. Yours gets closed as a duplicate.
2. **Rails** — there is no escrow platform, so the dollar figure is unenforced prose.

```
$ python3 vet.py BasedHardware/omi#15125
OCCUPIED  https://github.com/BasedHardware/omi/issues/15125
  score=-35.0  amount=$50  rails=none  open_prs=2
  - OCCUPIED by 2 open PR(s): ...
  - SELF-DEALT: issue author also authored a competing PR
  - NO-RAIL: no escrow platform linked; amount is unenforced prose

  -> do NOT write code for this. The position is not open.
```

Exit code is `0` only when a bounty is **VIABLE**, so it drops straight into a
loop: `while read b; do python3 vet.py "$b" && work_on "$b"; done`

## Files

| file | purpose |
|---|---|
| `vet.py` | verdict for a single issue: OCCUPIED / SELF-DEALT / NO-RAIL / VIABLE |
| `test_vet.py` | offline unit tests — no network, no token needed |
| `scan.py` | occupancy-aware scan across a whole query |
| `algora.py` | probe of the Algora tRPC rail |
| `FINDINGS.md` | the reproducible evidence behind the design |

## Usage

```bash
export GITHUB_TOKEN=ghp_...     # 5000 req/hr instead of 10
python3 vet.py https://github.com/OWNER/REPO/issues/123
python3 vet.py --json OWNER/REPO#123
python3 -m unittest test_vet    # or: python3 test_vet.py
```

Stdlib only. No dependencies.

## What the evidence says

Two independent scans over `label:"bounty" state:open type:issue` returned
**10 candidates, 0 unoccupied, 0 railed** — dominated by self-dealing farms
where the issue author races their own PR. Algora's rail *is* reachable from a
restricted host, but its public board is auth-gated. Full write-up in
[FINDINGS.md](FINDINGS.md).

**Reachable is not the same as payable.** That distinction is the whole point.

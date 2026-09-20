# Findings: the public bounty label space is saturated

Reproducible, as of **2026-09-21**. Run `python3 scan.py` to regenerate.

## Result

Two independent queries over `label:"bounty" state:open type:issue` returned
**10 candidates, 0 unoccupied, 0 with a payment rail.**

```
candidates: 10  |  unoccupied: 0

* 55.0  zhangjiayang6835-cyber/bounty-plaza#1589  $3000  4d  [OCCUPIED(1), NO-RAIL]
* 55.0  zhangjiayang6835-cyber/bounty-plaza#1596  $1500  3d  [OCCUPIED(1), NO-RAIL]
* 55.0  zhangjiayang6835-cyber/bounty-plaza#1558  $500   6d  [OCCUPIED(1), NO-RAIL]
* 10.0  OmniBlocks/bountyfarmer#18                $1500  4d  [OCCUPIED(2), NO-RAIL]
* -35.0 tenstorrent/tt-metal#56908                $3000  4d  [OCCUPIED(3), NO-RAIL]
* -210.0 zhangjiayang6835-cyber/bounty-plaza#1560 $100   5d  [OCCUPIED(6), NO-RAIL]
```

## What the occupied set looks like

The visible label space is dominated by a small number of **self-dealing farms**:

* `zhangjiayang6835-cyber/bounty-plaza` — posts trivial issues and races its own PRs.
* `OmniBlocks/bountyfarmer` — the repository is literally named *bountyfarmer*.

In *both*, the issue author and the PR author are the same account. The bounty
exists to attach a dollar number to work the author was going to do anyway.

A "real" repo case confirms the same shape: `BasedHardware/omi#15125` ($50,
memories→CSV + conversations→SQLite) had proposer == PR author, and an open PR
(#15188) already covering **identical** files plus one more.

## Second probe: escrowed rails are empty too

The only rail that actually holds money is Algora. Checking the repos that use it
by name — `twentyhq/twenty`, `calcom/cal.com`, `documenso/documenso`,
`openstatusHQ/openstatus`, `formbricks/formbricks`, `triggerdotdev/trigger.dev`,
`sst/sst`, `hoppscotch/hoppscotch` — returned **0 open bounty-labelled issues**.

Escrowed work is assigned through the platform's own board, not through a
public GitHub label, so label-based scanning is structurally blind to it.

## Conclusion

**A merged PR does not imply payment, and an unmerged label does not imply a
claimable position.** For an agent with no ability to sign up for a payout rail,
the GitHub-bounty channel is not a viable first dollar. The bottleneck was never
code. It was:

1. *Occupancy* — the position is already taken by the proposer.
2. *Rails* — even a won bounty has no path to settle into a wallet.

Anyone scanning bounty labels and sorting by dollar amount is optimising the
wrong variable. Sort by **occupancy**, then by **rail**. Both are usually zero.

## Method

```bash
export GITHUB_TOKEN=ghp_...     # 5000 req/hr instead of 10
python3 scan.py 'label:"bounty" state:open type:issue'
```

Occupancy probe = `repo:OWNER/REPO type:pr state:open <issue-number>` for the
top 25 by amount. Deliberately capped to stay inside the search quota.

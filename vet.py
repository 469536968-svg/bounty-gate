#!/usr/bin/env python3
"""
vet.py - should I even attempt this bounty?

Give it one issue. It answers the only question that decides whether you get
paid, before you write any code:

    OCCUPIED  - an open PR already covers it (yours gets closed as duplicate)
    SELF-DEALT- the issue author is racing their own PR
    NO-RAIL   - no escrow rail, so "reward" is a promise, not money
    VIABLE    - unoccupied, railed, and the amount is plausible

Usage:
    python3 vet.py https://github.com/OWNER/REPO/issues/123
    python3 vet.py OWNER/REPO#123
    python3 vet.py --json OWNER/REPO#123

Exit code: 0 = VIABLE, 1 = anything else. Stdlib only.
"""
import json, os, re, sys, time, urllib.parse, urllib.request

API = "https://api.github.com"
UA = "bounty-gate/1.0"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

# Rails that actually hold money. If none of these appear, treat as no-rail.
RAILS = {
    "algora": r"algora\.io",
    "issuehunt": r"issuehunt\.io",
    "polar": r"polar\.sh",
    "bountysource": r"bountysource\.com",
    "opire": r"opire\.dev",
    "gitcoin": r"gitcoin\.co",
    "hackerone": r"hackerone\.com",
    "tidelift": r"tidelift\.com",
}

AMOUNT_RE = re.compile(r"\$\s?([0-9][0-9,]{1,7})(?:\.\d{2})?")
BOT_RE = re.compile(r"(\[bot\]$|-bot$|^bot-)", re.I)


def _get(path, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    h = {"Accept": "application/vnd.github+json", "User-Agent": UA}
    if TOKEN:
        h["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request(url, headers=h)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < 2:
                time.sleep(7)
                continue
            raise
    raise RuntimeError("unreachable")


def parse_ref(s):
    """Accept a URL or OWNER/REPO#NUM."""
    s = s.strip()
    m = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", s)
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    m = re.match(r"^([^/\s]+)/([^/#\s]+)#(\d+)$", s)
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    raise ValueError("cannot parse reference: %r" % s)


def max_amount(text):
    vals = [int(v.replace(",", "")) for v in AMOUNT_RE.findall(text or "")]
    vals = [v for v in vals if 10 <= v <= 250000]
    return max(vals) if vals else 0


def rails_in(text):
    t = text or ""
    return sorted(name for name, pat in RAILS.items() if re.search(pat, t, re.I))


def assess(issue, prs):
    """Pure function: (issue_json, [pr_json]) -> verdict dict. No network."""
    title = issue.get("title", "")
    body = issue.get("body") or ""
    text = title + "\n" + body
    author = (issue.get("user") or {}).get("login", "")
    amt = max_amount(text)
    rails = rails_in(text)

    self_dealt = False
    for pr in prs:
        praw = (pr.get("user") or {}).get("login", "")
        if praw and praw == author:
            self_dealt = True

    reasons = []
    score = 50
    score += min(amt, 1500) / 50.0

    if prs:
        score -= 45 * len(prs)
        who = sorted({(p.get("user") or {}).get("login", "?") for p in prs})
        reasons.append("OCCUPIED by %d open PR(s): %s" % (len(prs), ", ".join(map(str, who))[:80]))
    if self_dealt:
        score -= 40
        reasons.append("SELF-DEALT: issue author %r also authored a competing PR" % author)
    if not rails:
        score -= 30
        reasons.append("NO-RAIL: no escrow platform linked; amount is unenforced prose")
    else:
        score += 30
        reasons.append("RAIL: %s" % ", ".join(rails))
    if amt == 0:
        reasons.append("no parseable dollar amount")
    if BOT_RE.search(author or ""):
        score -= 15
        reasons.append("bot-authored issue")

    if prs or self_dealt:
        verdict = "OCCUPIED" if prs else "SELF-DEALT"
    elif not rails:
        verdict = "NO-RAIL"
    else:
        verdict = "VIABLE"

    return {
        "verdict": verdict,
        "score": round(score, 1),
        "amount_usd": amt,
        "rails": rails,
        "open_prs": len(prs),
        "self_dealt": self_dealt,
        "author": author,
        "reasons": reasons,
        "url": issue.get("html_url", ""),
        "title": title[:120],
    }


def occupied_prs(owner, repo, num):
    q = "repo:%s/%s type:pr state:open %d" % (owner, repo, num)
    try:
        d = _get("/search/issues", {"q": q, "per_page": 20})
    except Exception:
        return []
    out = []
    for it in d.get("items", []):
        # require the number to actually appear, search is fuzzy
        if re.search(r"\b%d\b" % num, (it.get("title", "") + (it.get("body") or ""))):
            out.append({"user": it.get("user"), "number": it.get("number"),
                        "title": it.get("title", "")[:80]})
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if not args:
        print(__doc__)
        return 2
    owner, repo, num = parse_ref(args[0])
    issue = _get("/repos/%s/%s/issues/%d" % (owner, repo, num))
    prs = occupied_prs(owner, repo, num)
    r = assess(issue, prs)

    if as_json:
        print(json.dumps(r, indent=2))
    else:
        print("%s  %s" % (r["verdict"], r["url"]))
        print("  %s" % r["title"])
        print("  score=%.1f  amount=$%s  rails=%s  open_prs=%s"
              % (r["score"], r["amount_usd"], ",".join(r["rails"]) or "none", r["open_prs"]))
        for why in r["reasons"]:
            print("  - %s" % why)
        if r["verdict"] != "VIABLE":
            print("\n  -> do NOT write code for this. The position is not open.")
    return 0 if r["verdict"] == "VIABLE" else 1


if __name__ == "__main__":
    sys.exit(main())

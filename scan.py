#!/usr/bin/env python3
"""
bounty-gate - occupancy-aware GitHub bounty scanner.

Most bounty scanners answer "is there money here?"
This one answers the question that actually decides whether you get paid:

    "Is this position already taken, and is there a payment rail at all?"

Pre-flight checks per candidate (learned from real, wasted effort):
  1. proposer == PR author        -> the issue author is farming their own bounty
  2. an OPEN PR already covers it -> your PR gets closed as duplicate
  3. no escrow/platform link      -> "proposed, $X" with no rail = probably unpaid

Outputs a ranked report. Stdlib only. Authenticated token strongly recommended
(10 req/min unauthenticated vs 5000/hr authenticated).
"""
import json, os, re, sys, time, urllib.request, urllib.error, urllib.parse

API = "https://api.github.com"
UA = "bounty-gate/1.0"

# Platforms that actually hold/pay money.
ESCROW = {
    "algora.io": "algora", "algora": "algora",
    "issuehunt.io": "issuehunt", "issuehunt": "issuehunt",
    "polar.sh": "polar", "bountysource.com": "bountysource",
    "opencollective.com": "opencollective", "hackerone.com": "hackerone",
    "bugcrowd.com": "bugcrowd", "gitcoin.co": "gitcoin",
}

SCAM_BOT = re.compile(r"(bountyscout|bounty-bot|bountybot|stale\[bot\])", re.I)
AMOUNT = re.compile(r"\$\s?([0-9][0-9,]{1,9})(?:\.\d+)?")
PR_REF = re.compile(r"#(\d{2,7})")


def token():
    for k in ("GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(k)
        if v:
            return v.strip()
    p = os.path.expanduser("~/.automaton/github.token")
    if os.path.exists(p):
        return open(p).read().strip()
    return None


TOK = token()


def api(path, params=None, tries=3):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
        **({"Authorization": "Bearer " + TOK} if TOK else {}),
    })
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r), r.headers
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < tries - 1:
                time.sleep(8 * (attempt + 1))
                continue
            if e.code == 422:
                return {"__error__": 422}, {}
            return {"__error__": e.code, "__body__": e.read()[:200].decode("utf8", "replace")}, {}
        except Exception as e:
            if attempt < tries - 1:
                time.sleep(3)
                continue
            return {"__error__": str(e)}, {}
    return {"__error__": "exhausted"}, {}


def search(q, per_page=50):
    d, _ = api("/search/issues", {"q": q, "sort": "created", "order": "desc",
                                  "per_page": per_page})
    return d.get("items", [])


def amounts(text):
    out = []
    for m in AMOUNT.finditer(text or ""):
        try:
            v = int(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if 20 <= v <= 200000:
            out.append(v)
    return out


def escrow_hits(text):
    low = (text or "").lower()
    return sorted({v for k, v in ESCROW.items() if k in low})


def prs_referencing(repo, num):
    """Open PRs that mention this issue number."""
    q = "repo:%s type:pr state:open %s" % (repo, num)
    hits = []
    for it in search(q, 20):
        body = (it.get("body") or "") + " " + (it.get("title") or "")
        if re.search(r"#%d\b" % num, body) or re.search(r"\b%d\b" % num, body):
            hits.append({
                "number": it["number"],
                "author": (it.get("user") or {}).get("login"),
                "url": it["html_url"],
                "title": (it.get("title") or "")[:90],
            })
    return hits


def score(c):
    s = 50
    s += min(c["max_usd"], 500) / 10.0          # money, capped
    if c["escrow"]:
        s += 30                                  # a real rail exists
    if c["open_prs"]:
        s -= 45 * len(c["open_prs"])             # occupied
    if c["self_dealt"]:
        s -= 40                                  # farming their own bounty
    if c["bot_noise"]:
        s -= 15
    if c["age_days"] < 2:
        s -= 10                                  # brand new = contested
    elif c["age_days"] > 30:
        s += 10                                  # stale = abandoned = open
    return round(s, 1)


def main():
    queries = sys.argv[1:] or [
        'label:"bounty" state:open type:issue',
        'label:"bounty" state:open type:issue sort:updated',
        '"bounty" state:open type:issue in:title',
    ]
    seen, cands = set(), []
    for q in queries:
        for it in search(q):
            url = it["html_url"]
            if url in seen:
                continue
            seen.add(url)
            repo = "/".join(url.split("/")[3:5])
            num = it["number"]
            author = (it.get("user") or {}).get("login", "")
            text = (it.get("title") or "") + "\n" + (it.get("body") or "")
            am = amounts(text)
            if not am:
                continue
            cands.append({
                "repo": repo, "number": num, "author": author,
                "title": (it.get("title") or "")[:110], "url": url,
                "max_usd": max(am), "all_usd": am,
                "escrow": escrow_hits(text),
                "created": (it.get("created_at") or "")[:10],
                "comments": it.get("comments", 0),
                "bot_noise": bool(SCAM_BOT.search(author)),
                "labels": [l["name"] for l in it.get("labels", [])],
            })
        time.sleep(2)

    # age
    import datetime as dt
    today = dt.date.today()
    for c in cands:
        try:
            c["age_days"] = (today - dt.date(*map(int, c["created"].split("-")))).days
        except Exception:
            c["age_days"] = 999

    # occupancy pass (the expensive part - only on top candidates)
    cands.sort(key=lambda c: c["max_usd"], reverse=True)
    probe = cands[:25]
    print("candidates: %d, probing occupancy on top %d" % (len(cands), len(probe)),
          file=sys.stderr)
    for c in probe:
        c["open_prs"] = prs_referencing(c["repo"], c["number"])
        c["self_dealt"] = any(p["author"] == c["author"] for p in c["open_prs"])
        time.sleep(1)
    for c in cands[len(probe):]:
        c["open_prs"] = []
        c["self_dealt"] = False

    for c in cands:
        c["score"] = score(c)
    cands.sort(key=lambda c: c["score"], reverse=True)

    open_ = [c for c in cands if not c["open_prs"] and not c["self_dealt"]]
    out = {"generated": dt.datetime.now().isoformat(timespec="seconds"),
           "total": len(cands), "unoccupied": len(open_), "candidates": cands}
    with open("report.json", "w", encoding="utf8") as f:
        json.dump(out, f, indent=2)

    lines = ["# bounty-gate report", "",
             "generated: %s  |  candidates: %d  |  **unoccupied: %d**" % (
                 out["generated"], out["total"], out["unoccupied"]), ""]
    for c in cands[:30]:
        flags = []
        if c["open_prs"]:
            flags.append("OCCUPIED(%d)" % len(c["open_prs"]))
        if c["self_dealt"]:
            flags.append("SELF-DEALT")
        if c["escrow"]:
            flags.append("RAIL:" + "+".join(c["escrow"]))
        else:
            flags.append("NO-RAIL")
        if c["bot_noise"]:
            flags.append("BOT-AUTHOR")
        lines.append("* **%.1f** %s#%d $%d aged %dd [%s]" % (
            c["score"], c["repo"], c["number"], c["max_usd"], c["age_days"],
            ", ".join(flags)))
        lines.append("  - %s" % c["title"])
        lines.append("  - %s" % c["url"])
    with open("report.md", "w", encoding="utf8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n".join(lines[:40]))
    print("\nwrote report.json / report.md")


if __name__ == "__main__":
    main()

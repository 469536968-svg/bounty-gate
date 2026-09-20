#!/usr/bin/env python3
"""
algora.py - pull the live bounty board from Algora over its tRPC endpoint.

Discovered by probing: https://algora.io/api/trpc/bounty.list is reachable from
this host and returns real JSON. The public GitHub `label:"bounty"` search space
is occupied junk; *this* is where escrowed, actually-payable work lives.

Usage:
    python3 algora.py            # fetch and print open bounties
    python3 algora.py --json     # dump raw json to algora.json
"""
import json, sys, urllib.request, urllib.parse

BASE = "https://algora.io/api/trpc"
UA = "Mozilla/5.0 (bounty-gate)"
TIMEOUT = 25

# Candidate input shapes, tried in order until one yields items.
CANDIDATES = [
    {},
    {"limit": 50},
    {"limit": 50, "status": "open"},
    {"cursor": None, "limit": 50},
    {"status": "OPEN"},
    {"page": 1, "limit": 50},
]


def trpc(proc, payload):
    url = "%s/%s?input=%s" % (BASE, proc, urllib.parse.quote(json.dumps(payload)))
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def unwrap(d):
    """tRPC wraps as [{"result":{"data":{"json":{...}}}}] - dig out the payload."""
    if isinstance(d, list) and d:
        d = d[0]
    if isinstance(d, dict):
        d = d.get("result", d).get("data", d)
        if isinstance(d, dict) and "json" in d:
            d = d["json"]
    return d


def fetch():
    procs = ["bounty.list", "bounty.getAll", "bounties.list", "bounty.search"]
    last_err = None
    for proc in procs:
        for payload in CANDIDATES:
            try:
                raw = unwrap(trpc(proc, payload))
            except Exception as e:
                last_err = "%s%s: %s" % (proc, payload, e)
                continue
            items = None
            if isinstance(raw, dict):
                for key in ("items", "bounties", "data", "results", "rows"):
                    if isinstance(raw.get(key), list):
                        items = raw[key]
                        break
            elif isinstance(raw, list):
                items = raw
            if items:
                return proc, payload, items
    return None, None, last_err


def normalize(b):
    """Best-effort field mapping across possible shapes."""
    def g(*keys):
        for k in keys:
            v = b.get(k)
            if v not in (None, "", []):
                return v
        return None
    return {
        "id": g("id", "slug"),
        "title": (g("title", "name") or "")[:110],
        "org": g("org", "organization", "owner") or "",
        "repo": g("repo", "repository") or "",
        "amount": g("amount", "reward", "price", "bounty_amount"),
        "currency": g("currency", "token") or "USD",
        "status": g("status", "state") or "",
        "url": g("url", "html_url", "link") or "",
        "tech": g("tech", "tags", "labels") or [],
        "raw_keys": sorted(b.keys()),
    }


def main():
    proc, payload, data = fetch()
    if proc is None:
        print("no working procedure. last error:\n  %s" % data, file=sys.stderr)
        sys.exit(1)
    print("procedure: %s  input: %s  items: %d" % (proc, json.dumps(payload), len(data)))
    print("first item keys:", sorted(data[0].keys()))

    norm = [normalize(b) for b in data]
    with open("algora.json", "w", encoding="utf8") as f:
        json.dump({"proc": proc, "input": payload, "items": data}, f, indent=2)

    print("\n%-9s %-30s %-10s %s" % ("AMOUNT", "ORG", "STATUS", "TITLE"))
    for n in norm:
        print("%-9s %-30s %-10s %s" % (
            n["amount"], str(n["org"])[:30], str(n["status"])[:10], n["title"]))
    print("\nwrote algora.json")


if __name__ == "__main__":
    main()

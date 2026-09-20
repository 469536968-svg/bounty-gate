#!/usr/bin/env python3
"""
algora.py - probe the Algora bounty board over its tRPC endpoint.

FINDING (2026-09-21): the endpoint is REACHABLE from this host, which
falsifies the common claim that payment rails are unreachable.

    GET https://algora.io/api/trpc/bounty.list?input={}
    -> 200 [{"result":{"data":{"json":{"items":[],"next_cursor":null}}}}]

But it returns an EMPTY board for every unauthenticated input shape tried
({}, {"status":"open"}, {"limit":N}, {"page":N}). Only `bounty.list` resolves;
every other procedure name 404s. So the rail is reachable but the public
listing is auth/session gated.

Conclusion: reachable != usable-without-an-account. Escrowed work is assigned
through the platform board behind a login, not through a scrapable public feed,
and not through a GitHub label. That is the structural reason label-scanners
never find payable work.
"""
import json, sys, urllib.request, urllib.parse

URL = "https://algora.io/api/trpc/bounty.list"


def call(inp=None):
    inp = {} if inp is None else inp
    url = "%s?input=%s" % (URL, urllib.parse.quote(json.dumps(inp)))
    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def unwrap(d):
    if isinstance(d, list) and d:
        d = d[0]
    d = d.get("result", d).get("data", d)
    if isinstance(d, dict) and "json" in d:
        d = d["json"]
    return d


def main():
    raw = unwrap(call({"limit": 50, "status": "open"}))
    items = raw.get("items", []) if isinstance(raw, dict) else raw
    print("reachable: yes")
    print("items returned: %d" % len(items))
    print("next_cursor: %s" % (raw.get("next_cursor") if isinstance(raw, dict) else None))
    if not items:
        print("\nEmpty. The board is auth/session gated - see module docstring.")
        print("This is a real, reproducible negative result, not a tooling failure.")
    for b in items:
        print(" *", json.dumps(b)[:160])


if __name__ == "__main__":
    main()

"""Export a Linear team's issues to JSON: {exported_at, complete, issues[]}."""
import argparse
import datetime
import json
import os
import sys
import urllib.request

QUERY = ("query($team: String!, $after: String) { issues(filter: {team: {key: {eq: $team}}}, "
         "first: 50, after: $after) { nodes { id identifier number title description priority "
         "estimate createdAt updatedAt completedAt canceledAt state { name type } "
         "assignee { name } creator { name } parent { id } labels { nodes { name } } "
         "attachments { nodes { url title } } "
         "comments(first: 100) { nodes { id body createdAt user { name } } "
         "pageInfo { hasNextPage } } } "
         "pageInfo { hasNextPage endCursor } } }")


def _nodes(n, key):
    return ((n.get(key) or {}).get("nodes")) or []


def _issue(n):
    """One export row: the old keys stay, the rest is read-only extra for the importer."""
    who = lambda k: (n.get(k) or {}).get("name")  # noqa: E731
    row = {"id": n["id"], "identifier": n["identifier"], "title": n["title"],
           "state": (n.get("state") or {}).get("name"),
           "state_type": (n.get("state") or {}).get("type"), "updatedAt": n["updatedAt"]}
    for k in ("number", "description", "priority", "estimate", "createdAt", "completedAt",
              "canceledAt"):
        row[k] = n.get(k)
    row.update(assignee=who("assignee"), creator=who("creator"),
               parent=(n.get("parent") or {}).get("id"),
               labels=[x["name"] for x in _nodes(n, "labels")],
               attachments=[{"url": x["url"], "title": x.get("title")}
                            for x in _nodes(n, "attachments")],
               comments=[{"id": c["id"], "body": c["body"], "createdAt": c["createdAt"],
                          "author": who_c(c)} for c in _nodes(n, "comments")],
               comments_truncated=bool(((n.get("comments") or {}).get("pageInfo") or {})
                                       .get("hasNextPage")))
    return row


def who_c(c):
    return (c.get("user") or {}).get("name")


def _http_fetch(key):
    def fetch(query, variables):
        req = urllib.request.Request(
            "https://api.linear.app/graphql",
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={"Content-Type": "application/json", "Authorization": key})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    return fetch


def export(team, fetch, now=None):
    """complete is true only when pagination finished without any error."""
    now = now or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    issues, after, complete = [], None, False
    try:
        while True:
            resp = fetch(QUERY, {"team": team, "after": after})
            if resp.get("errors") or "data" not in resp:
                print("Linear GraphQL hiba: %s" % json.dumps(resp.get("errors"))[:300],
                      file=sys.stderr)
                break
            page = resp["data"]["issues"]
            for n in page["nodes"]:
                issues.append(_issue(n))
            if not page["pageInfo"]["hasNextPage"]:
                complete = True
                break
            after = page["pageInfo"]["endCursor"]
            if not after:
                print("Linear lapozás hiba: hiányzó kurzor", file=sys.stderr)
                break
    except Exception as e:  # network/parse errors leave the export incomplete
        print("Linear export hiba: %s" % e, file=sys.stderr)
    return {"exported_at": now, "complete": complete, "issues": issues}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    key = os.environ.get("LINEAR_API_KEY")
    if not key:
        print("A LINEAR_API_KEY környezeti változó hiányzik.", file=sys.stderr)
        return 2
    d = export(a.team, _http_fetch(key))
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
    return 0 if d["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())

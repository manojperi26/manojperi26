"""Generate assets/stats.svg (contribution stats + top languages) from the GitHub GraphQL API.

Runs inside GitHub Actions with the built-in GITHUB_TOKEN. No third-party services involved.
Usage: python scripts/generate_stats.py dist/stats.svg
"""
import html
import json
import os
import sys
import urllib.request

TOKEN = os.environ["GITHUB_TOKEN"]
LOGIN = os.environ.get("GH_LOGIN") or os.environ["GITHUB_REPOSITORY_OWNER"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "stats.svg"

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliation: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        languages(first: 6, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""


def gql(login):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats",
        },
    )
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(payload["errors"])
    return payload["data"]["user"]


user = gql(LOGIN)
cc = user["contributionsCollection"]
repos = user["repositories"]

metrics = [
    (f'{cc["contributionCalendar"]["totalContributions"]:,}', "Contributions (12 mo)"),
    (f'{cc["totalCommitContributions"]:,}', "Commits (12 mo)"),
    (f'{cc["totalPullRequestContributions"]:,}', "Pull requests (12 mo)"),
    (f'{repos["totalCount"]:,}', "Public repositories"),
]

langs = {}
for repo in repos["nodes"]:
    for edge in repo["languages"]["edges"]:
        name = edge["node"]["name"]
        entry = langs.setdefault(name, [0, edge["node"]["color"] or "#8B5CF6"])
        entry[0] += edge["size"]
total = sum(v[0] for v in langs.values()) or 1
top = sorted(langs.items(), key=lambda kv: kv[1][0], reverse=True)[:5]

W, H = 840, 240
LW = 400            # left panel width
RX = 430            # right panel x
RW = W - RX

svg = []
add = svg.append
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="GitHub stats for {html.escape(LOGIN)}">')
add("""<defs>
  <linearGradient id="border" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#7C3AED"/><stop offset="0.5" stop-color="#22D3EE"/><stop offset="1" stop-color="#6366F1"/>
  </linearGradient>
  <linearGradient id="num" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#C4B5FD"/><stop offset="1" stop-color="#67E8F9"/>
  </linearGradient>
  <linearGradient id="panel" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#151233"/><stop offset="1" stop-color="#0D1117"/>
  </linearGradient>
  <style>
    .n{font:800 34px 'Segoe UI',Arial,sans-serif;fill:url(#num)}
    .l{font:500 13px 'Segoe UI',Arial,sans-serif;fill:#A5B4FC}
    .h{font:700 15px 'Segoe UI',Arial,sans-serif;fill:#E9E5FF;letter-spacing:1px}
    .t{font:600 14px 'Segoe UI',Arial,sans-serif;fill:#E5E7EB}
    .p{font:500 13px 'Segoe UI',Arial,sans-serif;fill:#9CA3AF}
    .fade{animation:in .8s ease backwards}
    @keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
    @keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
    .bar{transform-origin:left center;animation:grow 1.2s ease backwards}
  </style>
</defs>""")
add(f'<rect x="1" y="1" width="{LW}" height="{H-2}" rx="16" fill="url(#panel)" stroke="url(#border)" stroke-width="1.5"/>')
add(f'<rect x="{RX}" y="1" width="{RW-1}" height="{H-2}" rx="16" fill="url(#panel)" stroke="url(#border)" stroke-width="1.5"/>')

add('<text class="h" x="28" y="34">ACTIVITY  ·  LAST 12 MONTHS</text>')
for i, (val, label) in enumerate(metrics):
    cx = 28 + (i % 2) * 190
    cy = 88 + (i // 2) * 78
    add(f'<g class="fade" style="animation-delay:{0.1*i:.1f}s"><text class="n" x="{cx}" y="{cy}">{html.escape(val)}</text><text class="l" x="{cx}" y="{cy+22}">{html.escape(label)}</text></g>')

add(f'<text class="h" x="{RX+28}" y="34">TOP LANGUAGES</text>')
bx, by, bw, bh = RX + 28, 52, RW - 56, 12
add(f'<clipPath id="bc"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6"/></clipPath>')
add('<g clip-path="url(#bc)"><g class="bar">')
x = bx
for name, (size, color) in top:
    w = bw * size / total
    add(f'<rect x="{x:.1f}" y="{by}" width="{w:.1f}" height="{bh}" fill="{html.escape(color)}"/>')
    x += w
add('</g></g>')
for i, (name, (size, color)) in enumerate(top):
    ly = 96 + i * 28
    add(f'<g class="fade" style="animation-delay:{0.15*i:.2f}s"><circle cx="{bx+6}" cy="{ly-5}" r="6" fill="{html.escape(color)}"/><text class="t" x="{bx+22}" y="{ly}">{html.escape(name)}</text><text class="p" x="{bx+bw}" y="{ly}" text-anchor="end">{100*size/total:.1f}%</text></g>')
add("</svg>")

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(svg))
print("wrote", OUT)

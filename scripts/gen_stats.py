#!/usr/bin/env python3
"""Generate assets/stats.svg from public GitHub data. Needs GITHUB_TOKEN; USER_LOGIN is optional."""
import datetime as dt
import json
import os
import urllib.request
from html import escape

USER = os.environ.get("USER_LOGIN", "VLOD-ZDOV")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "stats.svg")

COLORS = {
    "Rust": "#dea584", "Java": "#b07219", "Python": "#3572A5", "Kotlin": "#A97BFF",
    "Go": "#00ADD8", "C": "#555555", "C++": "#f34b7d", "C#": "#178600",
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "HTML": "#e34c26",
    "Shell": "#89e051", "GLSL": "#5686a5", "QML": "#44a51c", "PowerShell": "#012456",
}


def gql(query, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]


def main():
    d = gql(
        """query($u:String!){user(login:$u){createdAt followers{totalCount}
        repositories(first:100, ownerAffiliations:OWNER, privacy:PUBLIC, isFork:false){
          totalCount nodes{pushedAt stargazerCount languages(first:20){edges{size node{name}}}}}}}""",
        u=USER,
    )["user"]

    # old repos (no push for 18 months) are left out of languages and repo count
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=548)
    active = [r for r in d["repositories"]["nodes"]
              if dt.datetime.fromisoformat(r["pushedAt"].replace("Z", "+00:00")) >= cutoff]
    langs, stars = {}, 0
    for repo in active:
        stars += repo["stargazerCount"]
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]

    # contributionsCollection spans at most one year, so walk year by year
    start = dt.datetime.fromisoformat(d["createdAt"].replace("Z", "+00:00")).year
    now = dt.datetime.now(dt.timezone.utc)
    total_commits = total_contrib = this_year = 0
    for year in range(start, now.year + 1):
        c = gql(
            """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){
            contributionsCollection(from:$f,to:$t){totalCommitContributions
            restrictedContributionsCount contributionCalendar{totalContributions}}}}""",
            u=USER, f=f"{year}-01-01T00:00:00Z", t=f"{year}-12-31T23:59:59Z",
        )["user"]["contributionsCollection"]
        total_commits += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        total_contrib += c["contributionCalendar"]["totalContributions"]
        if year == now.year:
            this_year = c["contributionCalendar"]["totalContributions"]

    stats = [
        ("Commits", total_commits, "#7ee787"),
        (f"Contributions {now.year}", this_year, "#58a6ff"),
        ("Total contributions", total_contrib, "#d2a8ff"),
        ("Active repos", len(active), "#ffa657"),
        ("Stars", stars, "#f2cc60"),
    ]
    write_svg(stats, langs)


def write_svg(stats, langs):
    W, H = 900, 260
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda x: -x[1])[:8]
    other = total - sum(v for _, v in top)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           '<style>.m{font-family:\'JetBrains Mono\',Consolas,\'DejaVu Sans Mono\',monospace}'
           '.f{opacity:0;animation:in .6s ease-out forwards}'
           '@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}'
           '.g{transform-origin:left;transform:scaleX(0);animation:grow 1.2s ease-out .3s forwards}'
           '@keyframes grow{to{transform:scaleX(1)}}</style>',
           f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="16" fill="#0d1117" stroke="#30363d"/>',
           '<text x="32" y="44" class="m" font-size="18" font-weight="700" fill="#c9d1d9">'
           '<tspan fill="#7ee787">❯</tspan> git log --stat</text>']

    # stat tiles
    tw = (W - 64 - 4 * 12) / 5
    for i, (label, val, col) in enumerate(stats):
        x = 32 + i * (tw + 12)
        out.append(f'<g class="f" style="animation-delay:{i*0.12:.2f}s">'
                   f'<rect x="{x:.1f}" y="64" width="{tw:.1f}" height="78" rx="10" fill="#161b22" stroke="#30363d"/>'
                   f'<text x="{x+14:.1f}" y="106" class="m" font-size="26" font-weight="800" fill="{col}">{val:,}</text>'
                   f'<text x="{x+14:.1f}" y="128" class="m" font-size="11" fill="#8b949e">{escape(label)}</text></g>')

    # language bar
    out.append('<text x="32" y="174" class="m" font-size="13" fill="#8b949e">Languages (active repos, by code size)</text>')
    out.append(f'<clipPath id="bar"><rect x="32" y="186" width="{W-64}" height="12" rx="6"/></clipPath><g clip-path="url(#bar)" class="g">')
    x = 32.0
    for name, v in top + ([("Other", other)] if other else []):
        w = (W - 64) * v / total
        out.append(f'<rect x="{x:.2f}" y="186" width="{w+0.5:.2f}" height="12" fill="{COLORS.get(name, "#6e7681")}"/>')
        x += w
    out.append('</g>')

    # legend
    for i, (name, v) in enumerate(top):
        lx, ly = 32 + (i % 4) * 212, 222 + (i // 4) * 22
        out.append(f'<g class="f" style="animation-delay:{0.6+i*0.08:.2f}s">'
                   f'<circle cx="{lx+5}" cy="{ly-4}" r="5" fill="{COLORS.get(name, "#6e7681")}"/>'
                   f'<text x="{lx+16}" y="{ly}" class="m" font-size="13" fill="#c9d1d9">{escape(name)} '
                   f'<tspan fill="#8b949e">{100*v/total:.1f}%</tspan></text></g>')
    out.append('</svg>')

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()

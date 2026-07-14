#!/usr/bin/env python3
# Chart: "The flood hits the guard position hardest — pure exits stayed low until a late climb"
# (blog image: circuit-building-dos-wave-june-2026-chart-guards-vs-exits.png)
#
# Fully reproducible from public data:
#   1. streams CollecTor's signed consensus archives (the daily 12:00 consensus)
#      to classify every relay's role per day (guard-only / guard+exit / exit-only / middle);
#   2. streams CollecTor's signed server-descriptor archives to find, per day,
#      which relays published an `overload-general` line;
#   3. joins the two by fingerprint+day and plots the share of each role overloaded.
#
# Requires: python3 + matplotlib. Runtime: ~15-40 min (streams ~1-2 GB of archives).
# Usage: python3 chart-guards-vs-exits.py [output.png]
import sys, os, urllib.request, tarfile, base64, json, datetime as dt
from collections import defaultdict
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md

MONTHS = ["2026-06", "2026-07"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "chart-guards-vs-exits.png"

# Stream a CollecTor archive. Set CT_CACHE=/path to read pre-downloaded *.tar.xz from disk
# (optional; without it the archive is streamed straight from collector.torproject.org).
def open_archive(url):
    cache = os.environ.get("CT_CACHE")
    if cache:
        p = os.path.join(cache, url.rsplit("/", 1)[1])
        if os.path.exists(p): return tarfile.open(p, mode="r:xz")
    return tarfile.open(fileobj=urllib.request.urlopen(url, timeout=900), mode="r|xz")

# ---- 1. roles from the daily noon consensus ----
def classify(flags):
    g = "Guard" in flags; e = "Exit" in flags
    return "both" if (g and e) else "guard" if g else "exit" if e else "middle"

role_of = defaultdict(dict); role_total = defaultdict(lambda: defaultdict(int))
for month in MONTHS:
    url = f"https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-{month}.tar.xz"
    print(f"streaming {url} ...", flush=True)
    tf = open_archive(url)
    for mem in tf:
        if not mem.name.endswith("-12-00-00-consensus"): continue
        day = mem.name.split("/")[-1][:10]
        fp = None
        for line in tf.extractfile(mem).read().decode("ascii", "replace").split("\n"):
            if line.startswith("r "):
                f = line.split(); fp = None
                if len(f) >= 3:
                    try: fp = base64.b64decode(f[2] + "=").hex().upper()
                    except Exception: fp = None
            elif line.startswith("s ") and fp is not None:
                role = classify(set(line[2:].split()))
                role_of[day][fp] = role; role_total[day][role] += 1; fp = None
        print(f"  {day}: roles classified ({sum(role_total[day].values())} relays)", flush=True)

# ---- 2. overload-general per day from server descriptors ----
over = defaultdict(set)
def finish(fp, day, ov):
    if fp and day and ov: over[day].add(fp)
for month in MONTHS:
    url = f"https://collector.torproject.org/archive/relay-descriptors/server-descriptors/server-descriptors-{month}.tar.xz"
    print(f"streaming {url} ...", flush=True)
    tf = open_archive(url)
    n = 0
    for mem in tf:
        if not mem.isfile(): continue
        try: text = tf.extractfile(mem).read().decode("ascii", "replace")
        except Exception: continue
        fp = day = None; ov = False
        for line in text.split("\n"):
            if line.startswith("router "):
                finish(fp, day, ov); fp = day = None; ov = False
            elif line.startswith("fingerprint "): fp = line[11:].replace(" ", "").strip().upper()
            elif line.startswith("published "): day = line.split()[1]
            elif line.startswith("overload-general"): ov = True
        finish(fp, day, ov)
        n += 1
        if n % 50000 == 0: print(f"  {month}: {n} descriptors", flush=True)

# ---- 3. join + figure ----
days = [d for d in sorted(role_of) if "2026-06-01" <= d <= "2026-07-12"]  # end pinned to the last complete archive day
ROLES = ["guard", "both", "middle", "exit"]
series = {r: [] for r in ROLES}
for d in days:
    ro = role_of[d]; rt = role_total[d]; oc = defaultdict(int)
    for fp in over.get(d, ()):
        r = ro.get(fp)
        if r: oc[r] += 1
    for r in ROLES:
        series[r].append(100 * oc[r] / max(rt.get(r, 0), 1))
X = [dt.datetime.strptime(d, "%Y-%m-%d") for d in days]
json.dump({"days": days, "series": series}, open(OUT + ".data.json", "w"))
for i, d in enumerate(days):
    if d in ("2026-06-05", "2026-06-24", "2026-06-28", "2026-07-05", "2026-07-11"):
        print(f"  {d}  guard={series['guard'][i]:.1f}% exit={series['exit'][i]:.1f}% both={series['both'][i]:.1f}% middle={series['middle'][i]:.1f}%")

INK="#e6e6e6"; MUT="#9a9a9a"; BG="#1e1e1e"; GRID="#333"
GRN="#00ff7f"; RED="#ff6b6b"; AMB="#ffb454"; PUR="#b48cff"
fig, ax = plt.subplots(figsize=(10, 4.9), dpi=200); fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
onset = dt.datetime(2026, 6, 25); ax.axvspan(onset, X[-1], color=RED, alpha=0.06, zorder=0)
ax.axvline(onset, color=MUT, ls="--", lw=1, alpha=0.7)
STYLE = [("guard", RED, "guards (guard-only)", 2.8), ("both", AMB, "guard+exit", 1.8),
         ("middle", PUR, "middle", 1.6), ("exit", GRN, "exits (exit-only)", 2.4)]
for r, c, lab, lw in STYLE:
    ax.plot(X, series[r], color=c, lw=lw, label=lab, zorder=4 if r == "guard" else 3)
ax.text(onset, 0.5, "  flood onset Jun 25", color=MUT, fontsize=8.5, ha="left", va="bottom", rotation=90)
ax.annotate("pure exits\nclimbing late", xy=(X[-1], series["exit"][-1]), xytext=(-10, 30), textcoords="offset points",
            color=GRN, fontsize=8.3, ha="right", va="bottom", arrowprops=dict(arrowstyle="->", color=GRN, lw=1, alpha=0.85))
ax.set_ylim(0, max(series["guard"]) * 1.12); ax.set_ylabel("relays overloaded  (% of that role)", fontsize=10.5, color=MUT)
ax.grid(True, color=GRID, lw=0.7); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_color("#555")
ax.tick_params(colors=MUT); ax.xaxis.set_major_formatter(md.DateFormatter("%b %d")); ax.xaxis.set_major_locator(md.DayLocator(interval=4)); fig.autofmt_xdate()
lg = ax.legend(loc="upper left", fontsize=9.5, frameon=True, facecolor=BG, edgecolor="#444")
for t in lg.get_texts(): t.set_color(INK)
i11 = len(days) - 1  # latest full day in the archives
ax.set_title("The flood hits the guard position hardest — pure exits stayed low until a late climb",
             fontsize=12.3, color=INK, loc="left", pad=42, fontweight="bold")
ax.text(0, 1.015, "share of each role's relays overloaded, from Tor's signed CollecTor archives (consensus flags × overload-general) · daily · UTC\n"
        f"by {days[i11][5:]}: guard-only {series['guard'][i11]:.1f}%, guard+exit {series['both'][i11]:.1f}%, pure exit rising to {series['exit'][i11]:.1f}%",
        transform=ax.transAxes, fontsize=8.0, color=MUT, va="bottom", linespacing=1.3)
fig.text(0.995, 0.012, "Produced by 1AEO", color="#a5a5a5", fontsize=8, ha="right", va="bottom")
fig.tight_layout(pad=1.1)
fig.savefig(OUT, facecolor=BG, bbox_inches="tight")
print("wrote", OUT)

#!/usr/bin/env python3
# Chart: "Two overload waves across the Tor network, June-July 2026"
# (blog image: circuit-building-dos-wave-june-2026-chart-network-overload-only.png)
#
# Fully reproducible from public data: streams Tor's signed server-descriptor
# archives from CollecTor and counts, per UTC day, the share of publishing
# relays whose descriptor carries an `overload-general` line.
# Every relay publishes a descriptor at least every 18h, so each UTC day
# covers effectively the whole live network.
#
# The signed *monthly* server-descriptor archive lags real time by a day or two,
# so it only fully covers days through ~Jul 12. To fill the final chart day
# (Jul 13) we ALSO parse CollecTor's *recent/* per-file server-descriptor
# documents (each covers a slice of the last few days) and union them into the
# final day only -- every earlier day comes wholly from the signed monthly
# archive, so Jul 11 stays 11.4% and Jul 12 stays 12.2%.
#
# Requires: python3 + matplotlib. Runtime: ~10-30 min (streams ~1-2 GB of archives).
# Usage: python3 chart-network-overload.py [output.png]
import sys, os, re, urllib.request, tarfile, json, datetime as dt
from collections import defaultdict
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md

MONTHS = ["2026-06", "2026-07"]
LAST_DAY = "2026-07-13"      # final chart day, filled from CollecTor recent/ per-file docs
OUT = sys.argv[1] if len(sys.argv) > 1 else "chart-network-overload-only.png"

# Stream a CollecTor monthly archive. Set CT_CACHE=/path to read a pre-downloaded
# *.tar.xz from disk (optional speedup; without it the archive is streamed straight
# from collector.torproject.org).
def open_archive(url):
    cache = os.environ.get("CT_CACHE")
    if cache:
        p = os.path.join(cache, url.rsplit("/", 1)[1])
        if os.path.exists(p): return tarfile.open(p, mode="r:xz")
    return tarfile.open(fileobj=urllib.request.urlopen(url, timeout=900), mode="r|xz")

# Yield the decoded text of each CollecTor recent/ per-file server-descriptors
# document. Public source: collector.torproject.org/recent/. Set CT_FRESH=/path
# to read a local directory of those files instead (fast offline verification).
def fresh_texts():
    local = os.environ.get("CT_FRESH")
    if local:
        for name in sorted(os.listdir(local)):
            p = os.path.join(local, name)
            if os.path.isfile(p):
                with open(p, encoding="ascii", errors="replace") as fh:
                    yield fh.read()
        return
    base = "https://collector.torproject.org/recent/relay-descriptors/server-descriptors/"
    idx = urllib.request.urlopen(base, timeout=300).read().decode("utf-8", "replace")
    for name in sorted(set(re.findall(r'href="([0-9-]+-server-descriptors)"', idx))):
        try:
            yield urllib.request.urlopen(base + name, timeout=300).read().decode("ascii", "replace")
        except Exception:
            continue

pub = defaultdict(set)   # day -> fps that published
over = defaultdict(set)  # day -> fps whose descriptor carries overload-general

def finish(fp, day, ov):
    if fp and day:
        pub[day].add(fp)
        if ov: over[day].add(fp)

def parse_descriptors(text, pubmap, overmap):
    fp = day = None; ov = False
    for line in text.split("\n"):
        if line.startswith("router "):
            if fp and day:
                pubmap[day].add(fp)
                if ov: overmap[day].add(fp)
            fp = day = None; ov = False
        elif line.startswith("fingerprint "):
            fp = line[11:].replace(" ", "").strip().upper()
        elif line.startswith("published "):
            day = line.split()[1]
        elif line.startswith("overload-general"):
            ov = True
    if fp and day:
        pubmap[day].add(fp)
        if ov: overmap[day].add(fp)

# ---- 1. signed monthly archives (whole series) ----
for month in MONTHS:
    url = f"https://collector.torproject.org/archive/relay-descriptors/server-descriptors/server-descriptors-{month}.tar.xz"
    print(f"streaming {url} ...", flush=True)
    tf = open_archive(url)
    n = 0
    for mem in tf:
        if not mem.isfile(): continue
        try:
            text = tf.extractfile(mem).read().decode("ascii", "replace")
        except Exception:
            continue
        parse_descriptors(text, pub, over)
        n += 1
        if n % 50000 == 0: print(f"  {month}: {n} descriptors", flush=True)
    print(f"  {month}: done, {n} descriptors", flush=True)

# ---- 2. supplement ONLY the final day from CollecTor recent/ per-file docs ----
print("parsing CollecTor recent/ per-file server-descriptors for the final day ...", flush=True)
pub_f = defaultdict(set); over_f = defaultdict(set)
nf = 0
for text in fresh_texts():
    parse_descriptors(text, pub_f, over_f)
    nf += 1
print(f"  recent/: {nf} files; {LAST_DAY} adds pub {len(pub[LAST_DAY])}->{len(pub[LAST_DAY] | pub_f[LAST_DAY])}, "
      f"over {len(over[LAST_DAY])}->{len(over[LAST_DAY] | over_f[LAST_DAY])}", flush=True)
pub[LAST_DAY] |= pub_f[LAST_DAY]
over[LAST_DAY] |= over_f[LAST_DAY]

days = sorted(d for d in pub if "2026-06-15" <= d <= LAST_DAY and len(pub[d]) > 5000)  # wave 1 peaked Jun 28 (8.2%), wave 2 peaked Jul 12 (12.2%), eased to ~11.3% on Jul 13
X = [dt.datetime.strptime(d, "%Y-%m-%d") for d in days]
net = [100 * len(over[d]) / len(pub[d]) for d in days]
for d, v in zip(days, net):
    print(f"{d}  publishers={len(pub[d]):5d}  overloaded={len(over[d]):5d}  {v:.1f}%")
json.dump({d: {"pub": len(pub[d]), "over": len(over[d])} for d in days}, open(OUT + ".data.json", "w"))

# ---- figure ----
INK="#e6e6e6"; MUT="#9a9a9a"; BG="#1e1e1e"; GRID="#333"; RED="#ff6b6b"; AMB="#ffb454"
fig, ax = plt.subplots(figsize=(10, 4.7), dpi=200); fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
ax.fill_between(X, net, color=RED, alpha=0.16, zorder=2); ax.plot(X, net, color=RED, lw=2.6, zorder=3)
onset = dt.datetime(2026, 6, 25); ax.axvline(onset, color=MUT, ls="--", lw=1, alpha=0.7)
ax.text(onset, 12.2, "onset ~Jun 25", color=MUT, fontsize=8.5, ha="center", va="bottom")

# data-driven wave annotations
i1 = max((i for i, d in enumerate(days) if "2026-06-26" <= d <= "2026-07-02"), key=lambda i: net[i])
i2 = max((i for i, d in enumerate(days) if d >= "2026-07-08"), key=lambda i: net[i])
ax.annotate(f"wave 1\n{net[i1]:.1f}% ({len(over[days[i1]]):,} relays)", (X[i1], net[i1]), xytext=(0, 20),
            textcoords="offset points", ha="center", fontsize=9.5, color=AMB, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=MUT, lw=0.8))
ax.annotate(f"wave 2 peak\n{net[i2]:.1f}% ({len(over[days[i2]]):,}) · {X[i2]:%b %d}", (X[i2], net[i2]), xytext=(-150, 8),
            textcoords="offset points", ha="left", va="center", fontsize=9.5, color=RED, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=MUT, lw=0.8))
# mark the final day easing off the peak
ax.scatter([X[-1]], [net[-1]], s=22, color=RED, zorder=6, edgecolor=BG, lw=1)
ax.annotate(f"eased to {net[-1]:.1f}%\n{X[-1]:%b %d}", (X[-1], net[-1]), xytext=(10, 26),
            textcoords="offset points", ha="left", va="center", fontsize=9.0, color=INK, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=MUT, lw=0.8))
ax.text(X[3], 2.0, "baseline 1.5-3.3%", color=MUT, fontsize=8.5)
ax.set_ylim(0, 13); ax.set_ylabel("Tor relays reporting overload  (% of network)", fontsize=10.5, color=MUT)
ax.grid(True, color=GRID, lw=0.7); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_color("#555")
ax.tick_params(colors=MUT); ax.xaxis.set_major_formatter(md.DateFormatter("%b %d")); ax.xaxis.set_major_locator(md.DayLocator(interval=3)); fig.autofmt_xdate()
ax.set_title("Two overload waves across the Tor network, June–July 2026", fontsize=13, color=INK, loc="left", pad=26, fontweight="bold")
ax.text(0, 1.045, "share of all Tor relays signing an overload-general line, from Tor's signed CollecTor archives · daily · UTC",
        transform=ax.transAxes, fontsize=8.6, color=MUT, va="bottom")
fig.text(0.995, 0.012, "Produced by 1AEO", color="#a5a5a5", fontsize=8, ha="right", va="bottom")
fig.tight_layout(pad=1.1); fig.savefig(OUT, facecolor=BG, bbox_inches="tight")
print("wrote", OUT)

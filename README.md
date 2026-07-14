# Reproduce the public-data charts from the June–July 2026 circuit-building DoS posts

Every chart below is built **entirely from Tor's public data** — the signed
[CollecTor](https://collector.torproject.org/) archives and/or the
[Onionoo](https://onionoo.torproject.org/) API. No relay access, no private
telemetry. Each script is self-contained: it fetches the data, recomputes the
numbers from scratch, and renders the exact chart published in the post.

Scripts are grouped by post: **`blog1/`** (the network-view post) and
**`blog2/`** (the fleet post). Every chart in the network-view post is public;
from the fleet post, only the charts built from public data are here (the
first-party MetricsPort charts are not reproducible without relay access).

## Charts in the network-view post ("The Tor Network Is Under a Circuit-Building DoS Wave")

| script | chart | data source | runtime |
|---|---|---|---|
| `blog1/chart-network-overload.py` | Two overload waves across the Tor network | CollecTor server descriptors (`overload-general`) | 10–30 min |
| `blog1/chart-guards-vs-exits.py` | The flood hits the guard position hardest | CollecTor consensuses (flags) × server descriptors | 15–40 min |
| `blog1/chart-network-flap.py` | The flood shook the Running flag network-wide | CollecTor hourly consensuses (`Running` diffs) | 5–15 min |
| `blog1/chart-netflap-rate.py` | Running-flag flicker rate (% of the network) | CollecTor 6h consensuses (`Running` diffs) | 3–10 min |

## Public-data charts in the fleet post ("How Our Guard Fleet Held")

| script | chart | data source | runtime |
|---|---|---|---|
| `blog2/chart-network-overload-2line.py` | Network overload vs the 1AEO fleet | CollecTor server descriptors + Onionoo (1AEO fingerprint set) | 10–30 min |
| `blog2/chart-guard-count-time.py` | Overloaded guards over time, top-10 operators | CollecTor consensuses × server descriptors + Onionoo (operator sets) | 15–40 min |
| `blog2/chart-flagflap.py` | Our guards' Running-flag flapping vs the network's guards (matched %) | CollecTor 6h consensuses + Onionoo (1AEO fingerprint set) | 5–15 min |
| `blog2/chart-guard-bubble.py` | Scale vs. overload — top-10 guard operators | Onionoo `/details` (snapshot) | seconds |
| `blog2/chart-entryload.py` | Per-guard entry load vs overload | Onionoo `/details` + `/weights` (snapshot) | seconds |

## Requirements

- Python 3.9+ and `matplotlib` (`pip install matplotlib`). No other third-party packages.
- Network access to `collector.torproject.org` and `onionoo.torproject.org`.
- The CollecTor scripts stream the June + July 2026 monthly archives (several
  hundred MB to ~2 GB per run). Only the chart and a small `.data.json` are written.

## Usage

```
python3 blog1/<script>.py [output.png]   # or blog2/<script>.py
```

**Optional speed-ups (CollecTor scripts):** pre-download the monthly `.tar.xz`
archives once and point the scripts at them, avoiding re-downloads:

```
export CT_CACHE=/path/to/archives      # dir holding consensuses-2026-06.tar.xz, server-descriptors-2026-06.tar.xz, ...
export CT_FRESH=/path/to/recent-files  # (overload scripts only) dir of CollecTor recent/ per-file server-descriptors for the final day
```

Without them, everything is fetched live from CollecTor. (Note: the scripts use
Python's built-in `lzma`/`tarfile`, so no `xz` binary is required.)

## Method notes (the details that matter)

- **Overload:** a relay signs `overload-general` into its server descriptor when
  it crosses Tor's internal overload thresholds. Relays publish at least every
  18 h, so each UTC day effectively covers the whole live network; we count
  distinct fingerprints per day.
- **Final day (Jul 13):** CollecTor's signed *monthly* archive lags real time by
  a day or two (it fully covers days through ~Jul 12). The overload scripts fill
  the final chart day (Jul 13) by unioning CollecTor's *recent/* per-file
  server-descriptor documents into **that day only** — every earlier day comes
  wholly from the signed monthly archive, so Jul 11 stays 11.4% and Jul 12 stays
  12.2%. Overload peaked Jul 12 (12.2%, 1,254 relays) and eased to ~11.3% on Jul 13.
- **Roles:** each relay's role (guard-only / guard+exit / exit-only / middle) is
  read from the flags in the daily 12:00 UTC consensus and joined to that day's
  overload set by fingerprint.
- **Running-flag flap:** the `Running` set is diffed between consecutive hourly
  consensuses. ⚠️ CollecTor tar archives are **not** in time order — consensuses
  are collected first, then processed strictly in `valid-after` order (processing
  in tar order silently corrupts the diffs). A relay's first appearance is never
  counted as a flap, so relay onboarding cannot inflate the counts.
- **Operator grouping (AROI):** operators are grouped by the operator domain
  proven in ContactInfo (queried via Onionoo `contact=<domain>`), and 1AEO's own
  relays are identified publicly via `contact=1aeo.com` — never from any private
  list.
- **`blog2/chart-flagflap.py`:** a matched guards-vs-guards comparison — the % of OUR
  guard fleet that dropped the `Running` flag per 6h (green) vs the % of the whole
  network's guard relays that did (red), on one shared axis. Guard-only on both
  sides so the populations are comparable; 1AEO relays are identified via Onionoo
  `contact=1aeo.com`, migration relays excluded. Our guards essentially never
  flapped pre-flood, then peaked ~4.6% under load (vs the network's guards ~2.1%)
  and self-healed to zero — showing the relays stayed up, losing only the flag.

## Onionoo snapshots (`blog2/chart-guard-bubble.py`, `blog2/chart-entryload.py`)

Onionoo serves only the **current** network state — it has no historical archive —
so these two snapshot charts cannot be reproduced from a past date the way the
CollecTor time-series can. Each script embeds the plotted values from its
documented Onionoo query (snapshot **2026-07-13**, all Guard-flag relays per
operator) and renders deterministically from them. `chart-guard-bubble.py
--verify` re-runs the live Onionoo query and prints the current numbers so you
can compare against the embedded snapshot.

## A note on drift

CollecTor archives are immutable, so the CollecTor time-series reproduce
bit-for-bit. The pieces that touch Onionoo (the 1AEO fingerprint set, operator
counts) move slightly day to day as the live network changes; re-running a day
later shifts those by a relay or two without changing any headline figure.

Produced by [1AEO](https://1aeo.com).

"""TEST-ONLY: per batch prefix (A / B), early stops (travel < 15 m within 8 s of touchdown) per flyer
type and target from brace_an --table output, causes, single-model totals. usage: summarize.py A|B"""
import re, sys, collections, subprocess, os
from pathlib import Path
H = Path(__file__).resolve().parent
pre = sys.argv[1]
labs = sorted(d for d in os.listdir(H / "runs") if d.startswith(pre) and (H / "runs" / d / "verdict.json").exists())
txt = subprocess.run([sys.executable, "-I", str(H / "brace_an.py"), "--table"] + labs, capture_output=True, text=True).stdout
(H / f"batch_{pre.lower()}_table.txt").write_text(txt, "utf-8")
lanes, early, cause = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
for l in txt.splitlines():
    m = re.match(r"(\w\d)_(\S+)\s+lane (\d) (\S+)\s+men (\d+)", l)
    if not m:
        continue
    k = (m.group(2), "single" if m.group(5) == "1" else "multi" + m.group(5))
    t = m.group(4)
    lanes[(k, t)] += 1
    if "EARLY" in l:
        early[(k, t)] += 1
        cause[k][re.search(r"cause (\S+)", l).group(1).split("(")[0]] += 1
print(f"batch {pre}: {len(labs)} runs")
print("type       bodies   spear halb militia | causes")
for k in sorted(set(k for k, _ in lanes)):
    print(f"{k[0]:10s} {k[1]:8s}", " ".join(f"{early[(k, t)]}/{lanes[(k, t)]}" for t in ("spear", "halb", "militia")),
          " |", dict(cause[k]))
for name, f in (("single, spear+halb", lambda k, t: k[1] == "single" and t != "militia"),
                ("single, militia", lambda k, t: k[1] == "single" and t == "militia"),
                ("multi (lead model), all", lambda k, t: k[1] != "single")):
    print(f"{name}: {sum(v for (k, t), v in early.items() if f(k, t))} / {sum(v for (k, t), v in lanes.items() if f(k, t))}")

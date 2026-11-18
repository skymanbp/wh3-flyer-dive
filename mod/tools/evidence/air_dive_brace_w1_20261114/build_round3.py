"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 3): build the probe mini-mod from the lane as it is now (slide window
caves + mass cut), or with the mass cut switched off in THIS process only (window-only control), then add
the brace probe.
usage: python -I build_round3.py <full|window> <out.pack>"""
import subprocess, sys
from pathlib import Path
sys.path.insert(0, r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools")
import rolepath  # noqa: F401 -- because it puts the role dirs (lib/, pipelines/) on sys.path
import air_dive_rules

H = Path(__file__).resolve().parent
variant, out = sys.argv[1], sys.argv[2]
seen = {"cut": 0}
if variant == "window":
    air_dive_rules.mass_factor = lambda row: 1.0
elif variant == "full":
    _orig = air_dive_rules.tuned_cells

    def tuned_cells(row, declared=()):
        cells = _orig(row, declared)
        if "mass" in cells:
            seen["cut"] += 1
        return cells
    air_dive_rules.tuned_cells = tuned_cells
else:
    raise SystemExit(f"unknown variant {variant}")
import build_air_dive_minimod  # noqa: E402 -- because the override above must be in place first
base = H / "packs" / f"_base_{variant}.pack"
build_air_dive_minimod.main(["--out", str(base), "--probe"])
print(f"variant {variant}: rows with a cut mass {seen['cut']}")
if variant == "full" and not seen["cut"]:
    raise SystemExit("REFUSING: the full build cut no mass")
subprocess.run([sys.executable, "-I", str(H / "mkprobe.py"), str(base), out], check=True)

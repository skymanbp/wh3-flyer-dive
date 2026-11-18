"""TEST-ONLY: goal distance and order target through the brake before the melee order (batch-E residuals)."""
import sys, math
sys.path.insert(0, ".")
import brace_an as b
for lab, lane in [("E1_wyvern",1),("E2_wyvern",2),("E2_eagle",3),("E3_eagle",1)]:
    for rec in b.lanes(lab):
        if rec["lane"] != lane or rec["stop"] is None: continue
        s, td = rec["s"], rec["touchdown"]
        j = next(k for k in range(td, len(s)) if s[k]["vt"] == "43ADE470")
        print(lab, lane, rec["target"])
        for r in s[max(td, j-8):j+1]:
            g = math.hypot(r["gx"]-r["x"], r["gz"]-r["z"]); g7 = math.hypot(r["g7x"]-r["x"], r["g7z"]-r["z"])
            print(f"    {r['t']-s[td]['t']:+.1f} st {r['st']} s1c8 {r['s1c8']:5.2f} goal {g:6.1f} g7 {g7:6.1f} otgt {r['otgt']} ab0 {r['ab0']} vt {r['vt']}")

"""TEST-ONLY: rows around the melee-order arrival for batch-E residual early stops."""
import sys
sys.path.insert(0, ".")
import brace_an as b
for lab, lane in [("E1_wyvern",1),("E2_wyvern",2),("E2_eagle",3),("E3_eagle",1),("E2_chim",2),("E3_mant",1),("E1_eagle",2)]:
    for rec in b.lanes(lab):
        if rec["lane"] != lane or rec["stop"] is None: continue
        s, td = rec["s"], rec["touchdown"]
        j = next(k for k in range(td, len(s)) if s[k]["vt"] == "43ADE470")
        print(lab, lane, rec["target"])
        for r in s[max(td, j-4):j+1]:
            print(f"    {r['t']-s[td]['t']:+.1f} st {r['st']} sl {r['slot']} s1c8 {r['s1c8']:.2f} lay {r['lay']} fm {r['fm']} vt {r['vt']}")

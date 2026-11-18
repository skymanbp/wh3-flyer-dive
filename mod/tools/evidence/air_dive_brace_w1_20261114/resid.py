"""TEST-ONLY: residual batch-E early stops: rows around the stop + when the melee order arrived + engage events."""
import sys
sys.path.insert(0, ".")
import brace_an as b
for lab, lane in [("E1_wyvern",1),("E2_wyvern",2),("E2_eagle",3),("E3_eagle",1),("E1_wyvern",3),("E3_wyvern",3),("E2_terror",3),("E1_eagle",3)]:
    for rec in b.lanes(lab):
        if rec["lane"] != lane or rec["stop"] is None: continue
        s, i, td = rec["s"], rec["stop"], rec["touchdown"]
        ent = s[i]["ent"]
        first470 = next((r for r in s[td:] if r["vt"] == "43ADE470"), None)
        evs = [(round(t - s[td]["t"],1), k) for t, k, p in rec["EV"] if len(p) > 4 and p[4] == ent and t >= s[td]["t"] - 1]
        print(f"{lab} lane {lane} {rec['target']} td {s[td]['t']:.1f} stop +{s[i]['t']-s[td]['t']:.1f}  melee-order at "
              f"{'+%.1f' % (first470['t']-s[td]['t']) if first470 else '-'} (st {first470['st'] if first470 else '-'} lay {first470['lay'] if first470 else '-'} fm {first470['fm'] if first470 else '-'})  events {evs[:8]}")
        for r in s[max(td, i-3):i+2]:
            print(f"    {r['t']-s[td]['t']:+.1f} st {r['st']} sl {r['slot']} v {(r['vx']**2+r['vz']**2)**.5:.2f} s1c8 {r['s1c8']:.2f} lay {r['lay']} fm {r['fm']} vt {r['vt']} mst {r['mst']} mslot {r['mslot']} r324 {r['r324']}")

"""TEST-ONLY: brace_an.py --table gets an 'early' flag (travel < 15 m) and a cause per stop, read from
the probe events and samples in the 1.0 s before the brake tick:
  contact-engage  an M line (melee order ctor 0x14305abb4, issued from contact-engage) for this flyer
  re-order        an O line (0x143aed8c8 ctor) or the order vtable turning to 0x143aed8c8
  flight-ended    +0x710 went to 0 on the ground while the flyer was still fast
  other           none of the above (printed with its order / state change)"""
from pathlib import Path

p = Path(__file__).resolve().parent / "brace_an.py"
s = p.read_text("utf-8")
assert "def cause(" not in s
s = s.replace('''def main(argv):''', '''def cause(rec):
    s, i = rec["s"], rec["stop"]
    t0 = s[i]["t"]
    ent = s[i]["ent"]
    evs = [(t, k) for t, k, p in rec["EV"] if t0 - 1.0 <= t <= t0 + 0.05 and len(p) > 4 and p[4] == ent]
    if any(k == "M" for t, k in evs):
        return "contact-engage"
    win = [r for r in s if t0 - 1.0 <= r["t"] <= t0]
    if any(k == "O" for t, k in evs) or any(r["vt"] == "43AED8C8" for r in win):
        return "re-order"
    if any(a["fm"] != 0 and b["fm"] == 0 and b["lay"] == 0 for a, b in zip(win, win[1:])):
        return "flight-ended"
    return f"other({s[i - 1]['vt']}->{s[i]['vt']} st {s[i - 1]['st']}->{s[i]['st']})"


def main(argv):''')
old = '''                print(f"{lab:14s} lane {rec['lane']} {rec['target']:7s} men {rec['men']} STOP +{r0['t'] - s[rec['touchdown']]['t']:.1f}s "
                      f"travel {rec['travel']:.1f} m st/slot {s[rec['stop'] - 1]['st']}/{s[rec['stop'] - 1]['slot']} "
                      f"order {s[rec['stop'] - 1]['vt']}->{r0['vt']}")'''
new = '''                early = "EARLY" if rec["travel"] < 15 else "late "
                print(f"{lab:14s} lane {rec['lane']} {rec['target']:7s} men {rec['men']} STOP {early} +{r0['t'] - s[rec['touchdown']]['t']:.1f}s "
                      f"travel {rec['travel']:.1f} m st/slot {s[rec['stop'] - 1]['st']}/{s[rec['stop'] - 1]['slot']} "
                      f"cause {cause(rec)}")'''
assert old in s
s = s.replace(old, new)
p.write_text(s, "utf-8")
print("patched")

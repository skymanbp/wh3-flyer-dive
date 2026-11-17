#!/usr/bin/env python3
"""Read what the per-soldier recorder wrote. [ENGINE-ENTITY-READ-W1 2026-11-11]

Parses ld_entity_read.txt (format in ``pipelines/entity_read.lua``'s header)
and answers, for one target unit and one instant (a touchdown):

* how many of its men entered a knock animation (Derpy's slots 143-197) in
  the window after the instant, and how many it lost;
* each man's hit-point loss in the window (by model id);
* whether the summed per-man hit points agree with the engine's own
  ``unit:unary_hitpoints()`` (the cross-check that the reads are real).

It also cross-tabulates model +0x324 against the knock slots over every
sample, the in-game test of the donors' disagreement about that field
(``knock324_crosstab``). A record that stopped, failed, or never sampled is
never a measurement: ``problems()`` names why.

usage: python -P tools/pipelines/entity_read_report.py <ld_entity_read.txt slice>
/ 读逐兵模记录：撞倒几人、每人掉血、与单位血量对账、+0x324 交叉表。
"""
import json
import sys

KNOCK_SLOTS = range(143, 198)     # Derpy combat.lua: knock() 143..197
STATE_KNOCK = (14, 15, 16, 17)    # Altius: knocked back/down/flying, getting up
WINDOW_S = 1.5
UNARY_TOL = 0.01


def parse_text(text):
    """[battle] with header, units {uid: {...}}, checks, ticks [(t_s, {uid: row})], notes."""
    battles, cur = [], None
    for raw in (text or "").splitlines():
        parts = raw.split(" ")
        tag = parts[0] if parts else ""
        if tag == "BATTLE":
            cur = {"header": raw, "units": {}, "checks": {}, "ticks": [], "notes": []}
            battles.append(cur)
        elif cur is None:
            continue
        elif tag == "UNIT" and len(parts) >= 5:
            cur["units"][parts[1]] = {"alliance": int(parts[2]), "key": parts[3],
                                      "men": int(parts[4].split("=", 1)[1])}
        elif tag == "CHECK":
            cur["checks"][parts[1]] = " ".join(parts[2:])
        elif tag == "T" and len(parts) == 2:
            cur["ticks"].append((int(float(parts[1])) / 1000.0, {}))
        elif tag == "U" and cur["ticks"] and len(parts) >= 7:
            models, flight = [], None
            for m in parts[7:]:
                if m.startswith("f="):          # [AIR-DIVE-W16] model +0x710 / +0x70c
                    flight = m[2:]
                    continue
                f = m.split(",")
                if len(f) not in (8, 12):
                    continue
                rec = {"id": f[0], "x": float(f[1]), "z": float(f[2]),
                       "cur": int(f[3]), "max": int(f[4]), "slot": int(f[5]),
                       "st": int(f[6]), "mslot": int(f[7])}
                if len(f) == 12:                # [AIR-DIVE-W16] +0x1c8 / +0xab0
                    rec.update(spd=float(f[8]), hits=_load(f[9]),
                               mspd=float(f[10]), mhits=_load(f[11]))
                models.append(rec)
            cur["ticks"][-1][1][parts[1]] = {
                "alive": int(parts[2]), "n": int(parts[3]), "unary": float(parts[4]),
                "sum_cur": int(parts[5]), "sum_max": int(parts[6]), "flight": flight,
                "models": models}
        elif tag in ("STOP", "FAIL", "END", "ERROR"):
            cur["notes"].append(raw)
    return battles


def _load(cell):
    """+0xab0: an F32 written by the reader ("4.50"); the first W16 run
    wrote it as an I32 (its F32 bits) -- both read back as the float."""
    import struct
    if "." in cell or cell == "-1":     # "-1": no mount
        return float(cell)
    return struct.unpack("<f", struct.pack("<i", int(cell)))[0]


def problems(battle):
    out = [n for n in battle["notes"] if not n.startswith("END")]
    if not battle["ticks"]:
        out.append("the reader recorded no tick")
    if not battle["checks"]:
        out.append("no unit passed the start check")
    for uid in battle["checks"]:
        u = unary_check(battle, uid)
        if u is not None and u["ticks"] and not u["agree"]:
            out.append(f"unit {uid}: per-man hit points disagree with "
                       f"unary_hitpoints() by {u['max_abs_diff']}")
    return out


def knocked(m):
    """A knock animation (Derpy's slots, the man's or his mount's)."""
    return m["slot"] in KNOCK_SLOTS or m["mslot"] in KNOCK_SLOTS


def knock_state(m):
    """+0x324 in 14..17. Measured 2026-11-12 (run of ENGINE-ENTITY-READ-W1):
    every man-sample in a knock slot had it (14,756 / 14,756), no man with a
    readable non-knock slot had it (0), and it is also readable when the slot
    read is gated (3,629 samples with slot -1)."""
    return m["st"] in STATE_KNOCK


def unary_check(battle, uid):
    """Max |sum_cur / full_max - unary_hitpoints()| over the ticks, full_max
    = the summed max hit points of the first tick with every man alive (a
    shared mount counted once, as the recorder sums), or None."""
    men = battle["units"].get(uid, {}).get("men", 0)
    full = next((r["sum_max"] for _t, rows in battle["ticks"]
                 for u, r in rows.items() if u == uid and r["alive"] == men), None)
    if not full:
        return None
    worst, n = 0.0, 0
    for _t, rows in battle["ticks"]:
        r = rows.get(uid)
        if not r or not r["models"] or r["unary"] < 0:
            continue
        pred = r["sum_cur"] / full
        worst = max(worst, abs(pred - r["unary"]))
        n += 1
    return {"ticks": n, "max_abs_diff": round(worst, 5), "agree": n > 0 and worst <= UNARY_TOL}


def window(battle, uid, t0, span=WINDOW_S):
    """Knocks and losses of ``uid``'s men in [t0, t0 + span]."""
    before = None
    inside = []
    for t, rows in battle["ticks"]:
        r = rows.get(uid)
        if r is None:
            continue
        if t <= t0:
            before = (t, r)
        elif t <= t0 + span:
            inside.append((t, r))
    if before is None or not inside:
        return None
    b = {m["id"]: m for m in before[1]["models"]}
    knocked_ids, st_ids, first_knock = set(), set(), None
    pre_knocked = {i for i, m in b.items() if knocked(m) or knock_state(m)}
    for t, r in inside:
        for m in r["models"]:
            if m["id"] in pre_knocked:
                continue
            if knocked(m) or knock_state(m):
                if first_knock is None:
                    first_knock = round(t - t0, 2)
            if knocked(m):
                knocked_ids.add(m["id"])
            if knock_state(m):
                st_ids.add(m["id"])
    last = {m["id"]: m for m in inside[-1][1]["models"]}
    loss = {}
    for i, m in b.items():
        after = last[i]["cur"] if i in last else 0
        if m["cur"] - after:
            loss[i] = m["cur"] - after
    return {"t_before": before[0], "t_after": inside[-1][0],
            "men_before": len(b), "men_after": len(last),
            "men_knocked": len(st_ids | knocked_ids), "first_knock_after_s": first_knock,
            "men_knock_slot": len(knocked_ids), "men_state324_14_17": len(st_ids),
            "hp_before": before[1]["sum_cur"], "hp_after": inside[-1][1]["sum_cur"],
            "men_hit": len(loss), "per_man_loss": dict(sorted(loss.items()))}


def flyer_track(battle, uid, t0, span):
    """[AIR-DIVE-W16] The flyer's own reads around ``t0``: the collision-
    attack load (+0xab0, an F32 that rises by 1 per man the collision attack
    hits and decays; summed over the unit's men and mounts) at t0, its peak
    in (t0, t0 + span] (``hits_rise`` = peak - value at t0), the number of
    reader ticks on which it rose (``load_rises``), the peak +0x1c8 speed in
    that window, and the +0x710 values seen. None when no sample."""
    before, inside = None, []
    for t, rows in battle["ticks"]:
        r = rows.get(uid)
        if r is None or not r["models"] or "hits" not in r["models"][0]:
            continue
        if t <= t0:
            before = r
        elif t <= t0 + span:
            inside.append((t, r))
    if before is None or not inside:
        return None

    def hits(r):
        return round(sum(max(m["hits"], 0) + max(m["mhits"], 0) for m in r["models"]), 2)

    def speed(r):
        return max(max(m["spd"], m["mspd"]) for m in r["models"])
    base = hits(before)
    peak = max(hits(r) for _t, r in inside)
    first = next((round(t - t0, 2) for t, r in inside if hits(r) > base), None)
    seq = [hits(before)] + [hits(r) for _t, r in inside]
    rises = sum(1 for a, b in zip(seq, seq[1:]) if b > a + 1e-6)
    return {"hits_at_t0": base, "hits_rise": round(peak - base, 2), "load_peak": peak,
            "load_rises": rises, "first_hit_after_s": first,
            "peak_speed": round(max(speed(r) for _t, r in inside), 2),
            "speed_at_t0": round(speed(before), 2),
            "flight_modes": sorted({r["flight"] for _t, r in inside
                                    if r.get("flight") is not None})}


def series(battle, uid):
    """[AIR-DIVE-W16] [(t, "mode/sub", summed collision load, max speed,
    alive)] for one unit."""
    out = []
    for t, rows in battle["ticks"]:
        r = rows.get(uid)
        if r is None or not r["models"]:
            continue
        m0 = r["models"]
        hits = sum(max(m.get("hits", -1), 0) + max(m.get("mhits", -1), 0) for m in m0)
        spd = max(max(m.get("spd", -1), m.get("mspd", -1)) for m in m0)
        out.append((t, r.get("flight"), hits, spd, r["alive"]))
    return out


def knock324_crosstab(battle):
    """Over every man-sample: knock slot / other readable slot / slot gated
    (-1) x +0x324 value histogram."""
    tab = {"knock_slot": {}, "other_slot": {}, "slot_gated": {}}
    for _t, rows in battle["ticks"]:
        for r in rows.values():
            for m in r["models"]:
                side = ("knock_slot" if knocked(m) else
                        "slot_gated" if m["slot"] < 0 and m["mslot"] < 0 else "other_slot")
                tab[side][m["st"]] = tab[side].get(m["st"], 0) + 1
    return {k: dict(sorted(v.items())) for k, v in tab.items()}


def summary(battle):
    return {"header": battle["header"], "problems": problems(battle),
            "units": len(battle["units"]), "checked": len(battle["checks"]),
            "checks": battle["checks"], "ticks": len(battle["ticks"]),
            "knock324_crosstab": knock324_crosstab(battle),
            "unary_check": {u: unary_check(battle, u) for u in battle["checks"]}}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    with open(argv[0], encoding="utf-8", errors="replace") as f:
        battles = parse_text(f.read())
    if not battles:
        print("no BATTLE line")
        return 1
    print(json.dumps(summary(battles[-1]), indent=1))
    return 0 if not problems(battles[-1]) else 1


if __name__ == "__main__":
    sys.exit(main())

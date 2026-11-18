"""FLYER-SEAT-1117 (2026-11-17): a rider stays on its mount through every flight slot the mod changes.

WHAT WOULD GO WRONG WITHOUT THIS. A ridden flyer plays the mount's clip from the
renamed mount table and the rider's paired clip from the rider table, which
this mod does not change (lib/rider_seat.py). FLYER-FIX-1117 (34dfbf3) pointed
the pegasus-type mount's slot 103 at its bobbing level-flight clip while the
riders kept their steady dive clip in slot 1772: the rider's pelvis drifted up
to 1.06 m off the saddle and a player reported "the character model and the
mount are separated" the same day. Nothing caught it because every check
looked at the mount table alone.

A second cause showed in level flight after that fix (FLYER-SEAT-1117 second
half): a rider table's header s1 names the mount table it plays with, and the
renamed mount left every pegasus / hellsteed / longma rider naming the vanilla
mount; the engine then played them out of step (the vampire hung under the
hellsteed's belly). And the slot 484 the mod adds from the mount's 489 jump
attack played under the rider's own 1931 moving attack, 0.19-1.08 m off.

These checks pin:
* every installed rider table on a renamed mount copy whose s1 names the
  source ships as a copy whose s1 names the copy, carrying its land units
  (CA's own s1 mismatches listed in riders_kept);
* for every renamed table, every rider and every mount slot with a declared
  rider pair (rider_seat.RIDER_PAIR, flight and attack slots): where the pair
  that plays differs from CA's pair for that mount clip -- the clip changed
  (the levelled 103) or moved (484 from 489) -- the rider's seat offset stays
  within SEAT_TOL of its offset in CA's pair (same clock, each clip looping at
  its own length); a moved pair of the very clips CA paired counts as 0;
  a differing pair that cannot be measured fails;
* a mount slot removed under a live rider pair (104, 489) is declared with its
  evidence in REMOVED_SLOTS, so a new removal fails;
* the measurement sees the 34dfbf3 pairing (level flight clip in slot 103)
  as > 0.5 m off, so it cannot pass by measuring nothing;
* the declared seat bone per skeleton is (within SEAT_MARGIN) the bone CA's
  snug riders actually track;
* the levelled dive is level (the original FLYER-FIX-1117 defect, the body
  pitched 32 deg off level at ground level, stays fixed) and its seat bone
  did not move.
Vendored donor riders (Lore Disasters) on these mounts play the same vanilla
rider clips (hu1_hr1_sps_rider1_fly_charge_01), so they are covered by the
installed riders' measurement. The installed game is a required input: without
it nothing can be measured and the check refuses (§A14.4).
"""
import json
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import rolepath  # noqa: E402 -- tools dir must be on sys.path first (§A12.2)
import air_dive  # noqa: E402 -- same reason
import anim_codec  # noqa: E402 -- same reason
import anim_table_bin  # noqa: E402 -- same reason
import flyer_db  # noqa: E402 -- same reason
import rider_seat  # noqa: E402 -- same reason

ASSET_DIR = TOOLS_DIR.parent / "assets" / "air_dive"
SEAT_TOL = 0.05     # m; v7 re-encoding of a levelled clip moves the seat < 0.001 m
NEGATIVE_MIN = 0.5  # m; the 34dfbf3 pairing measured 1.015 m
# A rider pair is snug when some mount bone keeps the rider's pelvis within SNUG of a fixed offset; on
# horse01, 5 of CA's 8 dive pairs are (0.049-0.072 m), three track nothing tighter than 0.18 m (their
# pelvis rocks over the back). On a snug pair the declared seat must be within SEAT_MARGIN of the best
# bone (measured 2026-11-17: spine_1 0.063 / 0.075 against chest_left_0 0.049 / chest_right_0 0.072).
SNUG = 0.10
SEAT_MARGIN = 0.02


class _Game:
    """Installed tables, clip reader and the rider pairs, read once."""
    _loaded = None

    @classmethod
    def get(cls):
        if cls._loaded is None:
            data = air_dive.GAME_DATA
            missing = [n for n in air_dive.ANIM_PACKS + ("db.pack",) if not (Path(data) / n).is_file()]
            if missing:
                raise AssertionError(f"installed game data missing {missing} under {data}: "
                                     "no rider can be measured")
            bins, read_clip = air_dive.load_installed(data)
            tables = {}
            for blob in bins.values():
                try:
                    t = anim_table_bin.parse(blob)
                except anim_table_bin.BinFormatError:
                    continue  # matched_combat (version 1): not a battle table, holds no slots
                tables[t["name"]] = t
            lu, _h = flyer_db.decode_round_trip(Path(data) / "db.pack", "land_units_tables", "rider_seat")
            mo, _h = flyer_db.decode_round_trip(Path(data) / "db.pack", "mounts_tables", "rider_seat")
            mounts = {r["key"]: r for r in mo}
            riders = {}
            for r in lu:
                m = mounts.get(r.get("mount", ""))
                if m:
                    riders.setdefault(m["animation"], {}).setdefault(r["man_animation"], set()).add(m["entity"])
            cls._loaded = (tables, read_clip, riders, {})
        return cls._loaded


def _clip(path, asset_dir):
    tables, read_clip, _r, cache = _Game.get()
    key = (str(asset_dir), path.lower())
    if key not in cache:
        staged = Path(asset_dir) / path
        blob = staged.read_bytes() if staged.is_file() else read_clip(path)
        cache[key] = anim_codec.decode(blob)
    return cache[key]


def _refs(table, slot):
    return [r[0] for e in table["entries"] if e["slot"] == slot for r in e["refs"]]


# Mount slots the mod removes while the rider table keeps the paired slot. Nothing can pair there: the
# engine requests a mount slot only if the mount table has it. The evidence for each:
REMOVED_SLOTS = {
    104: "FLY_CHARGE_LAND removed by design (AIR-DIVE-MP-DIVE-W1, user ruling C8-61); in game a marker clip "
         "put back in slot 104 of the hellsteed table was never seen in flight (autotest run "
         "d_marker_vampire, 2026-11-17)",
    489: "JUMPING_ATTACK removed where the table has a 484 moving attack (dive_entries); the mount's jump "
         "attack then plays in 484, whose rider pair is measured by seat_report",
}


def _shipped_riders(asset_dir, manifest):
    """``{(rider table, mount copy): parsed shipped rider copy}`` from the manifest's ``riders_renamed``."""
    out = {}
    for rec in manifest.get("riders_renamed", []):
        out[(rec["source"], rec["s1"])] = anim_table_bin.parse((Path(asset_dir) / rec["bin"]).read_bytes())
    return out


def seat_report(asset_dir=ASSET_DIR):
    """``(measured, unmeasurable, removed)`` over every pair a renamed mount table can play with each of its
    installed riders (the shipped rider copy where the build ships one, else CA's table).

    For each mount slot S of the shipped table with a declared rider pair R (``rider_seat.RIDER_PAIR``), the
    pair that plays is (shipped mount clip in S, shipped rider clip in R); the pair CA authored for that mount
    clip is (vanilla mount clip in S0, vanilla rider clip in RIDER_PAIR[S0]) where S0 is the slot the shipped
    clip came from: S itself, or the ``slot_484_added`` source slot. A pair equal to CA's is not measured.
    ``measured`` is ``[(mount copy, rider, mount slot, error m)]``; ``unmeasurable`` lists differing pairs
    that cannot be measured (no declared seat, several mount clips, or a rider clip with no CA pair);
    ``removed`` lists ``(mount copy, rider, vanilla mount slot, rider slot)`` where the mount slot is gone but
    the rider still has its pair."""
    tables, read_clip, riders, _c = _Game.get()
    manifest = json.loads((Path(asset_dir) / "air_dive_manifest.json").read_text("utf-8"))
    shipped_riders = _shipped_riders(asset_dir, manifest)
    measured, unmeasurable, removed = [], [], []
    for rec in manifest["tables_renamed"]:
        van = tables[rec["source"]]
        shipped = anim_table_bin.parse((Path(asset_dir) / rec["bin"]).read_bytes())
        origin = {S: S for S in rider_seat.RIDER_PAIR}
        if rec.get("slot_484_added"):
            origin[air_dive.SLOT_MOVING] = rec["slot_484_added"]["from_slot"]
        skel = van["skeleton"]
        for rider_name, ents in sorted(riders.get(rec["source"], {}).items()):
            if not ents & set(rec["entities"]) or rider_name not in tables:
                continue
            rvan = tables[rider_name]
            rship = shipped_riders.get((rider_name, rec["renamed"]), rvan)
            for S, R in rider_seat.RIDER_PAIR.items():
                s, rr = _refs(shipped, S), _refs(rship, R)
                if not s:
                    if _refs(van, S) and rr:
                        removed.append((rec["renamed"], rider_name, S, R))
                    continue
                S0 = origin[S]
                v = _refs(van, S0)
                R0 = rider_seat.RIDER_PAIR.get(S0)
                rv = _refs(rvan, R0) if R0 else []
                if s == v and rr == rv:
                    if S0 != S:  # a moved pair, the very clips CA paired: same clips, same clock, offset 0
                        measured.append((rec["renamed"], rider_name, S, 0.0))
                    continue  # the pair CA authored
                if not rr and not rv:
                    continue  # the rider has no clip for it either way, as CA ships it
                if skel not in rider_seat.SEAT or len(s) != 1 or len(v) != 1 or len(rr) != len(rv):
                    unmeasurable.append((rec["renamed"], rider_name, S, s, rr, rv))
                    continue
                mbind = rider_seat.skeleton_bind(read_clip, skel)
                for rc, rc0 in zip(rr, rv):
                    rider = _clip(rc, asset_dir)
                    err = rider_seat.pair_error(_clip(s[0], asset_dir), rider, _clip(v[0], asset_dir),
                                                _clip(rc0, asset_dir), rider_seat.SEAT[skel]["seat"], mbind,
                                                rider_seat.skeleton_bind(read_clip, rider["skeleton"]))
                    measured.append((rec["renamed"], rider_name, S, round(err, 3)))
    return measured, unmeasurable, removed


def rider_header_report(asset_dir=ASSET_DIR):
    """``[(mount copy, rider table, problem)]``: every installed rider table that plays on a renamed mount copy
    and names the mount's source table in its header ``s1`` must ship as a copy whose ``s1`` names the mount
    copy and that carries the land units riding it (FLYER-SEAT-1117: with ``s1`` naming the vanilla mount the
    engine plays rider and mount out of step); a rider whose ``s1`` names something else is CA's own mismatch
    and must be listed in ``riders_kept``."""
    tables, _rc, riders, _c = _Game.get()
    manifest = json.loads((Path(asset_dir) / "air_dive_manifest.json").read_text("utf-8"))
    shipped = _shipped_riders(asset_dir, manifest)
    recs = {(r["source"], r["s1"]): r for r in manifest.get("riders_renamed", [])}
    kept = {r["rider_table"] for r in manifest.get("riders_kept", [])}
    bad = []
    for rec in manifest["tables_renamed"]:
        for rider_name, ents in sorted(riders.get(rec["source"], {}).items()):
            if not ents & set(rec["entities"]) or rider_name not in tables:
                continue
            if tables[rider_name]["s1"] != rec["source"]:
                if rider_name not in kept:
                    bad.append((rec["renamed"], rider_name, "s1 mismatch not listed in riders_kept"))
                continue
            t = shipped.get((rider_name, rec["renamed"]))
            if t is None:
                bad.append((rec["renamed"], rider_name, "no rider copy naming the mount copy"))
            elif t["s1"] != rec["renamed"] or not recs[(rider_name, rec["renamed"])]["land_units"]:
                bad.append((rec["renamed"], rider_name, f"copy s1 {t['s1']!r} or no land units"))
    return bad


class RiderStaysSeated(unittest.TestCase):
    def test_every_rider_names_its_mount_copy(self):
        self.assertEqual(rider_header_report(), [])

    def test_every_rider_stays_seated(self):
        measured, unmeasurable, _removed = seat_report()
        self.assertEqual(unmeasurable, [], "changed pairs that cannot be measured")
        slots = {m[2] for m in measured}
        self.assertIn(103, slots, "the levelled dive pairs were not measured")
        self.assertIn(air_dive.SLOT_MOVING, slots, "the added moving-attack pairs were not measured")
        self.assertGreaterEqual(len(measured), 40, "the pegasus / hellsteed / longma riders were not measured")
        bad = [m for m in measured if m[3] > SEAT_TOL]
        self.assertEqual(bad, [], f"rider off the saddle by more than {SEAT_TOL} m")

    def test_removed_slots_are_declared(self):
        _m, _u, removed = seat_report()
        self.assertTrue(removed, "no removed slot with a live rider pair was enumerated")
        self.assertEqual(sorted({r[2] for r in removed} - set(REMOVED_SLOTS)), [],
                         "a mount slot was removed under a live rider pair with no evidence it cannot play")

    def test_the_measurement_sees_the_34dfbf3_split(self):
        """Negative control: the level-flight clip in slot 103 under the rider's dive clip."""
        tables, read_clip, _r, _c = _Game.get()
        van = tables["hr1_pegasus"]
        rider = _clip(_refs(tables["hu1b_vampire_hr1_pegasus_sword"], 1772)[0], ASSET_DIR)
        err = rider_seat.seat_error(_clip(_refs(van, 102)[0], ASSET_DIR), _clip(_refs(van, 103)[0], ASSET_DIR),
                                    rider, "spine_1", rider_seat.skeleton_bind(read_clip, "horse01"),
                                    rider_seat.skeleton_bind(read_clip, rider["skeleton"]))
        self.assertGreater(err, NEGATIVE_MIN)

    def test_declared_seat_is_the_bone_cas_riders_track(self):
        tables, read_clip, riders, _c = _Game.get()
        for skel, spec in rider_seat.SEAT.items():
            pairs = set()
            for src, by_rider in riders.items():
                if src not in tables or tables[src]["skeleton"] != skel:
                    continue
                for rider_name in by_rider:
                    if rider_name not in tables:
                        continue
                    for mslot, rslot in rider_seat.RIDER_SLOT.items():
                        m, r = _refs(tables[src], mslot), _refs(tables[rider_name], rslot)
                        if m and r:
                            pairs.add((m[0], r[0]))
            self.assertTrue(pairs, f"{skel}: no authored rider pair to check the seat on")
            mbind = rider_seat.skeleton_bind(read_clip, skel)
            snug, loose = 0, []
            for mp, rp in sorted(pairs):
                with self.subTest(skeleton=skel, mount=mp, rider=rp):
                    if "fly_charge_01" not in mp:
                        continue  # the dive pair is the one the levelled clip relies on
                    mount, rider = _clip(mp, ASSET_DIR), _clip(rp, ASSET_DIR)
                    rbind = rider_seat.skeleton_bind(read_clip, rider["skeleton"])
                    spreads = {b: rider_seat.seat_spread(mount, rider, b, mbind, rbind)
                               for b, _p in mount["bones"][1:]}
                    if min(spreads.values()) > SNUG:
                        loose.append(rp)
                        continue  # CA's own pair tracks no bone tightly: no seat to name from it
                    self.assertLessEqual(spreads[spec["seat"]], min(spreads.values()) + SEAT_MARGIN)
                    snug += 1
            self.assertGreaterEqual(snug, 3, f"{skel}: too few snug rider pairs ({snug}; loose {loose})")

    def test_levelled_dive_is_level_and_keeps_its_seat(self):
        tables, read_clip, _r, _c = _Game.get()
        manifest = json.loads((ASSET_DIR / "air_dive_manifest.json").read_text("utf-8"))
        self.assertTrue(manifest["level_clips"], "no levelled dive clip shipped")
        for rec in manifest["level_clips"]:
            clip = _clip(rec["clip"], ASSET_DIR)
            spec = rider_seat.SEAT[clip["skeleton"]]
            bind = rider_seat.skeleton_bind(read_clip, clip["skeleton"])
            target = rider_seat.mean_pitch(_clip(rec["pitch_target_from"], ASSET_DIR), spec["axis"], bind)
            self.assertLess(abs(rider_seat.mean_pitch(clip, spec["axis"], bind) - target), 1.0)
            source = _clip(rec["source"], ASSET_DIR)
            self.assertGreater(abs(rider_seat.mean_pitch(source, spec["axis"], bind) - target), 20.0,
                               "the source dive is no longer the pitched clip this fixes")
            moved = max(sum((a - b) ** 2 for a, b in zip(rider_seat.bone_pos(source, f, spec["seat"], bind),
                                                          rider_seat.bone_pos(clip, f, spec["seat"], bind))) ** 0.5
                        for f in range(len(source["frames"])))
            self.assertLess(moved, 0.005)


if __name__ == "__main__":
    unittest.main()

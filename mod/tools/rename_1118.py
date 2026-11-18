#!/usr/bin/env python3
"""RENAME-1118 (docs/DECISIONS.md D9): drop `ld` from every name the mod ships.

Two commands, both deterministic:

* ``apply``  -- moves the nine shipped Lua files to their new paths and rewrites
  the old names in the repository's code, tests and Workshop texts with one
  ordered list of literal replacements. Every rule carries the number of
  replacements it must make over the whole tree; any other number (a miss, or a
  hit the map did not foresee) refuses before a byte is written. Run on a tree
  that is already renamed, it finds nothing to do and says so; a tree that is
  half renamed is refused.
  Not touched here, because they are generated: the staged flight tables
  (``python -P tools/pipelines/air_dive.py``) and the two cave site tables
  (``dive_cave_asm.py --write-site``, ``pin_cave_asm.py --write-site``). Rerun
  those after ``apply``; their sources carry the new names.

* ``check [--pack P ...]`` -- the zero-leftover check: no old name in the code
  and Workshop texts (outside the names this rename keeps on purpose, ALLOWED
  below, each with its reason) and no ``ld`` / ``LD`` token, cave mark or
  "lore disaster" in any byte of the given packs (paths, and every entry's
  content read as UTF-8 and as UTF-16). Exit 1 on any hit.

The old -> new table and the reasons are in docs/HISTORY.md, RENAME-1118.

usage:  python -P tools/rename_1118.py apply
        python -P tools/rename_1118.py check --pack <main.pack> --pack <balance.pack>
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# ---- what the rename covers ------------------------------------------------
# Paths are repository-relative, forward slashes.
MOVES = [
    ("mod/script/battle/mod/ld_flyer_dive.lua", "mod/script/battle/mod/flyer_dive.lua"),
    ("mod/script/battle/mod/ld_flyer_takeoff.lua", "mod/script/battle/mod/flyer_takeoff.lua"),
    ("mod/script/campaign/mod/ld_flyer_dive.lua", "mod/script/campaign/mod/flyer_dive.lua"),
    ("mod/script/campaign/mod/ld_flyer_takeoff.lua", "mod/script/campaign/mod/flyer_takeoff.lua"),
    ("mod/script/campaign/lore_disasters/lib/ld_flyer_dive.lua", "mod/script/campaign/flyer_dive/lib/dive.lua"),
    ("mod/script/campaign/lore_disasters/lib/ld_flyer_takeoff.lua", "mod/script/campaign/flyer_dive/lib/takeoff.lua"),
    ("mod/script/campaign/lore_disasters/lib/ld_cave_common.lua", "mod/script/campaign/flyer_dive/lib/cave_common.lua"),
    ("mod/script/campaign/lore_disasters/data/ld_flyer_dive_site.lua", "mod/script/campaign/flyer_dive/data/dive_site.lua"),
    ("mod/script/campaign/lore_disasters/data/ld_flyer_takeoff_site.lua", "mod/script/campaign/flyer_dive/data/takeoff_site.lua"),
]

# Files the text rules never touch: historical records, third-party code, the
# Lore Disasters mod's own keys (adapter input), and generated files that are
# regenerated instead (see the module docstring).
EXCLUDED_PREFIXES = (
    "mod/tools/evidence/",
    "mod/assets/vendored_scripts/",
    "mod/assets/air_dive/",
    "mod/tools/data/main_mod_flyers.json",
    "mod/script/campaign/flyer_dive/data/",          # the site tables, regenerated
    "mod/script/campaign/lore_disasters/data/",
    "mod/tools/rename_1118.py",
    "mod/tools/tests/test_no_old_names.py",          # holds old names on purpose (negative controls)
)
SCOPE_PREFIXES = ("mod/", "workshop/")

# Per-file rewrites first: comments that name the Lore Disasters mod's files, and
# lines whose new wording is not a plain substitution. (file, old, new, count)
FILE_RULES = [
    ("mod/script/battle/mod/ld_flyer_takeoff.lua",
     "-- §C8-57 and §C8-58] Ships in ld_mod.pack and in the stand-alone\n"
     "-- ld_air_dive.pack (same path, so both enabled load it once). The rule and\n",
     "-- §C8-57 and §C8-58] The rule and\n", 1),
    ("mod/script/campaign/mod/ld_flyer_takeoff.lua",
     "-- §C8-57 and §C8-58] Same shape as campaign/mod/ld_army_cap.lua: memreader_plus\n"
     "-- is loaded (it ships pinned in ld_mod.pack), the cave sites are searched at\n",
     "-- §C8-57 and §C8-58] memreader_plus (a declared prerequisite) is loaded,\n"
     "-- the cave sites are searched at\n", 1),
    ("mod/script/campaign/lore_disasters/lib/ld_cave_common.lua",
     "-- battle/mod/ld_engine_resist.lua / ld_flyer_dive.lua / ld_flyer_takeoff.lua\n",
     "-- battle/mod/flyer_dive.lua / flyer_takeoff.lua and a third cave mod's\n", 1),
    ("mod/script/campaign/lore_disasters/lib/ld_flyer_dive.lua",
     "-- ld_flyer_dive.lua — the physics dive", "-- dive.lua — the physics dive", 1),
    ("mod/script/campaign/lore_disasters/lib/ld_flyer_takeoff.lua",
     "-- ld_flyer_takeoff.lua — flyers are held", "-- takeoff.lua — flyers are held", 1),
    ("mod/script/campaign/mod/ld_flyer_dive.lua",
     'title = "Lore Disasters flyer physics dive"', 'title = "Flyer Dive: physics dive"', 1),
    ("mod/script/campaign/mod/ld_flyer_takeoff.lua",
     'title = "Lore Disasters flyer take-off"', 'title = "Flyer Dive: take-off from melee"', 1),
    ("mod/tools/pipelines/air_dive_probe.lua",
     "same relative-path convention as ld_battle_probe /\n-- ld_selftest)",
     "same relative-path convention as the main mod's\n-- battle probe and self-test)", 1),
    ("mod/tools/pipelines/air_dive_probe.lua", "lib_battle_manager.lua:802, ld_incarnate_watch",
     "lib_battle_manager.lua:802, the main mod's incarnate watch", 1),
    ("mod/tools/pipelines/air_dive_probe.lua", "ld_incarnate_watch.lua (unit key)",
     "the main mod's incarnate watch (unit key)", 1),
    ("mod/tools/pipelines/air_dive_probe.lua", "(see ld_battle_probe.lua header)",
     "(the main mod's battle probe does the same)", 1),
    # the cave buffers' marks (they feed each site table's format and source_sha)
    ("mod/tools/pipelines/dive_cave_asm.py",
     'MAGIC = b"LDFLYDV2"                           # [FLYER-FIX-1117] two counters more: v2',
     'MAGIC = b"FLYDIVE3"                           # [FLYER-FIX-1117] two counters more: v2; '
     '3: renamed (RENAME-1118)', 1),
    ("mod/tools/pipelines/pin_cave_asm.py",
     'MAGIC = b"LDFLYPN2"                  # 2: +40 single-model window (§C8-78)',
     'MAGIC = b"FLYPINS3"                  # 2: +40 single-model window (§C8-78); 3: renamed (RENAME-1118)', 1),
    # a test-only fake key; four of its five uses follow a "\t" escape, so a token rule would miss them
    ("mod/tools/tests/test_air_dive_breath.py", "ld_breath", "donor_breath", 5),
    ("mod/tools/tests/test_anim_table_rename.py",
     'bins = sorted(base.rglob("*_ld_dive*.bin"))',
     'bins = sorted(p for p in base.rglob("*_dive*.bin") if "_dive_rider" not in p.name)', 2),
    ("mod/tools/tests/test_anim_table_rename.py",
     'self.assertNotIn("_ld_", r[0], f"slot {e[\'slot\']}")',
     'self.assertNotIn("flyer_dive", r[0], f"slot {e[\'slot\']}")', 1),
    ("mod/tools/lib/anim_table_rename.py", "(``@ld_air_dive.animpack``, the W1-W7",
     "(the W1-W7 builds' own animpack,", 1),
    ("mod/tools/pipelines/air_dive.py", "same-named bins in ``@ld_air_dive.animpack``,",
     "same-named bins in the W1-W7 builds' own animpack,", 1),
    ("mod/tools/tests/test_anim_table_rename.py", "same-named bins in ``@ld_air_dive.animpack``,",
     "same-named bins in the W1-W7 builds' own animpack,", 1),
    ("mod/tools/lib/air_dive_rules.py",
     "# One owner / feature for ld_mod.pack and the stand-alone ld_air_dive.pack, so\n# the two never fight.",
     "# One owner / feature (the Lore Disasters main pack shipped the same while it\n"
     "# carried the flyer mod, so the two never fought).", 1),
    ("mod/tools/pipelines/build_air_dive_minimod.py", "inside the Lore Disasters ld_mod.pack,",
     "inside the Lore Disasters main pack,", 1),
    ("mod/tools/pipelines/build_air_dive_minimod.py", "(the Lore Disasters ld_mod.pack used the same",
     "(the Lore Disasters main pack used the same", 1),
    ("mod/tools/pipelines/build_air_dive_minimod.py", "(the Lore Disasters\n# ld_mod.pack carried",
     "(the Lore Disasters\n# main pack carried", 1),
]

# Ordered literal rules over every file in scope: (old, new, total count).
RULES = [
    # module paths and the folder the rule modules live in
    ("script/campaign/lore_disasters/lib/ld_flyer_dive", "script/campaign/flyer_dive/lib/dive", 3),
    ("script/campaign/lore_disasters/lib/ld_flyer_takeoff", "script/campaign/flyer_dive/lib/takeoff", 4),
    ("script/campaign/lore_disasters/lib/ld_cave_common", "script/campaign/flyer_dive/lib/cave_common", 5),
    ("script/campaign/lore_disasters/data/ld_flyer_dive_site", "script/campaign/flyer_dive/data/dive_site", 4),
    ("script/campaign/lore_disasters/data/ld_flyer_takeoff_site", "script/campaign/flyer_dive/data/takeoff_site", 2),
    ("lib/ld_flyer_dive", "lib/dive", 7),
    ("lib/ld_flyer_takeoff", "lib/takeoff", 6),
    ("lib/ld_cave_common", "lib/cave_common", 14),
    ("data/ld_flyer_*_site", "data/*_site", 1),
    ("ld_flyer_dive_site", "dive_site", 3),
    ("ld_flyer_takeoff_site", "takeoff_site", 3),
    ("ld_cave_common", "cave_common", 1),
    # keys the mod mints
    ("ld_flyer_very_large_entity", "flyer_dive_very_large_entity", 1),
    ("ld_flyer_large_entity", "flyer_dive_large_entity", 2),
    ("ld_flyer_* rows", "flyer_dive_* rows", 1),
    # owners, listeners, log files, entry script names
    ("ld_flyer_dive", "flyer_dive", 23),
    ("ld_flyer_takeoff", "flyer_takeoff", 20),
    # pack, fragment, animpack, animation folder, probes, adapter-only keys
    ("ld_air_dive_tables", "flyer_dive_tables", 5),
    ("ld_air_dive_probe", "flyer_dive_probe", 14),
    ("ld_air_dive_autotest", "flyer_dive_autotest", 34),
    ("ld_air_dive_charge_impact", "flyer_dive_charge_impact", 1),
    ("ld_air_dive_impact", "flyer_dive_impact", 1),
    ("ld_air_dive.pack", "flyer_dive_takeoff.pack", 15),
    ("animations/battle/ld_air_dive/", "animations/battle/flyer_dive/", 5),
    ("ld_air_dive", "flyer_dive_takeoff", 5),
    ("_ld_dive", "_dive", 23),
    ("_ld_rider", "_dive_rider", 1),
    ("_ld_level", "_dive_level", 1),
    ("_ld_plough", "_dive_plough", 4),
    ("ld_pin_on_hit_probe", "pin_on_hit_probe", 3),
    ("ld_pin_probe", "pin_probe", 6),
    # development environment variables
    ("LD_WH3_DATA", "WH3_DATA", 3),
    ("LD_WH3_ROOT", "WH3_ROOT", 3),
    ("LD_GAME_EXE", "WH3_GAME_EXE", 3),
    ("LD_VANILLA_DB_PACK", "WH3_DB_PACK", 1),
    ("LD_MEMREADER_DIR", "MEMREADER_DIR", 1),
    # tool aliases and test-only fake keys
    ("_ld_os", "_boot_os", 12),
    ("_ld_sys", "_boot_sys", 6),
    ("ld_no_such_flyer", "no_such_flyer", 1),
]

# ---- the zero-leftover check -----------------------------------------------
TOKEN = re.compile(r"[A-Za-z0-9_]*(?:(?<![A-Za-z0-9])[lL][dD](?![A-Za-z0-9])|LDFLY|[Ll]ore[ _][Dd]isaster)[A-Za-z0-9_]*")
TOKEN_B = re.compile(TOKEN.pattern.encode())

# Old-name tokens this rename keeps on purpose, by file prefix -> reason.
ALLOWED = {
    # The Lore Disasters mod's keys and names: adapter input and comments about it.
    "MAIN_MOD": "a key or name of the Lore Disasters mod (adapter input, or a comment about that mod)",
    "ENTITY_READ": "the external test-only reader's pack and log names, set by its own build script",
    "PROSE": "prose naming the Lore Disasters mod (not a name this mod ships)",
}


def _main_mod_tokens():
    """Every `ld_` key the adapter snapshot names: those stay as they are."""
    text = (REPO / "mod/tools/data/main_mod_flyers.json").read_text(encoding="utf-8")
    return {t for t in TOKEN.findall(text) if t.startswith("ld_")}


def allowed_reason(rel, token, main_mod):
    """Why an old-looking token may stay, or None. Nothing under mod/script/ (the
    shipped scripts) is ever allowed."""
    if rel.startswith("mod/script/"):
        return None
    if token in main_mod:
        return "MAIN_MOD"
    if token == "ld_" and rel == "mod/tools/lib/air_dive_rules.py":
        return "MAIN_MOD"                   # "every ``ld_`` key below" -- the adapter rows
    if token in {"ld_mod", "ld_resist_both", "ld_chr_galrauch", "ld_chr_kabandha",
                 "ld_custom_emp_inf_reiksguard_foot",
                 "lore_disasters", "lore_disasters_characters", "ld_dwf_flying_thunderbarge",
                 "ld_cth_flying_sky_ark", "ld_moncav_tze_disc", "ld_unused_teb_birdmen_wings",
                 "ld_teb_birdmen", "ld_mikael_skeletal_hippo", "ld_ovn_arb_cav_flying_carpet",
                 "ld_arb_flying_air_skiff", "ld_black_grail_hippo", "ld_blood_dragon_hippogryph",
                 "ld_bm_wf_obsidian_great_wyrm", "ld_cr_vehicle_tmb_tomb_barque",
                 "ld_cth_inf_onyx_armored_crowmen", "ld_drakenhof_templar_skeleton_manticore",
                 "ld_dread_flying_pegasus_hero", "ld_emp_griffon_blood", "ld_hef_mnt_dragon"}:
        return "MAIN_MOD"
    if token == "ld_entity_read" and rel.startswith("mod/tools/pipelines/"):
        return "ENTITY_READ"
    if token == "Lore Disasters":
        return "PROSE"
    return None


def tracked_files():
    out = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, check=True)
    return [f for f in out.stdout.splitlines() if f]


def in_scope(rel):
    return rel.startswith(SCOPE_PREFIXES) and not rel.startswith(EXCLUDED_PREFIXES)


def read(rel):
    return (REPO / rel).read_bytes().decode("utf-8")


def write(rel, text):
    # newline="" keeps the file's own line ends (a CRLF working tree stays CRLF, Lua stays LF)
    with open(REPO / rel, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _norm(s, text):
    """Rule strings are written with \\n; a CRLF file needs \\r\\n."""
    return s.replace("\n", "\r\n") if "\r\n" in text else s


def _rule_pattern(old):
    """A rule that starts with a letter or digit only matches at a token start:
    `ld_air_dive` must not match inside `build_air_dive_minimod`."""
    head = "(?<![A-Za-z0-9])" if old[0].isalnum() else ""
    return re.compile(head + re.escape(old))


def plan():
    """(moves to do, {rel: new text}, counts) -- or a refusal."""
    moves_left = [(a, b) for a, b in MOVES if (REPO / a).exists()]
    moves_done = [(a, b) for a, b in MOVES if not (REPO / a).exists() and (REPO / b).exists()]
    if len(moves_left) + len(moves_done) != len(MOVES):
        missing = [a for a, b in MOVES if not (REPO / a).exists() and not (REPO / b).exists()]
        raise SystemExit(f"[rename_1118] REFUSING: neither old nor new path exists: {missing}")
    files = [f for f in tracked_files() if in_scope(f)]
    texts = {}
    for rel in files:
        try:
            texts[rel] = read(rel)
        except UnicodeDecodeError:
            continue                        # binary: nothing to rename in it
    file_hits, rule_hits = [], []
    for rel, old, new, want in FILE_RULES:
        text = texts.get(rel)
        if text is None:
            file_hits.append((rel, old[:40], 0, want))
            continue
        o, n = _norm(old, text), _norm(new, text)
        got = text.count(o)
        file_hits.append((rel, old[:40], got, want))
        texts[rel] = text.replace(o, n)
    for old, new, want in RULES:
        got = 0
        pattern = _rule_pattern(old)
        for rel, text in texts.items():
            text2, c = pattern.subn(lambda _m, new=new: new, text)
            if c:
                got += c
                texts[rel] = text2
        rule_hits.append((old, new, got, want))
    changed = {rel: t for rel, t in texts.items() if t != read(rel)}
    return moves_left, moves_done, changed, file_hits, rule_hits


def apply(dry):
    moves_left, moves_done, changed, file_hits, rule_hits = plan()
    nothing = not moves_left and not changed
    if nothing and not any(g for *_x, g, _w in file_hits) and not any(g for *_x, g, _w in rule_hits):
        print("[rename_1118] already applied: no old path, no rule with anything to do")
        return 0
    if moves_done:
        raise SystemExit(f"[rename_1118] REFUSING: half renamed ({len(moves_done)} moves already done)")
    bad = [h for h in file_hits if h[2] != h[3]] + [h for h in rule_hits if h[2] != h[3]]
    for h in file_hits:
        print(f"  file rule {h[2]:4d} (want {h[3]:4d})  {h[0]}: {h[1]!r}")
    for h in rule_hits:
        print(f"  rule      {h[2]:4d} (want {h[3]:4d})  {h[0]!r} -> {h[1]!r}")
    if dry:
        print(f"[rename_1118] dry run: {len(changed)} files would change, {len(moves_left)} moves")
        return 0
    if bad:
        raise SystemExit(f"[rename_1118] REFUSING: {len(bad)} rules made another number of replacements "
                         "than recorded; nothing written")
    for rel, text in changed.items():
        write(rel, text)
    for a, b in moves_left:
        (REPO / b).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "-C", str(REPO), "mv", a, b], check=True)
    for d in ("mod/script/campaign/lore_disasters/lib", "mod/script/campaign/lore_disasters/data",
              "mod/script/campaign/lore_disasters"):
        p = REPO / d
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    print(f"[rename_1118] applied: {len(changed)} files rewritten, {len(moves_left)} files moved; "
          "now regenerate the staged tables and the two site tables")
    return 0


def check_tree():
    main_mod = _main_mod_tokens()
    hits = []
    old_paths = [a for a, _b in MOVES if (REPO / a).exists()]
    if old_paths:
        hits.append(("<paths>", "old path still there", old_paths))
    for rel in tracked_files():
        if not in_scope(rel) and not rel.startswith("mod/script/campaign/flyer_dive/data/"):
            continue
        if rel.startswith("mod/tools/rename_1118.py"):
            continue
        if TOKEN.search(rel):
            hits.append((rel, "old name in the path", rel))
        try:
            text = read(rel)
        except UnicodeDecodeError:
            continue
        for no, line in enumerate(text.splitlines(), 1):
            for tok in TOKEN.findall(line):
                if allowed_reason(rel, tok, main_mod) is None:
                    hits.append((rel, no, tok))
    return hits


def check_pack(path):
    sys.path.insert(0, str(REPO / "mod/tools"))
    import packfile
    pf = packfile.PackFile.open(str(path))
    hits = []
    if TOKEN.search(Path(path).name):
        hits.append((path, "pack name", Path(path).name))
    for e in pf.entries:
        if TOKEN.search(e.path):
            hits.append((e.path, "path", e.path))
        data = pf.read_file(e)
        for m in TOKEN_B.finditer(data):
            hits.append((e.path, "utf-8", m.group().decode("latin1")))
        for start in (0, 1):
            t = data[start:len(data) - ((len(data) - start) % 2)].decode("utf-16-le", errors="replace")
            for m in TOKEN.finditer(t):
                if len(m.group()) >= 4:     # two random bytes read as UTF-16 are noise, not a name
                    hits.append((e.path, "utf-16", m.group()))
    return hits, len(pf.entries)


def check(packs):
    bad = 0
    tree = check_tree()
    print(f"[rename_1118] tree: {len(tree)} old names outside the kept ones")
    for h in tree[:50]:
        print("   ", h)
    bad += len(tree)
    for p in packs:
        hits, n = check_pack(p)
        print(f"[rename_1118] pack {p}: {n} entries, {len(hits)} old-name hits")
        for h in hits[:50]:
            print("   ", h)
        bad += len(hits)
    print("[rename_1118] CLEAN" if not bad else f"[rename_1118] FOUND {bad}")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--dry-run", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("--pack", action="append", default=[])
    args = ap.parse_args(argv)
    if args.cmd == "apply":
        return apply(args.dry_run)
    return check(args.pack)


if __name__ == "__main__":
    sys.exit(main())

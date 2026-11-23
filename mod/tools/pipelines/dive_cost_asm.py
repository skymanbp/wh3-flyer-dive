"""The shipped physics-dive site table: the twelve dive caves of dive_cave_asm.py with the dive mark of
dive_mark_asm.py, plus ``dv_brace`` (D31, pipelines/dive_brace_asm.py) and ``dv_reflect`` (D51,
pipelines/dive_reflect_asm.py). This file writes ``script/campaign/flyer_dive/data/dive_site.lua`` (dive_cave_asm.py
does not: its table would drop them). MAGIC FLYDIVE9.

[D51] D15's dive cost (the cave ``dv_cost`` with its anchor ``dv_facing``, and lib/dive_cost.lua, which took a share
of maximum health) is removed; Charge Reflection on flyers is now the engine's own reflection multiply, doubled for
flyers by ``dv_reflect``. The file keeps its name (the build, the tests and HISTORY name it). The dive mark stays in
the caves (D51: removing it changes their bytes; nothing reads it now), and the 3136 bytes after it that
held the cost area stay reserved, so ``dv_brace``'s offsets do not move.

Buffer: dive_mark_asm's (the shipped layout, then the mark), then
  RESERVED_AT  3136 bytes, unused since D51 (D15's cost header and ring)
  BRACE_AT +0 u32 dv_brace's setting word   +4 u32 its counter
           +8 u32 dv_reflect's factor word (hundredths, 0 off)   +12 u32 its counter
           +16 u32 dv_brace's later steps left to the engine   +20 u32 its flyers with no slide entry (D64)
           +64 dv_brace's hit slots, one per slide slot (dive_brace_asm.HIT_BYTES each, D64)

``python dive_cost_asm.py [--write-site] [--check-exe]`` (keystone + unicorn): every emulator case of the twelve
caves with the mark, the mark's cases, dive_cave_asm's and dive_mark_asm's mutants on the marked caves,
dv_brace's and dv_reflect's cases and mutants; ``--write-site`` writes the shipped table.
"""
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
import rolepath  # noqa: F401,E402 -- imported because it puts the role directories on sys.path

import air_dive_rules  # noqa: E402 -- because rolepath above puts lib/ on sys.path
import cave_site_text  # noqa: E402 -- same reason
import dive_cave_asm as base  # noqa: E402 -- same reason (pipelines/)
import dive_mark_asm as mark  # noqa: E402 -- same reason (pipelines/)
import dive_brace_asm as brace  # noqa: E402 -- same reason (pipelines/)
import dive_reflect_asm as reflect  # noqa: E402 -- same reason (pipelines/)

MAGIC = b"FLYDIVE9"     # 4: + the mark and dv_cost (D15); 5: + dv_brace (D31); 6: dv_cost -> dv_reflect (D51); 7: hand-off 0.5, k 4 (D62); 8: once per soldier, hand-off at walk speed (D64); 9: the slide ends when the flyer stops slowing (D66)
RESERVED_AT = mark.BYTES                # 7296, a multiple of 64
BRACE_AT = RESERVED_AT + 64 + 64 * 48   # where D15's cost ring ended, so dv_brace's offsets are unchanged
BRACE_WORD_AT, BRACE_COUNT_AT = BRACE_AT, BRACE_AT + 4
# [D51] dv_reflect (dive_reflect_asm.py): the factor word Lua writes (hundredths, 0 off) and its counter
REFLECT_WORD_AT, REFLECT_COUNT_AT = BRACE_AT + 8, BRACE_AT + 12
# [D64] dv_brace's once-per-soldier memory (dive_brace_asm.py): two counters and one hit slot per slide slot
BRACE_REPEAT_AT, BRACE_NOSLOT_AT = BRACE_AT + brace.REPEAT_REL, BRACE_AT + brace.NOSLOT_REL
BRACE_HIT_AT = BRACE_AT + brace.HIT_REL
BYTES = BRACE_HIT_AT + base.SLIDE_SLOTS * brace.HIT_BYTES
EXE_SITES = {"dv_brace": brace.EXE_SITE, "dv_reflect": reflect.EXE_SITE}


def run_checks():
    """(codes, fails, counts, survivors): the marked caves under every shipped case and the mark's cases,
    dive_cave_asm's mutants on the marked sources, dive_mark_asm's mutants, dv_brace's and dv_reflect's cases and
    mutants."""
    codes, fails, counts = mark.check()
    survivors = []
    with mark._marked():
        for label, name, old, new in base.MUTANTS:
            src = mark.cave_source(name)
            if src.count(old) < 1:
                raise SystemExit(f"[dive_cost_asm] REFUSING: dive_cave_asm mutant {label!r} does not apply to the "
                                 "marked source")
            f, _n = base.CHECKS[name](base.assemble(name, src.replace(old, new, 1)))
            if not f:
                survivors.append(f"dive_cave_asm: {label}")
    survivors += [f"dive_mark_asm: {m}" for m in mark.negative_controls()]
    codes["dv_brace"] = brace.assemble(BRACE_WORD_AT, BRACE_COUNT_AT)
    f, n = brace.check(codes["dv_brace"], BRACE_WORD_AT, BRACE_COUNT_AT)
    fails += f
    counts["dv_brace"] = n
    survivors += [f"dv_brace: {m}" for m in brace.negative_controls(BRACE_WORD_AT, BRACE_COUNT_AT)]
    codes["dv_reflect"] = reflect.assemble(REFLECT_WORD_AT, REFLECT_COUNT_AT)
    f, n = reflect.check(codes["dv_reflect"], REFLECT_WORD_AT, REFLECT_COUNT_AT)
    fails += f
    counts["dv_reflect"] = n
    survivors += [f"dv_reflect: {m}" for m in reflect.negative_controls(REFLECT_WORD_AT, REFLECT_COUNT_AT)]
    return codes, fails, counts, survivors


# --- site table ------------------------------------------------------------------------------------------
CAVES = tuple(base.CAVES) + ("dv_brace", "dv_reflect")


def layout():
    lay = dict(mark.layout())
    lay.update({"bytes": BYTES, "magic": MAGIC.decode(), "brace_word_at": BRACE_WORD_AT,
                "brace_count_at": BRACE_COUNT_AT, "reflect_word_at": REFLECT_WORD_AT,
                "reflect_count_at": REFLECT_COUNT_AT, "brace_repeat_at": BRACE_REPEAT_AT,
                "brace_noslot_at": BRACE_NOSLOT_AT})
    return lay


def brace_rules():
    """[D31 / D51] the numbers the battle script and the MCT page need for dv_brace and dv_reflect, all from
    air_dive_rules"""
    r = air_dive_rules
    return {"default_on": r.BRACE_LINE_DEFAULT_ON, "k": r.BRACE_MASS_K, "k_min": r.BRACE_MASS_K_RANGE[0],
            "k_max": r.BRACE_MASS_K_RANGE[1], "k_step": r.BRACE_MASS_K_STEP, "share": r.BRACE_SHARE_MIN,
            "share_min": r.BRACE_SHARE_MIN_RANGE[0], "share_max": r.BRACE_SHARE_MIN_RANGE[1],
            "share_step": r.BRACE_SHARE_MIN_STEP, "scale": r.BRACE_WORD_SCALE,
            "reflect": r.REFLECT_FLYER_FACTOR, "reflect_min": r.REFLECT_FLYER_FACTOR_RANGE[0],
            "reflect_max": r.REFLECT_FLYER_FACTOR_RANGE[1], "reflect_step": r.REFLECT_FLYER_FACTOR_STEP,
            "mct_mod": r.BREATH_SWITCH_MCT_MOD,
            "mct_on": r.BRACE_MCT_OPTIONS["on"], "mct_k": r.BRACE_MCT_OPTIONS["k"],
            "mct_share": r.BRACE_MCT_OPTIONS["share"], "mct_reflect": r.BRACE_MCT_OPTIONS["reflect"],
            "default_word": r.brace_word(r.BRACE_MASS_K, r.BRACE_SHARE_MIN),
            "default_reflect_word": r.reflect_word(r.REFLECT_FLYER_FACTOR)}


def source_sha():
    norm = lambda s: "\n".join(line.strip() for line in s.splitlines() if line.strip())  # noqa: E731 -- because base.source_sha uses the same one-liner
    with mark._marked():
        marked = {n: norm(mark.cave_source(n)) for n in base.CAVES}
    blob = json.dumps({"base": base.source_sha(), "marked": marked, "layout": layout(),
                       "dv_brace": norm(brace.source(BRACE_WORD_AT, BRACE_COUNT_AT)),
                       "brace_site": [brace.SITE, brace.STOLEN, brace.RESUME_OFF], "brace": brace_rules(),
                       "dv_reflect": norm(reflect.source(REFLECT_WORD_AT, REFLECT_COUNT_AT)),
                       "reflect_site": [reflect.SITE, reflect.AT, reflect.STOLEN]},
                      sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def agreement_format():
    """whole and exact in a float32: players whose caves or numbers differ are told they run another version"""
    return 2 + int(source_sha()[:5], 16)


def _lua_bytes(raw):
    return "'" + "".join(f"\\{b}" for b in raw) + "'"


def template(code):
    return cave_site_text.bytes_template(code, base.BUF_PLACEHOLDER, base.RESUME_PLACEHOLDER,
                                         {base.ORIG_PLACEHOLDER: "{orig:8}"})


def site_lua(codes):
    skip_bits = struct.unpack("<I", struct.pack("<f", base.SKIP_SPEED))[0]
    lines = [
        "-- dive_site.lua -- GENERATED by tools/pipelines/dive_cost_asm.py",
        "-- (--write-site); do not edit, rerun the generator. Pure data.",
        "-- [AIR-DIVE-MP-DIVE-W1 2026-11-12, §C8-61] The physics dive: twelve code caves (dive_cave_asm.py) with the",
        "-- dive mark (dive_mark_asm.py), plus dv_brace (D31, a braced line against a dive) and dv_reflect (D51,",
        "-- Charge Reflection doubled for flyers at the engine's own multiply), as memreader Plus site-loader entries,",
        "-- plus the buffer layout and the numbers (tools/lib/air_dive_rules.py).",
        "-- / 物理俯冲：代码洞的位点表、缓冲区布局与数值（生成物）。",
        "return {",
        f"    owner = '{base.OWNER}',",
        f"    feature = '{base.FEATURE}',",
        "    entries = {",
    ]
    for name, (pattern, at, stolen, _resume) in base.CAVES.items():
        lines += cave_site_text.cave_entry_lines(
            name, base.FEATURE, pattern, at, stolen, template(codes[name]),
            base.CALL_SITES[name]["call_at"] if name in base.CALL_SITES else None)
    lines += cave_site_text.cave_entry_lines("dv_brace", base.FEATURE, brace.SITE, 0, brace.STOLEN,
                                             template(codes["dv_brace"]))
    lines += cave_site_text.cave_entry_lines("dv_reflect", base.FEATURE, reflect.SITE, reflect.AT, reflect.STOLEN,
                                             template(codes["dv_reflect"]))
    resume = {n: base.CAVES[n][3] for n in base.CAVES if base.CAVES[n][3]}
    resume["dv_brace"] = brace.RESUME_OFF
    resume["dv_reflect"] = len(reflect.REPLACED)    # from the site (match + at): api.address is the site
    b = brace_rules()
    lines += [
        "    },",
        "    caves = { " + ", ".join(f"'{n}'" for n in CAVES) + " },",
        "    resume_at = { " + ", ".join(f"{n} = {v}" for n, v in resume.items()) + " },",
        base.SITE_DISTANCES,
        "    layout = {",
        "        " + ", ".join(f"{k} = {v!r}".replace('"', "'") for k, v in layout().items()) + ",",
        "    },",
        f"    skip_speed = {base.SKIP_SPEED}, skip_speed_bits = {skip_bits},",
        "    -- [D31 / D51] dv_brace, dv_reflect and the MCT settings of the braced-line work (lib/brace_rule.lua,",
        "    -- the MCT page)",
        "    brace = {",
        f"        default_on = {'true' if b['default_on'] else 'false'}, k = {b['k']!r}, k_min = {b['k_min']!r}, "
        f"k_max = {b['k_max']!r}, k_step = {b['k_step']!r},",
        f"        share = {b['share']!r}, share_min = {b['share_min']!r}, share_max = {b['share_max']!r}, "
        f"share_step = {b['share_step']!r}, scale = {b['scale']},",
        f"        reflect = {b['reflect']!r}, reflect_min = {b['reflect_min']!r}, reflect_max = {b['reflect_max']!r}, "
        f"reflect_step = {b['reflect_step']!r},",
        f"        default_word = {b['default_word']}, default_reflect_word = {b['default_reflect_word']},",
        f"        mct_mod = '{b['mct_mod']}', mct_on = '{b['mct_on']}', mct_k = '{b['mct_k']}', "
        f"mct_share = '{b['mct_share']}', mct_reflect = '{b['mct_reflect']}',",
        "    },",
        f"    format = {agreement_format()},",
        f"    build = '{base.BUILD}',",
        f"    source_sha = '{source_sha()}',",
        "}",
    ]
    return "\n".join(lines) + "\n"


def check_site_file(mod_dir=base.MOD_DIR):
    """Offline (no keystone): the committed site table matches these sources and numbers."""
    path = Path(mod_dir) / base.SITE_LUA
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for needle in (f"source_sha = '{source_sha()}'", f"format = {agreement_format()},"):
        if needle not in text:
            raise RuntimeError(f"[dive_cost_asm] REFUSING: {path} is missing or stale (lacks {needle!r}); "
                               "rerun dive_cost_asm.py --write-site")
    return True


def check_exe(exe_path=base.EXE):
    """The twelve dive sites (dive_cave_asm.check_exe), dv_brace's and dv_reflect's sites, each exactly once and
    holding the bytes the caves replace. Returns {name: virtual address of the replaced bytes}."""
    import pefile
    found = base.check_exe(exe_path)
    pe = pefile.PE(str(exe_path), fast_load=True)
    image = pe.OPTIONAL_HEADER.ImageBase
    code = [(image + s.VirtualAddress, s.get_data()) for s in pe.sections if s.Characteristics & 0x20000000]
    for name, pattern, at, want in (("dv_brace", brace.SITE, 0, brace.STOLEN),
                                    ("dv_reflect", reflect.SITE, reflect.AT, reflect.STOLEN)):
        rx = re.compile(b"".join(b"." if t == "??" else re.escape(bytes([int(t, 16)])) for t in pattern.split()),
                        re.S)
        hits = [va + m.start() for va, data in code for m in rx.finditer(data)]
        if len(hits) != 1:
            raise RuntimeError(f"[dive_cost_asm] REFUSING: {name} matches {len(hits)} times in {exe_path}")
        if pattern.split()[at:at + len(want.split())] != want.split():
            raise RuntimeError(f"[dive_cost_asm] REFUSING: {name} pattern does not hold its replaced bytes at {at}")
        found[name] = hits[0] + at
    return found


def main(argv):
    if "--check-exe" in argv:
        print("[dive_cost_asm] exe sites:", {k: hex(v) for k, v in check_exe().items()})
    codes, fails, counts, survivors = run_checks()
    if fails:
        raise SystemExit("[dive_cost_asm] emulator check FAILED:\n  " + "\n  ".join(fails[:40]))
    if survivors:
        raise SystemExit(f"[dive_cost_asm] REFUSING: mutants passed every case: {survivors}")
    n_mut = len(base.MUTANTS) + len(mark.MUTANTS) + len(brace.MUTANTS) + len(reflect.MUTANTS)
    print(f"[dive_cost_asm] caves {', '.join(f'{n} {len(codes[n])} B' for n in codes)}; emulator cases {counts}; "
          f"{n_mut} mutants each caught ({len(base.MUTANTS)} dive, {len(mark.MUTANTS)} mark, "
          f"{len(brace.MUTANTS)} brace, {len(reflect.MUTANTS)} reflect)")
    if "--write-site" in argv:
        out = base.MOD_DIR / base.SITE_LUA
        out.write_text(site_lua(codes), encoding="utf-8", newline="\n")
        print(f"[dive_cost_asm] wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1:])

"""TEST-ONLY (AIR-DIVE-BRACE-W1, bounded-slide A/B): build the probe mini-mod with one part of the
data rule switched back to vanilla, by wrapping air_dive_rules.tuned_cells in THIS process only
(the shipped code is not edited).
  current  -- the lane as it is (dv_settle caves, turn anims off, deceleration 30)
  turn     -- allow_turn_to_move_anim / allow_static_turn_anim left vanilla (turn animations restored)
  decel    -- deceleration left vanilla (each flyer's own value)
  both     -- turn + decel
usage: python -I build_variant.py <variant> <out.pack>"""
import sys
sys.path.insert(0, r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools")
import rolepath  # noqa: F401 -- because it puts the role dirs (lib/, pipelines/) on sys.path
import air_dive_rules

DROP = {"current": (), "turn": tuple(air_dive_rules.TURN_ANIM_CELLS), "decel": ("deceleration",),
        "both": tuple(air_dive_rules.TURN_ANIM_CELLS) + ("deceleration",)}
variant, out = sys.argv[1], sys.argv[2]
drop = DROP[variant]
_orig = air_dive_rules.tuned_cells
seen = {"rows": 0, "dropped": 0}


def tuned_cells(row, declared=()):
    cells = _orig(row, declared)
    if cells:
        seen["rows"] += 1
    for k in drop:
        if k in cells:
            del cells[k]
            seen["dropped"] += 1
    return cells


air_dive_rules.tuned_cells = tuned_cells
import build_air_dive_minimod  # noqa: E402 -- because the wrapper above must be in place first
sys.argv = ["build_air_dive_minimod.py", "--out", out, "--probe"]
build_air_dive_minimod.main()
print(f"variant {variant}: rows tuned {seen['rows']}, cells left vanilla {seen['dropped']} ({', '.join(drop) or 'none'})")
if drop and not seen["dropped"]:
    raise SystemExit("REFUSING: the variant changed nothing")

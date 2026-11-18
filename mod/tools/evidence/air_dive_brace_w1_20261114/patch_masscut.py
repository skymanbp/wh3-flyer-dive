"""TEST-ONLY patch script (AIR-DIVE-BRACE-W1, user ruling 2026-11-14): flyer mass cut in the one rule
air_dive_rules.tuned_cells -- large x0.85, very_large x0.75, flying war machines / chariots excluded --
and the W16 collision-attack head-count kept on the uncut (vanilla) mass. CRLF kept."""
from pathlib import Path

P = Path(r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools/lib/air_dive_rules.py")
raw = P.read_bytes().decode("utf-8")
t = raw.replace("\r\n", "\n")
REPS = [
    ("""Untouched by design: ``fly_speed``, ``mass``, ``hit_points`` (no balance
change beyond the charge), the 6 ``fauna`` decoration birds, and rows on
any other locomotion row (``hovering_entity``, ``cathay_dragon_entity``,
``wheeled_entity``, ``small_entity``, ``medium_entity``).""",
     """* ``mass`` [AIR-DIVE-BRACE-W1, user ruling 2026-11-14]: large flyers x0.85,
  very_large x0.75 (``MASS_FACTOR``), the same large-flyer rule as
  :func:`flyer_units` (``fly_speed > 0``, not fauna, by the body row's
  size). Flying war machines and chariots keep their mass
  (``MASS_CUT_MACHINES``: the bodies whose every fielded unit is caste
  warmachine / chariot, or a machine a lord or hero rides, measured on the
  installed 9.0 tables and ld_mod 2026-11-14, flyer-balance_scratch). The
  cut ignores a declared ``mass`` (no flying character spec declares one,
  measured 2026-11-14: 3 of 256 specs do, all on foot). The W16 collision
  attack is still sized on the UNCUT mass (:func:`uncut_mass`), so the cut
  changes the body's mass and nothing else.

Untouched by design: ``fly_speed``, ``hit_points`` (no balance change beyond
the charge and the mass cut), the 6 ``fauna`` decoration birds, and rows on
any other locomotion row (``hovering_entity``, ``cathay_dragon_entity``,
``wheeled_entity``, ``small_entity``, ``medium_entity``)."""),
    ("""EXCLUDED_TYPES = frozenset({"fauna"})
""", """EXCLUDED_TYPES = frozenset({"fauna"})
# [AIR-DIVE-BRACE-W1, user ruling 2026-11-14] flyer mass by body size (module docstring)
MASS_FACTOR = {"large": 0.85, "very_large": 0.75}
# flying war machines and chariots keep their mass: every fielded unit on the body is caste warmachine /
# chariot (thunderbarges, sky junk, Cathay sky ark, skycutters), or the machine is one a lord or hero
# also rides (gyrocopter, gyrobomber, sky lantern, burning chariot) -- 11 bodies, measured 2026-11-14
MASS_CUT_MACHINES = frozenset({
    "wh3_dlc25_dwf_mnt_veh_thunderbarge", "wh3_dlc25_dwf_mnt_veh_thunderbarge_grungni",
    "ld_dwf_flying_thunderbarge", "wh3_main_cth_flying_sky_junk", "ld_cth_flying_sky_ark",
    "wh3_main_cth_flying_sky_lantern", "wh3_dlc27_hef_mnt_skycutter", "wh3_dlc27_hef_mnt_skycutter_bolt",
    "wh3_main_flying_tze_burning_chariot", "wh_main_dwf_flying_gyrocopter", "wh_main_dwf_flying_gyrobomber",
})
"""),
    ("""def tuned_cells(row, declared=()):""", """def mass_factor(row):
    \"\"\"[AIR-DIVE-BRACE-W1] The mass multiplier the rule applies to one entity row (1.0 = untouched).\"\"\"
    if not is_flyer(row) or row["key"] in MASS_CUT_MACHINES:
        return 1.0
    return MASS_FACTOR.get(row["size"], 1.0)


def uncut_mass(row):
    \"\"\"[AIR-DIVE-BRACE-W1] The mass a row had before :func:`tuned_cells` cut it -- the collision
    attack is sized on it, so the cut changes nothing but the body's mass.\"\"\"
    f = mass_factor(row)
    return float(row["mass"]) if f == 1.0 else round(float(row["mass"]) / f, 3)


def tuned_cells(row, declared=()):"""),
    ("""    out.update(knock_cells(row, declared))   # [AIR-DIVE-W16] stage C and up
    return out""", """    out.update(knock_cells(row, declared))   # [AIR-DIVE-W16] stage C and up
    f = mass_factor(row)                     # [AIR-DIVE-BRACE-W1] a declared mass is cut too
    if f != 1.0:
        out["mass"] = round(float(row["mass"]) * f, 3)
    return out"""),
    ("""def flyer_weapon_plan(land_units, mounts, entities, weapons, stage=None,
                      anchors=None):""", """def flyer_weapon_plan(land_units, mounts, entities, weapons, stage=None,
                      anchors=None, mass_of=None):"""),
    ("""    ``anchors`` default: CA's own rows among the given ones.""",
     """    ``anchors`` default: CA's own rows among the given ones.
    ``mass_of`` (row -> mass) default the row's own mass: the mass the collision
    attack is sized on [AIR-DIVE-BRACE-W1: the uncut mass]."""),
    ("""        t, c = collision_attack(e["size"], e["mass"], anchors)""",
     """        t, c = collision_attack(e["size"], mass_of(e) if mass_of else e["mass"], anchors)"""),
    ("""    cells, clones, repoint = flyer_weapon_plan(land, mounts, ents, weapons, stage,
                                               anchors=anchors)""",
     """    # [AIR-DIVE-BRACE-W1] sized on the uncut mass: an installed body's own (vanilla) mass, any other
    # body's mass before tuned_cells cut it -- the shipped rows here already carry the cut
    inst_ent = inst["battle_entities_tables"]
    cells, clones, repoint = flyer_weapon_plan(
        land, mounts, ents, weapons, stage, anchors=anchors,
        mass_of=lambda e: float(inst_ent[e["key"]][0]["mass"]) if e["key"] in inst_ent else uncut_mass(e))"""),
]
for a, b in REPS:
    assert t.count(a) == 1, a[:80]
    t = t.replace(a, b)
P.write_bytes(t.replace("\n", "\r\n").encode("utf-8"))
print("patched air_dive_rules")

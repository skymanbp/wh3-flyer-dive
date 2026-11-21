# SFO compatibility: what our pack overwrites (2026-11-21)

Read-only comparison of the released pack (`flyer_dive_takeoff.pack`, 14,103,811 bytes, sha256 `d898c50a…be30`),
SFO: Grimhammer III (Workshop 2792731173, `sfo_grimhammer_3_main.pack`, 2,110,166,586 bytes, updated 2026-11-19,
downloaded with steamcmd) and the installed game's `db.pack`. Scripts: `D:/Projects/.worktrees/wh3-flyer-dive/sfo-1121/`
(`sfo_diff.py`, `our_cols.py`; result `sfo_diff.json`).

## Players' reports

- Cutiegorgon, 2026-11-18: does not work with SFO, some flying units' health far too low.
- radalr, 2026-11-19: pegasus knights 9K health with SFO, 6K with this mod.
- krishkrush, othmane-aragon, 2026-11-16: asked for an SFO submod.

## What happens

DB merge is whole-row replacement. Our pack re-ships whole vanilla rows with a few cells changed, so where our row
wins over SFO's, every SFO cell on that row goes back to vanilla.

| Table | Our rows | SFO rows (new keys) | Overlap | SFO columns we put back to vanilla (rows) |
|---|---|---|---|---|
| land_units | 335 | 2,913 (235) | 335 | bonus_hit_points 332, attribute_group 321, rank_depth 316, melee_defence 265, melee_attack 248, charge_bonus 204, armour 154 |
| battle_entities | 137 | 1,521 (275) | 134 | hit_points 134, charge distances 119 / 89 / 60, mass 86, charge_speed 79, flying_charge_speed 76, fly_speed 72 |
| mounts | 67 | 37 (22) | 3 | entity 3 |
| melee_weapons | 182 | 1,631 (432) | 142 | ap_damage 132, damage 127, splash_attack_max_attacks 104, collision_attack_max_targets 94 |

Example: `wh2_dlc09_tmb_mon_carrion_0` bonus_hit_points vanilla 202, SFO 250, ours 202.

## The columns our pack actually changes (from vanilla)

- land_units: `man_animation` (326 rows, the renamed flight tables), `primary_melee_weapon` (62, the `_dive` clones).
- battle_entities: `deceleration`, `allow_turn_to_move_anim`, `allow_static_turn_anim`, `jump_attack_chance` (137 each),
  the three charge distances (132-134), `flying_charge_speed` (128), `locomotion_constants` (95), `mass` (93).
- mounts: `animation` (67).
- melee_weapons: `collision_attack_max_targets` (154), `..._cooldown` (139); 28 rows are new `_dive` clones.

## Consequence for a submod

A pack loaded above both SFO and the main pack, whose rows start from SFO's row and change only our columns, keeps
SFO's health, attack, defence, weapons and abilities. SFO's own new units (235 land units, 275 entities) already get
the memory-level rules (dive, braced line, take-off, Charge Reflection); the per-row work does not cover them yet.
The owner's ruling on SFO's own tuning numbers is D56.

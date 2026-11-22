"""Air dive charge: the one rule for a flying battle entity's data. [AIR-DIVE-W1]

User 2026-11-09 (CONTENT_LEDGER §C8-45 item 3): flyers go straight up and
down, charge feebly and hover in place when chasing. This module owns the
DATA half of the fix -- every emitter that ships a flying ``battle_entities``
row calls :func:`tuned_cells` and nothing else, so the rule lives in one
place. In this repository that emitter is the pack build
(``pipelines/build_air_dive_minimod.py``). The Lore Disasters mod's own
emitters called the same rule for its bodies; the rows here that name those
bodies are marked ADAPTER INPUT (kept for the future main-mod adapter pack,
never shipped by this one).
The ANIMATION half (the renamed flight tables without slot 104, slot 489
playing the plough clip whose size-class table lives here as
``PLOUGH_PROFILES``) is ``pipelines/air_dive.py`` and
``pipelines/air_dive_clips.py``.

Anchors, measured on the installed 9.0 ``battle_entities`` (1,341 rows, 143
with ``fly_speed > 0``; ``research_1109/air_dive_charge.md`` §1.1):

* ``flying_charge_speed / fly_speed``: min 1.00, median 1.39, max 1.88.
  [AIR-DIVE-W10 2026-11-11] Set per flyer from ``FLYER_CHARGE_SPEEDS``
  (role and lore, user ruling 2026-11-11), capped at 20 (CA's own maximum,
  the boss Terrorgheist). W1-W9 used one formula, ``max(own, fly_speed *
  1.6)``: dragon 9.5/12.5 -> 15.2, pegasus 10.5/13 -> 16.8.
* ``acceleration``: untouched, vanilla (flyer quartiles 6 / 6 / 8, max 11).
  W1-W16 raised it to a floor of 8 so a diving flyer reached charge speed
  inside the dive. [AIR-DIVE-TAKEOFF-W1 2026-11-12, user ruling, CONTENT_LEDGER
  §C8-58] Reverted: two runs against two on the same build (star dragon
  and griffon knights, vanilla 5-6 against the floor) showed no difference
  in touchdown speed, target damage or models knocked down, and the floor
  changed how every flyer below 8 moved in every other situation.
* ``charge_distance_*`` (commence_run / adopt_charge_pose / pick_target):
  flyer medians 35 / 30 / 35, maxima 60 / 45 / 60. Floor 50 / 40 / 45:
  the charge starts earlier, which is the room the dive needs.
* ``locomotion_constants``: ``large_entity`` and ``very_large_entity`` stand
  and turn at 0.3 / 0.2 (and refuse to start moving until facing within
  30 / 15 degrees), shared with every ground monster. Flyers on them are
  re-pointed to two rows of our own, copies of CA's rows with
  ``max_standing_turn_speed`` 1.0 and ``force_initial_turn_angle`` 90 --
  the values CA itself gives ``cathay_dragon_entity`` (1.0) and
  ``medium_entity`` (90). Ground monsters keep the shared rows.

* ``allow_turn_to_move_anim`` / ``allow_static_turn_anim`` [AIR-DIVE-W6
  2026-11-10]: both False. The W4 battle probe (user runs 2026-11-10
  14:04 and 14:41, star dragon) showed what holds a landed flyer: after the
  land clip (1.6 s on W3, 0.6 s on W5) the dragon stands at 0.00 m/s while
  its bearing turns 148.6 -> 124.2 deg at ~17.5 deg/s for 1.4-1.9 s, the
  rate of dr1's 45-degree turn clips (slots 73/74 and 932/933, 1.9 s, zero
  forward animroot) -- it lands off-axis and plays a standing turn before
  it may move, so the charge's speed is gone. CA itself switches the
  turn-to-move clip off for its big chargers (Stonehorn, Thundertusk and
  the Thundertusk boss: 3 of the 28 rows with it False) and the static
  turn off for 52 rows; flyers are 143 / 143 True on both. Off for flyers,
  the entity turns under locomotion instead of a standing clip.

* ``deceleration`` [AIR-DIVE-W7 2026-11-10]: at most 4.0. The same probe
  showed the second half of "lands and stops": a touchdown ends the fly
  charge and the engine brakes the unit at its own ``deceleration``.
  Mistwalker griffon knights touched down at 11.9 m/s 10.7 m from the
  enemy and were at 0.9 m/s 0.9 s later, 5.3 m on, still short of the
  rank -- the land clip had ended 0.1 s after touchdown (W5), so that
  braking is the entity's, not the clip's. Installed values: flyers
  median 10 (griffon 10, star dragon 10), fast ground units
  (charge_speed > 8) median 6 and down to 1 (ground demigryph 5.8,
  Stonehorn 7). Capped at 4.0 -- the lowest a vanilla flyer already has
  (and the Stonehorn RoR's) -- a flyer landing at 12 m/s carries on
  about 18 m (v^2 / 2a), through the 7-12 m gap the probe measured and
  into the rank, the way a ground charger arrives at speed.
  [AIR-DIVE-W11 2026-11-11] Now SET to 13.0 (CA's own maximum, any
  entity) for every flyer. Since W9 the slot-489 plough clip moves the
  landed flyer, so the post-touchdown braking above no longer matters;
  what the cap did instead was brake the flyer IN THE AIR: the approach
  decelerates at this value toward the stop point, v^2 = 2 a d, so at 4.0
  every flyer touched down at 6-9 m/s whatever its charge speed (probe:
  braking 2.3-4.0 m/s2 over the last 30-45 m, deceleration 1.0 -> 0.3-0.9).
  Autotest, level lanes: 4.0 -> star dragon 7.4 / 8.6, manticore 6.8 /
  6.5 m/s at touchdown; 13.0 -> 13.3 / 13.0 (88 % / 74 % of their charge
  speed); 25 (outside CA's range) -> 14.6 / 16.4.
  [AIR-DIVE-CONTINUOUS-W1 2026-11-12, §C8-59] Now 30.0, above CA's range,
  so the approach does not brake before touchdown at all and the plough
  clip can start at the arrival speed (the continuous dive). Measured,
  level lanes: star dragon cruise 13.2-13.8 m/s and no dip at touchdown
  (at 13: down to 7.5-7.7). Side effect on an ordinary move order (no
  charge; autotest --scenario move, one run each): the stop from fly speed
  takes 0.4 s / 0.3-1.3 m instead of 0.6-1.0 s / 1.6-3.6 m (peak 22-30
  m/s2 against 13-15); turning is unchanged (path / straight line
  0.85-1.0 both).

* ``jump_attack_chance`` [AIR-DIVE-W8 2026-11-10]: 100. Touchdown zeroes a
  flyer's speed; only an attack slot's clip moves the entity after it, and
  the slot-489 JUMPING_ATTACK plays right after touchdown only on this roll
  (vanilla flyers ~20). Required together with slot 104 removed from the
  renamed tables (``pipelines/air_dive.py``): canary 12 (100, slot 104
  kept) moved 0.0 m after touchdown, canary 9/10 (slot 104 removed, vanilla
  chance) about 0-5 m, canary 13 (both) 24.26 / 24.28 m, 6.5-10 m into the
  line (autotest, user-confirmed).

ONE PACK (owner ruling 2026-11-18, docs/DECISIONS.md D10, withdrawing the
2026-11-17 balance submod of D1): the mass cut is part of :func:`tuned_cells`
again and the breath usage-flag table (:func:`breath_usage_writer`, below)
ships in the same pack, ``flyer_dive_takeoff.pack``.

* ``mass`` [AIR-DIVE-BRACE-W1, user ruling 2026-11-14; back in the main
  pack 2026-11-18, D10]: large flyers x0.85,
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
  Per-entity exceptions (``MASS_SIZE_OVERRIDE``, each with its ruling): the
  celestial lion takes the large-flyer factor x0.85 although its body is
  very_large (user ruling 2026-11-15: at x0.75 the crowd slowed it below the
  2 m/s melee hand-off inside 15 m in 8 of 16 spear + halberd lanes, against
  1 of 16 uncut; §C11 AIR-DIVE-BRACE-W1 sections 19 and 22).

Untouched by design: ``fly_speed``, ``hit_points`` (no balance change beyond
the charge and the mass cut), the 6 ``fauna`` decoration birds, and rows on
any other locomotion row (``hovering_entity``, ``cathay_dragon_entity``,
``wheeled_entity``, ``small_entity``, ``medium_entity``).
/ 飞兽数据的唯一规则：冲锋速度、冲锋起跑距离、转向参数行、跳击概率 100（加速度不改，用原版）。
"""
from __future__ import annotations

CHARGE_CAP = 20.0
DECELERATION = 30.0  # [AIR-DIVE-CONTINUOUS-W1] no braking before touchdown (docstring)
CHARGE_DISTANCE_FLOORS = {
    "charge_distance_commence_run": 50.0,
    "charge_distance_adopt_charge_pose": 40.0,
    "charge_distance_pick_target": 45.0,
}
# vanilla shared row -> our flyer row
LOCOMOTION_REPOINT = {
    "large_entity": "flyer_dive_large_entity",
    "very_large_entity": "flyer_dive_very_large_entity",
}
LOCOMOTION_CELLS = {
    "max_standing_turn_speed": 1.0,
    "force_initial_turn_angle": 90.0,
}
EXCLUDED_TYPES = frozenset({"fauna"})
# [AIR-DIVE-BRACE-W1, user ruling 2026-11-14] flyer mass by body size (module docstring)
MASS_FACTOR = {"large": 0.85, "very_large": 0.75}
# [AIR-DIVE-BRACE-W1, user ruling 2026-11-15] entity -> the MASS_FACTOR size it is cut as instead of its
# own body size (module docstring). The boss lion is the same beast on the same body (CHARGE_SPEED rows).
MASS_SIZE_OVERRIDE = {
    "wh3_dlc24_cth_mon_celestial_lion": "large",
    "wh3_dlc27_cth_mon_celestial_lion_boss": "large",
}
# flying war machines and chariots keep their mass: every fielded unit on the body is caste warmachine /
# chariot (thunderbarges, sky junk, Cathay sky ark, skycutters), or the machine is one a lord or hero
# also rides (gyrocopter, gyrobomber, sky lantern, burning chariot) -- 11 bodies, measured 2026-11-14
# ADAPTER INPUT: ld_dwf_flying_thunderbarge and ld_cth_flying_sky_ark are Lore Disasters donor bodies
# (data/main_mod_flyers.json) that this pack does not ship; they cut nothing here (no installed entity
# has those keys) and stay so the future main-mod adapter pack keeps the same machine set.
MASS_CUT_MACHINES = frozenset({
    "wh3_dlc25_dwf_mnt_veh_thunderbarge", "wh3_dlc25_dwf_mnt_veh_thunderbarge_grungni",
    "ld_dwf_flying_thunderbarge", "wh3_main_cth_flying_sky_junk", "ld_cth_flying_sky_ark",
    "wh3_main_cth_flying_sky_lantern", "wh3_dlc27_hef_mnt_skycutter", "wh3_dlc27_hef_mnt_skycutter_bolt",
    "wh3_main_flying_tze_burning_chariot", "wh_main_dwf_flying_gyrocopter", "wh_main_dwf_flying_gyrobomber",
})
# [AIR-DIVE-W6] no standing turn clip after landing (module docstring)
TURN_ANIM_CELLS = {
    "allow_turn_to_move_anim": False,
    "allow_static_turn_anim": False,
}
# [AIR-DIVE-W8] was 100 (slot 489 played the plough clip right after
# touchdown). [AIR-DIVE-MP-DIVE-W1 2026-11-12, §C8-61] 0: the shipped ground
# handoff plays no jump attack at touchdown; a landed flyer keeps moving and
# the collisions slow it (pipelines/air_dive.py dive_entries,
# lib/dive.lua).
JUMP_ATTACK_CHANCE = 0

# [AIR-DIVE-W10 2026-11-11] Charge speed per flyer, by role and lore (user
# ruling 2026-11-11: "不要全部一样，根据定位和背景逐个调整" -- no single
# formula). One row per flying battle entity (fly_speed > 0, not fauna): the
# installed flyers this pack overrides, and ADAPTER INPUT: every ``ld_`` key
# below -- the Lore Disasters mod's three own bodies (ld_chr_galrauch,
# ld_chr_kabandha, ld_moncav_tze_disc) and its 17 donor flyers
# (data/main_mod_flyers.json). This pack ships none of those 20 rows. They stay
# because pipelines/air_dive.py counts the bodies that ride a flight table (one
# renamed copy per charge speed, so the staged tables depend on them) and the
# future main-mod adapter pack needs the same rule rows;
# tests/test_air_dive_charge_speeds.py pins all three sets, no stale row.
# A flyer with no row is a refusal in tuned_cells, so every emitter fails
# closed on a new flyer.
# Anchor: the installed flying_charge_speed (flyers 3.2 .. 20, common
# 10.5 .. 15; the boss Terrorgheist's 20 is CA's maximum and the engine's
# observed displacement cap). Bands, so a role reads the same everywhere:
#   skirmisher    light, fast flyers that strike and wheel away   15 .. 19
#   mounted_hero  a hero on one of those steeds                   same as steed
#   shock_monster mid-weight beasts built to hit a line           14 .. 17.5
#   heavy_dragon  dragons and wyrms: slower wings, huge mass      14 .. 17
#   greater_daemon daemon princes and greater daemons             13 .. 17
#   machine       gyrocopters, skycutters (fast) / airships, barges (vanilla)
# Speed is not the whole hit: collision damage scales with mass, so a star
# dragon at 15 still lands harder than a pegasus at 18 (§C11 AIR-DIVE-GRIFFON
# phase 2: the plough's first 1.5 s is almost all collision damage).
# / 每个飞兽一行冲锋速度，按定位与背景定；缺行即拒绝。
FLYER_ROLES = ("skirmisher", "mounted_hero", "shock_monster", "heavy_dragon",
               "greater_daemon", "machine")
FLYER_CHARGE_SPEEDS = {
    # --- skirmisher: fast, light ------------------------------------------
    "wh_dlc05_wef_mon_great_eagle_blood": (19.0, "skirmisher", "Great Eagles: the swiftest birds in the setting; vanilla's fastest common flyer (15)"),
    "wh_dlc05_wef_hawk_blood": (19.0, "skirmisher", "Warhawk riders: Athel Loren's light raiding hawks, as fast as the eagles"),
    "wh_main_flying_pegasus_blood": (18.0, "skirmisher", "Pegasus knights: fast and light, Bretonnia's aerial lancers"),
    "wh2_main_def_mnt_dark_pegasus": (18.0, "skirmisher", "Dark pegasi: the same light steed as the Bretonnian pegasus"),
    "wh3_main_flying_jade_longma_blood": (18.0, "skirmisher", "Jade Longma: celestial horses of Cathay, swift skirmish cavalry"),
    "wh2_dlc12_lzd_ripperdactyl_blood": (18.0, "skirmisher", "Ripperdactyls: frenzied diving killers, faster than terradons"),
    "wh_main_vmp_cavalry_flying_hellsteed_blood": (17.0, "skirmisher", "Hellsteeds: fast nightmare steeds, lighter in the hit than living mounts"),
    "wh2_main_lzd_terradon_blood": (17.0, "skirmisher", "Terradons: skink dive-bombers, fast passes over the line"),
    "wh2_main_lzd_terradon_blessed_blood": (17.0, "skirmisher", "Blessed terradons: same mount as the terradon riders"),
    "wh2_main_lzd_terradon_zwup_blood": (17.0, "skirmisher", "Zwup's terradon: same mount as the terradon riders"),
    "wh_main_flying_fell_bat_blood": (17.0, "skirmisher", "Fell bats: frenzied giant bats that swarm in fast"),
    "wh3_main_arkhan_tmb_flying_fell_bat_blood": (17.0, "skirmisher", "Arkhan's fell bats: same frenzied bats"),
    "wh3_main_tze_flying_screamer": (17.0, "skirmisher", "Screamers: sky-sharks of Tzeentch that slash on the pass"),
    "wh3_dlc24_tze_mon_flying_screamer_ror": (17.0, "skirmisher", "Screamers regiment of renown: same daemons"),
    "wh3_main_infantry_dae_furies_blood": (17.0, "skirmisher", "Chaos furies: winged daemons that drop on prey"),
    "wh3_main_infantry_kho_furies_blood": (17.0, "skirmisher", "Khorne furies: same daemons"),
    "wh3_main_infantry_nur_furies_blood": (17.0, "skirmisher", "Nurgle furies: same daemons"),
    "wh3_main_infantry_sla_furies_blood": (17.0, "skirmisher", "Slaanesh furies: same daemons"),
    "wh3_main_infantry_tze_furies_blood": (17.0, "skirmisher", "Tzeentch furies: same daemons"),
    "wh2_main_infantry_harpies_blood": (16.0, "skirmisher", "Harpies: light, savage swoopers, infantry-weight in the hit"),
    "wh2_main_infantry_harpies_blood_ror": (16.0, "skirmisher", "Harpies regiment of renown: same creatures"),
    "wh_dlc05_bst_inf_harpy": (16.0, "skirmisher", "Beastmen / Wood Elf harpies: same creatures"),
    "ld_ovn_arb_cav_flying_carpet": (16.0, "skirmisher", "Araby flying carpets: light enchanted skirmishers (OvN donor)"),
    "wh2_dlc09_tmb_flying_carrion": (15.0, "skirmisher", "Carrion: undead vultures, quick but feeble in the strike"),
    "wh2_dlc09_tmb_flying_carrion_ror": (16.0, "skirmisher", "Carrion regiment of renown: larger birds, vanilla gives them +3"),
    "wh3_dlc27_tmb_mon_carrion_boss": (17.0, "skirmisher", "Boss carrion: vanilla already 15, the fastest carrion"),
    "wh3_dlc26_ogr_blood_vultures": (15.0, "skirmisher", "Blood vultures: scavenger birds of the Mountains of Mourn"),
    "wh3_dlc24_cth_inf_onyx_crowmen": (15.0, "skirmisher", "Onyx crowmen: winged infantry that harry and wheel away"),
    "wh3_dlc24_cth_inf_onyx_crowmen_ror": (15.0, "skirmisher", "Onyx crowmen regiment of renown: same infantry"),
    "ld_cth_inf_onyx_armored_crowmen": (14.0, "skirmisher", "Armoured crowmen: the onyx crowmen in plate, one step slower (Zerooz donor)"),
    "wh2_dlc11_cst_mon_deck_dropper_bat": (15.0, "skirmisher", "Deck droppers: bats ferrying zombie gunners, bombers not chargers"),
    "ld_teb_birdmen": (14.0, "skirmisher", "Birdmen of Catrazza: men on engineered glider wings, light and slow"),
    "ld_unused_teb_birdmen_wings": (14.0, "skirmisher", "Birdmen of Catrazza wing body: same gliders"),
    # --- mounted_hero: the steed's speed -----------------------------------
    "wh_main_flying_pegasus_hero_blood": (18.0, "mounted_hero", "Heroes on pegasi: the pegasus knights' steed"),
    "wh2_main_def_mnt_dark_pegasus_sulephet": (18.0, "mounted_hero", "Morathi on Sulephet: a dark pegasus"),
    "wh2_dlc12_lzd_ripperdactyl_hero_blood": (18.0, "mounted_hero", "Skink chiefs on ripperdactyls: the ripperdactyl's speed"),
    "wh2_main_lzd_terradon_hero_blood": (17.0, "mounted_hero", "Skink chiefs on terradons: the terradon's speed"),
    "ld_dread_flying_pegasus_hero": (17.0, "mounted_hero", "Dread King's undead pegasus: a hellsteed's speed (Dread King donor)"),
    # --- shock_monster ------------------------------------------------------
    "wh_dlc01_flying_manticore_blood": (17.5, "shock_monster", "Manticores: the most ferocious shock beast, fastest of the mid-weights"),
    "wh_dlc01_mnt_flying_manticore_blood": (17.5, "shock_monster", "Manticore mounts: same beast"),
    "wh3_main_flying_manticore_blood": (17.5, "shock_monster", "Ogre feral manticore: same beast"),
    "wh3_dlc27_chs_feral_manticore_boss": (17.5, "shock_monster", "Boss manticore: same beast"),
    "wh_dlc07_brt_mnt_hippogryph_blood": (17.0, "shock_monster", "Royal hippogryph knights: Bretonnia's heaviest lance charge, ferocious mounts"),
    "wh_main_brt_mnt_hippogryph_hero_blood": (17.0, "shock_monster", "Heroes on hippogryphs: same mount"),
    "wh_main_brt_mnt_hippogryph_beaquis_blood": (17.5, "shock_monster", "Beaquis: Louen's legendary hippogryph, vanilla gives it the most mass"),
    "wh_main_flying_griffon_blood": (16.0, "shock_monster", "Griffons: strong shock flyers, heavier than pegasi, quicker than dragons"),
    "wh_main_flying_griffon_legendary_blood": (16.5, "shock_monster", "Deathclaw and Eltharion's griffon: the largest griffons"),
    "ld_emp_griffon_blood": (16.0, "shock_monster", "Empire griffon (Zerooz donor): a griffon"),
    "wh_main_flying_wyvern_blood": (16.0, "shock_monster", "Wyverns: fast, vanilla's quickest wyrm (fly 11)"),
    "wh3_dlc27_sla_mon_preyton": (16.0, "shock_monster", "Preytons: Slaanesh's stag-winged hunters, swift predators"),
    "wh3_dlc27_sla_mon_preyton_boss": (16.0, "shock_monster", "Boss preyton: same beast"),
    "wh3_dlc27_sla_mon_preyton_ror": (16.0, "shock_monster", "Preyton regiment of renown: same beast"),
    "wh2_dlc17_lzd_mon_coatl": (16.0, "shock_monster", "Coatl: feathered sky-serpent, a swift glider"),
    "wh2_dlc17_lzd_mon_coatl_ror": (16.0, "shock_monster", "Coatl regiment of renown: same serpent"),
    "wh_main_flying_vargheists_blood": (16.0, "shock_monster", "Vargheists: frenzied winged vampires that fall on prey"),
    "ld_black_grail_hippo": (16.0, "shock_monster", "Black Grail hippogryph: a corrupted hippogryph, a step under the living one (CoU donor)"),
    "ld_blood_dragon_hippogryph": (16.0, "shock_monster", "Blood Dragon hippogryph (CoU donor): a hippogryph under a vampire knight"),
    "wh3_dlc24_cth_mon_great_moon_bird": (17.0, "shock_monster", "Great moon bird: Cathay's celestial bird, vanilla 14 like the phoenixes"),
    "wh2_main_hef_mon_phoenix": (17.0, "shock_monster", "Flamespyre phoenix: a fast firebird, vanilla 14"),
    "wh2_dlc10_hef_mon_phoenix_boss": (17.0, "shock_monster", "Boss phoenix: same firebird"),
    "wh2_dlc15_hef_mon_arcane_phoenix_0": (17.0, "shock_monster", "Arcane phoenix: same firebird"),
    "wh3_dlc27_hef_mnt_ashtari": (17.0, "shock_monster", "Ashtari: Caradryan's phoenix"),
    "wh2_main_hef_mon_phoenix_frostheart": (15.0, "shock_monster", "Frostheart phoenix: the slower ice phoenix (fly 10 against 12)"),
    "wh3_dlc27_nor_mon_chimera": (15.0, "shock_monster", "Chimera: three-headed and heavy, a brawler more than a diver"),
    "wh3_dlc27_nor_mon_chimera_boss": (15.0, "shock_monster", "Boss chimera: same beast"),
    "wh3_dlc22_tze_mon_cockatrice": (15.0, "shock_monster", "Cockatrice: a petrifying beast that fights in place"),
    "wh3_dlc27_tze_mon_cockatrice_boss": (15.0, "shock_monster", "Boss cockatrice: same beast"),
    "wh3_dlc24_cth_mon_celestial_lion": (15.0, "shock_monster", "Celestial lion: a guardian beast, sturdy rather than quick"),
    "wh3_dlc27_cth_mon_celestial_lion_boss": (15.0, "shock_monster", "Boss celestial lion: same beast"),
    "wh_main_flying_terrorgheist_blood": (15.0, "shock_monster", "Terrorgheists: huge undead bats, heavy but driven"),
    "wh_main_flying_terrorgheist_blood_qb": (15.0, "shock_monster", "Quest terrorgheist: same beast"),
    "wh2_dlc11_cst_terrorgheist_blood": (15.0, "shock_monster", "Vampire Coast terrorgheist: same beast"),
    "wh_dlc08_vmp_mon_terrorgheist_boss": (20.0, "shock_monster", "Boss terrorgheist: vanilla already 20, CA's maximum; kept"),
    "wh3_dlc23_chd_mnt_great_taurus": (15.0, "shock_monster", "Great tauruses: burning bulls that charge on wings of fire"),
    "wh3_dlc23_chd_mon_great_taurus": (15.0, "shock_monster", "Great taurus: same beast"),
    "wh3_dlc23_chd_mnt_bale_taurus": (15.0, "shock_monster", "Bale tauruses: the great taurus' larger kin"),
    "wh3_dlc23_chd_mnt_bale_taurus_cinderbreath": (15.0, "shock_monster", "Cinderbreath: Drazhoath's bale taurus"),
    "wh3_dlc23_chd_mon_bale_taurus": (15.0, "shock_monster", "Bale taurus: same beast"),
    "wh3_dlc27_chd_mon_bale_taurus_boss": (15.0, "shock_monster", "Boss bale taurus: same beast"),
    "ld_mikael_skeletal_hippo": (15.0, "shock_monster", "Skeletal hippogryph (CoU donor): bone, lighter in the charge than the living beast"),
    "ld_drakenhof_templar_skeleton_manticore": (15.0, "shock_monster", "Skeletal manticore (CoU donor): bone, slower than the living manticore"),
    "wh3_dlc23_chd_mnt_lammasu": (14.0, "shock_monster", "Lammasu: a sorcerer's ponderous winged bull, not a charger"),
    "wh3_dlc23_chd_mon_lammasu": (14.0, "shock_monster", "Lammasu: same beast"),
    "wh3_dlc27_chd_mon_lammasu_boss": (14.0, "shock_monster", "Boss lammasu: same beast"),
    "wh3_dlc29_vmp_mon_morghast": (14.0, "shock_monster", "Morghasts: heavy bone constructs of Nagash"),
    "wh3_dlc29_vmp_mon_morghast_ror": (14.0, "shock_monster", "Morghast regiment of renown: same constructs"),
    "wh3_dlc29_vmp_mnt_dread_abyssal_arkhan": (14.0, "shock_monster", "Dread abyssal: bone-wrought nightmare steed, heavy"),
    "wh3_dlc29_vmp_mnt_dread_abyssal_mannfred": (14.0, "shock_monster", "Dread abyssal: same steed"),
    "wh3_dlc29_vmp_mnt_dread_abyssal_neferata": (14.0, "shock_monster", "Dread abyssal: same steed"),
    "wh3_main_cavalry_tze_disc_knight_blood": (14.0, "shock_monster", "Doom knights on discs of Tzeentch: skimming daemon discs, light cavalry speed"),
    "ld_moncav_tze_disc": (14.0, "shock_monster", "Our Doom Knight disc body: same discs"),
    "wh3_dlc20_chs_cha_chaos_lord_hero_mtze_disc": (14.0, "shock_monster", "Chaos lords / exalted heroes on discs: the Doom Knights' disc"),
    "wh3_main_tze_herald_disc_blood": (13.0, "shock_monster", "Heralds of Tzeentch on discs: casters, slower than the knights"),
    "wh3_main_tze_iridescent_horror_disc_blood": (13.0, "shock_monster", "Iridescent horrors on discs: casters"),
    "wh3_dlc20_chs_cha_chaos_sorcerer_metal_mtze_disc": (13.0, "shock_monster", "Chaos sorcerers on discs: casters"),
    "wh3_dlc20_chs_cha_chaos_sorcerer_tzeentch_mtze_disc": (13.0, "shock_monster", "Chaos sorcerers on discs: casters"),
    "wh3_dlc24_tze_cha_blue_scribes_rider_blood": (13.0, "shock_monster", "The Blue Scribes: scholars on a disc"),
    "wh3_dlc24_tze_mon_flamers_changebringers_disc": (13.0, "shock_monster", "Changebringer flamers on discs: shooters"),
    "wh3_main_flying_tze_burning_chariot": (13.0, "shock_monster", "Burning chariots of Tzeentch: a chariot drawn by screamers"),
    "wh3_main_flying_rot_fly_blood": (13.0, "shock_monster", "Plague drones: bloated rot flies, heavy and slow"),
    "wh3_main_flying_rot_fly_hero_blood": (13.0, "shock_monster", "Heralds on rot flies: same flies"),
    "wh2_dlc17_bst_cha_malagor_blood": (15.0, "shock_monster", "Malagor the Dark Omen: a winged bray-shaman, a caster rather than a charger"),
    "wh3_dlc20_kho_cha_valkia": (18.0, "shock_monster", "Valkia the Bloody: Khorne's winged consort, a swift duellist (vanilla 15)"),
    "wh3_dlc20_sla_cha_azazel": (17.0, "shock_monster", "Azazel: Slaanesh's winged daemon prince of the Chosen, swift"),
    "ld_chr_abhorash_entity": (17.0, "shock_monster", "Abhorash: the winged Lord of the Blood Dragons, the greatest vampire warrior (Abhorash donor)"),
    # --- heavy_dragon -------------------------------------------------------
    "wh2_main_hef_mon_sun_dragon_blood": (17.0, "heavy_dragon", "Sun dragons: the youngest and quickest dragons"),
    "wh3_main_cth_mon_storm_dragon_blood": (17.0, "heavy_dragon", "Storm dragon: Cathay's tempest dragon, the fastest of the dragon emperors' kin"),
    "wh2_main_hef_mon_moon_dragon_blood": (16.0, "heavy_dragon", "Moon dragons: middle-aged dragons"),
    "wh_main_flying_dragon_blood": (16.0, "heavy_dragon", "Dragons (forest dragons and the shared dragon body): the common dragon"),
    "wh_dlc08_flying_dragon_blood": (16.0, "heavy_dragon", "Unused dragon body: the common dragon"),
    "wh2_dlc16_flying_dragon_blood_360": (16.0, "heavy_dragon", "Sisters of Twilight's forest dragon: the common dragon"),
    "wh2_main_def_black_dragon_blood": (16.0, "heavy_dragon", "Black dragons: Naggaroth's savage dragons"),
    "wh2_dlc11_def_black_dragon_lokhir_blood": (16.0, "heavy_dragon", "Lokhir's black dragon: same"),
    "wh3_dlc25_emp_mnt_carmine_dragon": (16.0, "heavy_dragon", "The Carmine Dragon: Elspeth's amethyst-bound dragon"),
    "wh3_dlc24_cth_cha_yuan_bo_dragon_blood": (16.0, "heavy_dragon", "Yuan Bo: the Jade Dragon, a dragon emperor's son"),
    "ld_hef_mnt_dragon": (16.0, "heavy_dragon", "High Elf dragon mount (Zerooz donor): the common dragon"),
    "wh2_main_hef_mon_star_dragon": (15.0, "heavy_dragon", "Star dragons: the oldest and heaviest, slow wings but 5,900 mass -- the hit is devastating"),
    "wh_main_flying_dragon_blood_boss": (15.0, "heavy_dragon", "Boss dragons: vanilla gives them 7,000 mass"),
    "wh3_dlc27_def_mon_black_dragon_boss": (15.0, "heavy_dragon", "Boss black dragon: a step under the black dragon"),
    "wh_dlc08_wef_forest_dragon_boss": (15.0, "heavy_dragon", "Boss forest dragon: a step under the common dragon"),
    "wh3_main_cth_mon_iron_dragon_blood": (15.0, "heavy_dragon", "Iron dragon: armoured in iron, heavier and slower than the storm dragon"),
    "wh_main_flying_chs_dragon_blood": (15.0, "heavy_dragon", "Chaos dragon body: a twisted dragon"),
    "wh_dlc08_flying_chaos_frost_dragon_blood": (15.0, "heavy_dragon", "Frost wyrms: vast Norscan ice wyrms"),
    "ld_chr_galrauch": (15.0, "heavy_dragon", "Galrauch: the vast twin-headed chaos dragon, 7,000 mass"),
    "wh3_dlc29_flying_zombie_dragon_blood": (14.0, "heavy_dragon", "Zombie dragons: rotting carcasses held aloft by necromancy"),
    "ld_bm_wf_obsidian_great_wyrm": (14.0, "heavy_dragon", "Obsidian great wyrm (CoU donor): a heavy stone-scaled wyrm"),
    # --- greater_daemon -----------------------------------------------------
    "wh3_main_kho_mon_bloodthirster": (17.0, "greater_daemon", "Bloodthirsters: Khorne's greater daemons hurl themselves at the foe"),
    "wh3_main_kho_cha_exalted_bloodthirster": (17.0, "greater_daemon", "Exalted bloodthirster: same"),
    "wh3_twa08_kho_mon_bloodthirster_ror": (17.0, "greater_daemon", "Bloodthirster regiment of renown: same"),
    "ld_chr_kabandha": (17.0, "greater_daemon", "Ka'Bandha: a bloodthirster"),
    "wh3_main_dae_cha_be_lakor": (17.0, "greater_daemon", "Be'lakor: the first daemon prince, a shadow that strikes fast"),
    "wh3_dlc20_chs_cha_daemon_prince_msla": (17.0, "greater_daemon", "Daemon prince of Slaanesh: the swiftest prince (vanilla 15.5)"),
    "wh3_main_dae_cha_daemon_prince": (16.0, "greater_daemon", "Daemon prince: a winged champion ascended"),
    "wh3_main_dae_cha_daemon_prince_generic": (16.0, "greater_daemon", "Daemon prince: same"),
    "wh3_dlc20_chs_cha_daemon_prince": (16.0, "greater_daemon", "Daemon prince: same"),
    "wh3_dlc20_chs_cha_daemon_prince_mkho": (16.0, "greater_daemon", "Daemon prince of Khorne: same"),
    "wh3_dlc20_chs_cha_daemon_prince_mnur": (16.0, "greater_daemon", "Daemon prince of Nurgle: same"),
    "wh3_dlc20_chs_cha_daemon_prince_mtze": (16.0, "greater_daemon", "Daemon prince of Tzeentch: same"),
    "wh3_pro10_tze_cha_daemon_prince_of_tzeentch": (16.0, "greater_daemon", "Daemon prince of Tzeentch (prologue): same"),
    "wh_main_chs_lord_of_change_blood": (15.0, "greater_daemon", "Lords of Change: sorcerers first, they do not crash in like a bloodthirster"),
    "wh_main_chs_lord_of_change_blood_ror": (15.0, "greater_daemon", "Lord of Change regiment of renown: same"),
    "wh3_main_tze_cha_exalted_lord_of_change": (15.0, "greater_daemon", "Exalted lord of change: same"),
    "wh3_main_tze_cha_kairos_fateweaver": (14.0, "greater_daemon", "Kairos Fateweaver: an ancient two-headed oracle, the least of a charger"),
    "wh3_dlc29_vmp_cha_nagash": (13.0, "greater_daemon", "Nagash: the Supreme Lord of Undeath floats to battle, he does not charge"),
    # --- machine ------------------------------------------------------------
    "wh3_dlc27_hef_mnt_skycutter": (17.0, "machine", "Skycutters: light chariots drawn by swiftfeather rocs"),
    "wh3_dlc27_hef_mnt_skycutter_bolt": (17.0, "machine", "Skycutter with bolt thrower: same chariot"),
    "wh3_dlc27_hef_mnt_skycutter_lords": (17.0, "machine", "Heroes on skycutters: same chariot"),
    "wh_main_dwf_flying_gyrocopter": (15.0, "machine", "Gyrocopters: light rotor machines, quick strafing runs"),
    "wh_main_dwf_flying_gyrobomber": (13.0, "machine", "Gyrobombers: heavier bomb-laden gyrocopters"),
    "wh3_dlc25_dwf_mnt_veh_thunderbarge": (3.2, "machine", "Thunderbarge: a dwarf airship, it does not charge; vanilla kept"),
    "wh3_dlc25_dwf_mnt_veh_thunderbarge_grungni": (3.2, "machine", "Grungni's thunderbarge: airship, vanilla kept"),
    "ld_dwf_flying_thunderbarge": (3.0, "machine", "Thunderbarge (Cody donor): airship, donor value kept"),
    "wh3_main_cth_flying_sky_junk": (3.2, "machine", "Sky junk: a Cathayan airship, vanilla kept"),
    "wh3_main_cth_flying_sky_lantern": (6.1, "machine", "Sky lantern: a floating lantern platform, vanilla kept"),
    "ld_cth_flying_sky_ark": (3.7, "machine", "Sky ark (Zerooz donor): airship, donor value kept"),
    "ld_arb_flying_air_skiff": (3.6, "machine", "Araby air skiff (Golden Magus donor): airship, donor value kept"),
    "ld_cr_vehicle_tmb_tomb_barque": (7.0, "machine", "Tomb barque (Amenemhetum donor): a floating bone barge, donor value kept"),
}


def charge_speed(key):
    """``(speed, role, reason)`` of one shipping flyer; a flyer without a row
    is a refusal (the table is the coverage list)."""
    try:
        return FLYER_CHARGE_SPEEDS[key]
    except KeyError:
        raise RuntimeError(
            f"[air_dive_rules] REFUSING: flyer {key!r} has no row in "
            "FLYER_CHARGE_SPEEDS; give it a charge speed by role and lore") from None


def _validate_charge_speeds():
    for key, (speed, role, reason) in FLYER_CHARGE_SPEEDS.items():
        if not 0 < speed <= CHARGE_CAP:
            raise RuntimeError(f"[air_dive_rules] {key}: charge speed {speed} outside (0, {CHARGE_CAP}]")
        if role not in FLYER_ROLES:
            raise RuntimeError(f"[air_dive_rules] {key}: unknown role {role!r}")
        if not reason.strip():
            raise RuntimeError(f"[air_dive_rules] {key}: empty reason")


_validate_charge_speeds()

# [AIR-DIVE-W9 2026-11-10] The from-scratch slot-489 plough clip
# (pipelines/air_dive_clips.py) moves the landed flyer by its animroot: a
# speed profile per size class, (peak m/s, travel m). The probe saw the
# landed displacement peak at 20.0 m/s even where a clip's root reached
# 27 m/s, so 20 m/s is the large class and the engine cap; a dragon's
# vanilla jump attack carries it ~20 m (canary 13: 20.1 m clip -> 24.3 m
# observed). Medium and small scale down with the body.
# [AIR-DIVE-W12 2026-11-11] The class now sets only the plough's TIMING
# (its travel / peak, i.e. how long the flyer ploughs and so how many
# knock-back splashes it throws); the peak speed is the flyer's own charge
# speed from FLYER_CHARGE_SPEEDS (user 2026-11-11: momentum = speed x mass,
# faster or heavier flyers hit harder) and the travel follows from it --
# :func:`plough_profile`. A star dragon (charge 15) ploughs at 15 m/s for
# 16.5 m, a great eagle (19) at 19 m/s for 16.9 m.
PLOUGH_PROFILES = {
    "L": (20.0, 22.0),
    "M": (18.0, 16.0),
    "S": (14.0, 11.0),
}
# skeleton -> size class, for every skeleton a renamed flight table rides;
# a skeleton missing here is a refusal in the author, never a default.
PLOUGH_SKELETON_CLASS = {
    "dragon01": "L", "dragon01b": "L", "dragon04": "L", "bird02": "L",
    "bigcat03": "L", "bigcat03b": "L", "bigcat03ca": "L", "oxen01": "L",
    "humanoid10": "L", "cockatrice01": "L",
    "bigcat02": "M", "bigcat02b": "M", "bigcat02c": "M", "bird01": "M",
    "bird01b": "M", "humanoid10e": "M", "skycutter01": "M", "humanoid06g": "M",
    "humanoid16c": "M", "humanoid08b": "M",
    "horse01": "S", "mantaray01": "S", "humanoid14": "S", "hu14_team01": "S",
}


def plough_profile(skeleton, speed):
    """[AIR-DIVE-W12] ``(class, peak m/s, travel m)`` of the plough clip for a
    flyer with plough speed ``speed`` (:func:`plough_speed`, the arrival
    speed; AIR-DIVE-CONTINUOUS-W1) on ``skeleton``: peak = the speed (at
    most CHARGE_CAP, the engine's displacement cap), travel = the class's
    travel x peak / class peak, so every flyer of a class ploughs for the
    same time. A skeleton without a class is a refusal."""
    cls = PLOUGH_SKELETON_CLASS.get(skeleton)
    if cls is None:
        raise RuntimeError(f"[air_dive_rules] REFUSING: skeleton {skeleton} has no size class")
    if not 0 < speed <= CHARGE_CAP:
        raise RuntimeError(f"[air_dive_rules] REFUSING: plough speed {speed} outside (0, {CHARGE_CAP}]")
    v_class, travel_class = PLOUGH_PROFILES[cls]
    return cls, float(speed), travel_class * speed / v_class


# [AIR-DIVE-CONTINUOUS-W1 2026-11-12, §C8-59 item 1] The continuous dive
# ("K"): the plough clip STARTS at the speed the flyer arrives with and only
# slows down -- no 0 -> peak ramp after touchdown, so the dive and the impact
# read as one move. Arrival speed = ARRIVAL_FRACTION x the flyer's charge
# speed: the flyer's own cruise in the dive, measured 2026-11-12 at
# deceleration 30 (star dragon charge 15: 13.2-13.8 m/s; feral manticore
# 17.5: 15.3-15.8 -> 0.88-0.92). The W13 body-size bonus ("按体型加重", the
# peak x 4/3 for very_large, 7/6 for large) is dropped by the same ruling:
# with no braking before touchdown the impact speed measured the same
# (star dragon hp lost at 1.5 s: 14.4 / 6.6 / 9.8 % against swordsmen /
# greatswords / braced spearmen, shipped W13 11.9 / 7.2 / 8.2 %). ``size``
# is still checked (an unknown size stays a refusal).
BODY_SIZES = ("small", "medium", "large", "very_large")
ARRIVAL_FRACTION = 0.9


def plough_speed(charge, size):
    """[AIR-DIVE-CONTINUOUS-W1] Plough clip speed (m/s, on the 0.1 grid) of a
    flyer with charge speed ``charge``: its arrival speed, capped at
    CHARGE_CAP; ``size`` must be a battle_entities size (refusal otherwise)."""
    if size not in BODY_SIZES:
        raise RuntimeError(f"[air_dive_rules] REFUSING: body size {size!r} "
                           f"not one of {BODY_SIZES}")
    return min(CHARGE_CAP, round(charge * ARRIVAL_FRACTION, 1))


def speed_tag(speed):
    """[AIR-DIVE-W12] name tag of a plough speed: 16.5 -> 'v165'."""
    tenths = round(speed * 10)
    if abs(tenths - speed * 10) > 1e-6:
        raise RuntimeError(f"[air_dive_rules] REFUSING: speed {speed} is not on a 0.1 grid")
    return f"v{tenths}"


# ADAPTER INPUT [AIR-DIVE-W12 2026-11-11]: land units and mounts the Lore
# Disasters mod's generators emit on a flight table the dive renames, as
# (source table, battle entity). This pack ships none of these rows; the air
# dive still counts them (pipelines/air_dive.py census_riders: every rider of
# a table gives its speed a renamed copy, so the staged tables depend on
# them), and :func:`dive_table` is the repoint the future main-mod adapter
# pack will call (it refuses a (table, entity) missing here).
# Measured on that mod's built ld_mod.pack 2026-11-11: its fragments
# lore_disasters (unit clones) 6, lore_disasters_characters (characters) 2.
# [AIR-DIVE-W13] GENERATED_ENTITY_SIZES: the battle_entities ``size`` of the
# two entities only that mod's generator emits (read from that built pack's
# lore_disasters_characters fragment 2026-11-11: both very_large); the
# installed entities' size is read from the installed table, never here.
GENERATED_RIDERS = (
    ("bc2_deathclaw", "wh3_dlc24_cth_mon_celestial_lion"),
    ("bc3b_dlc27_chimera", "wh3_dlc27_nor_mon_chimera"),
    ("bi1b_carrion", "wh2_dlc09_tmb_flying_carrion"),
    ("dr1_dragon_boss", "wh2_main_hef_mon_star_dragon"),
    ("dr1_dragon", "wh2_main_def_black_dragon_blood"),
    ("hu8b_vargheist", "wh_main_flying_vargheists_blood"),
    ("dr1b_chaos_dragon", "ld_chr_galrauch"),
    ("hu10_wh3_bloodthirster_axe_and_whip", "ld_chr_kabandha"),
)
GENERATED_ENTITY_SIZES = {"ld_chr_galrauch": "very_large",
                          "ld_chr_kabandha": "very_large"}


def is_flyer(row):
    """A battle entity the rule applies to: it flies and is not decoration."""
    return float(row["fly_speed"]) > 0 and row["type"] not in EXCLUDED_TYPES


def mass_factor(row):
    """[AIR-DIVE-BRACE-W1] The mass multiplier the rule applies to one entity row (1.0 = untouched)."""
    if not is_flyer(row) or row.get("key") in MASS_CUT_MACHINES or "mass" not in row:
        return 1.0                    # a partial row with no mass (a unit test's) has nothing to cut
    return MASS_FACTOR.get(MASS_SIZE_OVERRIDE.get(row.get("key"), row.get("size")), 1.0)


def uncut_mass(row):
    """[AIR-DIVE-BRACE-W1] The mass a row had before :func:`tuned_cells` cut it -- the collision
    attack is sized on it, so the cut changes nothing but the body's mass."""
    f = mass_factor(row)
    return float(row["mass"]) if f == 1.0 else round(float(row["mass"]) / f, 3)


def tuned_cells(row, declared=()):
    """``{field: new value}`` for one entity row; ``{}`` for a non-flyer.

    ``declared`` names columns an author set on purpose (a character spec's
    per-column departure); those are left alone. Only cells whose value
    changes are returned, so a caller can pass the installed bytes through
    for everything else.
    """
    if not is_flyer(row):
        return {}
    declared = set(declared)
    out = {}
    if "flying_charge_speed" not in declared:
        # [AIR-DIVE-W10] per flyer, by role and lore; no row = refusal
        want = charge_speed(row["key"])[0]
        if want != float(row["flying_charge_speed"]):
            out["flying_charge_speed"] = want
    if "deceleration" not in declared and float(row["deceleration"]) != DECELERATION:
        out["deceleration"] = DECELERATION
    for field, floor in CHARGE_DISTANCE_FLOORS.items():
        if field not in declared and float(row[field]) < floor:
            out[field] = floor
    loco = row["locomotion_constants"]
    if "locomotion_constants" not in declared and loco in LOCOMOTION_REPOINT:
        out["locomotion_constants"] = LOCOMOTION_REPOINT[loco]
    for field, value in TURN_ANIM_CELLS.items():
        if field not in declared and row[field] != value:
            out[field] = value
    if ("jump_attack_chance" not in declared
            and int(row["jump_attack_chance"]) != JUMP_ATTACK_CHANCE):
        out["jump_attack_chance"] = JUMP_ATTACK_CHANCE
    out.update(knock_cells(row, declared))   # [AIR-DIVE-W16] stage C and up
    f = mass_factor(row)                     # [AIR-DIVE-BRACE-W1] a declared mass is cut too
    if f != 1.0:
        out["mass"] = round(float(row["mass"]) * f, 3)
    return out


def _tsv_cell(text):
    if text in ("true", "false"):
        return text == "true"
    try:
        return float(text)
    except ValueError:
        return text


def _tsv_format(old, value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if "." in old:
        return f"{float(value):.{len(old.split('.', 1)[1])}f}"
    return str(int(value))


def rewrite_vendored_entities_tsv(text):
    """[AIR-DIVE-W10] ``(text, rows changed)``: :func:`tuned_cells` on every
    flyer row of one staged ``battle_entities_tables`` TSV (RPFM's format:
    column names, ``#table;version`` marker, one row per line). ADAPTER
    INPUT: the Lore Disasters mod's donor closures carry their own flying
    bodies (17 rows in 11 closures, data/main_mod_flyers.json), and that mod's
    build applied this to the in-memory copy so the staged TSV stayed
    donor-faithful. This repository's build does not call it;
    tests/test_air_dive_charge_speeds.py runs it on the snapshot rows. A
    donor flyer without a FLYER_CHARGE_SPEEDS row is a refusal.
    / 捐赠方闭包自带的飞兽实体行同样套俯冲规则（内存中改，暂存 TSV 不动）。"""
    lines = text.split("\n")
    header = lines[0].rstrip("\r").split("\t")
    changed = 0
    for i in range(2, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        eol = "\r" if line.endswith("\r") else ""
        cells = line[:len(line) - len(eol)].split("\t")
        row = {k: _tsv_cell(v) for k, v in zip(header, cells)}
        new = tuned_cells(row)
        if not new:
            continue
        for field, value in new.items():
            j = header.index(field)
            cells[j] = _tsv_format(cells[j], value)
        lines[i] = "\t".join(cells) + eol
        changed += 1
    return ("\n".join(lines) if changed else text), changed


def flyer_locomotion_rows(installed_rows):
    """Our two locomotion rows, each a copy of CA's shared row plus the cells.

    ``installed_rows`` is the decoded installed table; a missing source row is
    a refusal (the copy would otherwise be invented).
    """
    by_key = {r["key"]: r for r in installed_rows}
    rows = []
    for src, dst in sorted(LOCOMOTION_REPOINT.items()):
        if src not in by_key:
            raise RuntimeError(f"installed locomotion constants lack {src!r}")
        if dst in by_key:
            raise RuntimeError(f"{dst!r} already exists in the installed table")
        row = dict(by_key[src])
        row["key"] = dst
        row.update(LOCOMOTION_CELLS)
        rows.append(row)
    return rows


# [AIR-DIVE-W8 2026-11-10] the flight tables the dive changes (slot 104
# removed) ship under new
# names (lib/anim_table_rename.py: vanilla tables cannot be overridden by
# name); pipelines/air_dive.py records the rename map in its manifest, and
# every land-unit emitter repoints through table_renames().
_RENAMES = None


def table_renames():
    """``(records, renames)`` from the air-dive manifest
    (:func:`anim_table_rename.load_renames`: a source table maps to its one
    renamed copy, or [AIR-DIVE-W12] to ``{battle entity: copy}`` when its
    riders charge at different speeds); read once, fail-closed when the
    manifest is missing."""
    global _RENAMES
    if _RENAMES is None:
        import anim_table_rename
        import rolepath
        manifest = (rolepath.TOOLS_DIR.parent / "assets" / "air_dive"
                    / "air_dive_manifest.json")
        _RENAMES = anim_table_rename.load_renames(manifest)
    return _RENAMES


def rider_renames():
    """[FLYER-SEAT-1117 2026-11-17] ``(records, units, renames)`` for the rider
    table copies the air-dive manifest records under ``riders_renamed``
    (``pipelines/air_dive.py rider_copies``): the records (as
    :func:`anim_table_rename.rename_bin` returns them, plus ``land_units``),
    ``{land unit: (rider source, rider copy)}`` and ``{rider source: {land
    unit: rider copy}}`` (the culture-row form). Fail-closed: a missing or
    empty list, or one land unit given two copies, is a refusal."""
    import json
    import anim_table_rename
    import rolepath
    manifest = rolepath.TOOLS_DIR.parent / "assets" / "air_dive" / "air_dive_manifest.json"
    records = json.loads(manifest.read_text(encoding="utf-8")).get("riders_renamed")
    if not records:
        raise anim_table_rename.Refused(f"{manifest}: no 'riders_renamed' records")
    units, renames = {}, {}
    for rec in records:
        for unit in rec["land_units"]:
            if unit in units:
                raise anim_table_rename.Refused(f"{unit}: rider copies {units[unit][1]} and {rec['renamed']}")
            units[unit] = (rec["source"], rec["renamed"])
            renames.setdefault(rec["source"], {})[unit] = rec["renamed"]
    return records, units, renames


def dive_table(man_animation, entity):
    """The animation table a land unit on ``man_animation`` with battle
    entity ``entity`` must name so it plays the dive: the renamed copy for
    that entity's charge speed, or unchanged. [AIR-DIVE-W12] An entity the
    air dive did not census on a renamed table is a refusal (add it to
    GENERATED_RIDERS and rerun pipelines/air_dive.py)."""
    import anim_table_rename
    return anim_table_rename.repoint(man_animation, table_renames()[1], entity)


# [AIR-DIVE-W15 2026-11-11] User: "允许所有喷吐类技能在接战时释放" -- every
# breath ability castable in melee. The lever is CA's own
# special_ability_to_invalid_usage_flags (703 installed rows): an ability
# with flag ``engaged_in_melee`` ("Engaged in melee", assembly kit
# special_ability_invalid_usage_flags.xml) cannot be used in melee, and with
# ``grounded`` ("Grounded", alt text "Flying") only while flying -- 13 of the
# 18 melee-blocked projectile breaths carry both, and a flyer fighting ground
# troops is grounded, so both rows go. Measured on the installed 9.0 tables:
# 71 breath abilities by the rule below, 20 of them melee-blocked (2 vortex
# breaths of the Blue Fire of Chaos, 18 projectile breaths); CA's own
# wh3_dlc24 Ice Breath and wh3_dlc27 Flaming Breath already carry neither row.
# A breath ability, from data only (no hand list):
#   * unit_abilities.type == "wh_type_breath" (CA's breath ability type, the
#     cone vortices: Wind Blast, Pestilent Breath, Blue Fire ...), or
#   * it emits (unit_special_abilities.activated_projectile / .vortex) a
#     projectile or vortex whose key, or the projectile's projectile_display,
#     names a breath (dragon, hydra, terrorgheist, frost wyrm, bale taurus ...;
#     the Coruscating Blast / Dark Fire / Death Shriek fire
#     *_dragon_breath projectiles), or
#   * it emits something and its English on-screen name (CA's
#     unit_abilities__.loc) says "Breath" (the Breath of the Hydra quest
#     vortex, whose keys do not).
# A donor or generated ability (its text is ours, not CA's) that the rule
# misses is a build failure (:func:`breath_misses`) when it emits something
# and carries an icon CA uses only on breaths (Ushoran's breath reuses the
# Death Shriek icon).
BREATH_TYPE = "wh_type_breath"
BREATH_TOKEN = "breath"
BREATH_BLOCK_FLAGS = ("engaged_in_melee", "grounded")
USAGE_FLAGS_TABLE = "special_ability_to_invalid_usage_flags_tables"


def _names_breath(text):
    return bool(text) and BREATH_TOKEN in str(text).lower()


def breath_abilities(unit_abilities, special_abilities, projectiles, names=None):
    """``{ability key: reason}`` over the given rows (lists of dicts keyed by
    the RPFM column names: unit_abilities ``key``/``type``,
    unit_special_abilities ``key``/``activated_projectile``/``vortex``,
    projectiles ``key``/``projectile_display``); ``names`` maps an ability
    key to its English on-screen name where CA's text is read. A projectile
    an ability names but no row carries is a refusal."""
    types = {r["key"]: r.get("type") for r in unit_abilities}
    displays = {r["key"]: r.get("projectile_display") for r in projectiles}
    out = {}
    for key, kind in types.items():
        if kind == BREATH_TYPE:
            out[key] = "type " + BREATH_TYPE
    for r in special_abilities:
        key, proj, vortex = r["key"], r.get("activated_projectile"), r.get("vortex")
        if key in out or not (proj or vortex):
            continue
        if proj and proj not in displays:
            raise RuntimeError(f"[air_dive_rules] REFUSING: {key} fires projectile "
                               f"{proj!r} that no projectiles row carries")
        if proj and (_names_breath(proj) or _names_breath(displays[proj])):
            out[key] = f"projectile {proj} (display {displays[proj]})"
        elif _names_breath(vortex):
            out[key] = f"vortex {vortex}"
        elif _names_breath((names or {}).get(key)):
            out[key] = f"on-screen name {names[key]!r}"
    return out


def breath_icons(unit_abilities, breath):
    """Icons that mark a breath in CA's data: used by at least one breath
    ability of ``unit_abilities`` (the installed rows) and by none of its
    other abilities (Bangstick's icon is also the Godkiller pistol's, so it
    marks nothing)."""
    by_icon = {}
    for r in unit_abilities:
        if r.get("icon_name"):
            by_icon.setdefault(r["icon_name"], set()).add(r["key"] in breath)
    return {icon for icon, kinds in by_icon.items() if kinds == {True}}


def breath_misses(breath, unit_abilities, special_abilities, marker_icons):
    """``{key: why}``: abilities of these rows (donor or generated, whose text
    is not CA's) that emit something and carry a breath-only icon
    (:func:`breath_icons` over the installed rows) but are not in
    ``breath``. ADAPTER INPUT: the Lore Disasters build refused a non-empty
    answer for its donor and generated abilities; this pack ships only
    installed abilities, so only tests/test_air_dive_breath.py calls it."""
    emits = {r["key"] for r in special_abilities
             if r.get("activated_projectile") or r.get("vortex")}
    icons = {r["key"]: r.get("icon_name") for r in unit_abilities}
    return {key: f"icon {icons[key]} marks a breath"
            for key in sorted(emits - set(breath)) if icons.get(key) in marker_icons}


def breath_usage_rows(rows, breath, flags=BREATH_BLOCK_FLAGS):
    """``(kept, removed)``: the usage-flag junction rows without those that
    block a breath ability with one of ``flags``."""
    kept, removed = [], []
    for r in rows:
        if r["special_ability"] in breath and r["invalid_usage_flag"] in flags:
            removed.append(r)
        else:
            kept.append(r)
    return kept, removed


def rewrite_vendored_usage_flags_tsv(text, breath, flags=BREATH_BLOCK_FLAGS):
    """``(text, rows removed)``: :func:`breath_usage_rows` on one staged
    ``special_ability_to_invalid_usage_flags_tables`` TSV (column names,
    ``#table;version`` marker, one row per line). ADAPTER INPUT: the Lore
    Disasters build applied it to its donor TSVs in memory (the staged TSV
    stayed donor-faithful); here only tests/test_air_dive_breath.py calls it."""
    lines = text.split("\n")
    header = lines[0].rstrip("\r").split("\t")
    fi, ai = header.index("invalid_usage_flag"), header.index("special_ability")
    out, removed = lines[:2], 0
    for line in lines[2:]:
        cells = line.rstrip("\r").split("\t")
        if line.strip() and cells[ai] in breath and cells[fi] in flags:
            removed += 1
            continue
        out.append(line)
    return ("\n".join(out) if removed else text), removed


def installed_breath_sources(db_pack, tag="air_dive_breath"):
    """``(unit_abilities, unit_special_abilities, projectiles, usage rows,
    usage header)`` from the installed db.pack, every table round-tripped
    through our writer schema (installed_db_table: fail-closed)."""
    import flyer_db as installed_db_table   # [FLYER-FIX-1117] self-contained build
    got = {}
    for table in ("unit_abilities_tables", "unit_special_abilities_tables",
                  "projectiles_tables", USAGE_FLAGS_TABLE):
        got[table] = installed_db_table.decode_round_trip(db_pack, table, tag)
    return (got["unit_abilities_tables"][0], got["unit_special_abilities_tables"][0],
            got["projectiles_tables"][0], got[USAGE_FLAGS_TABLE][0],
            got[USAGE_FLAGS_TABLE][1])


def installed_ability_names(local_en_pack):
    """``{ability key: English on-screen name}`` from CA's
    text/db/unit_abilities__.loc in ``local_en_pack`` (fail-closed: the
    file must be there exactly once)."""
    from packfile import PackFile, decode_loc_rows
    pack = PackFile.open(str(local_en_pack))
    hits = [e for e in pack.entries
            if e.path.replace("\\", "/").lower() == "text/db/unit_abilities__.loc"]
    if len(hits) != 1:
        raise RuntimeError(f"[air_dive_rules] REFUSING: {local_en_pack} carries "
                           f"{len(hits)} unit_abilities__.loc")
    prefix = "unit_abilities_onscreen_name_"
    return {k[len(prefix):]: v for k, v, *_ in decode_loc_rows(
        pack.read_file(hits[0]), hits[0].path) if k.startswith(prefix)}


def installed_breath_table(db_pack, local_en_pack, flags=BREATH_BLOCK_FLAGS):
    """The vanilla-path replacement of the usage-flag table: ``(kept rows,
    removed rows, breath {key: reason}, header)``. Refuses when nothing
    would change (the lever went away in a patch: shipping the whole table
    for nothing is a cost)."""
    ua, usa, proj, rows, header = installed_breath_sources(db_pack)
    breath = breath_abilities(ua, usa, proj, installed_ability_names(local_en_pack))
    kept, removed = breath_usage_rows(rows, breath, flags)
    if not removed:
        raise RuntimeError("[air_dive_rules] REFUSING: no installed breath ability "
                           "is blocked in melee any more; re-measure before shipping "
                           "the usage-flag table")
    return kept, removed, breath, header


USAGE_FLAGS_FRAGMENT = "data__"   # the vanilla path: a junction row cannot be deleted by key


def breath_usage_writer(db_pack, local_en_pack, flags=BREATH_BLOCK_FLAGS):
    """``(writer, removed rows, breath)``: the vanilla-path replacement of the
    usage-flag table (:func:`installed_breath_table`) as a DBTableWriter under
    the installed fragment's GUID; flyer_dive_takeoff.pack ships it at
    ``db/<USAGE_FLAGS_TABLE>/<USAGE_FLAGS_FRAGMENT>`` (one pack again since
    2026-11-18, D10)."""
    import flyer_db as db_writer   # [FLYER-FIX-1117] self-contained build
    kept, removed, breath, header = installed_breath_table(db_pack, local_en_pack, flags)
    schema = dict(db_writer.SCHEMAS[USAGE_FLAGS_TABLE])
    schema["guid"] = header["guid"]
    writer = db_writer.DBTableWriter(USAGE_FLAGS_TABLE, schema=schema)
    for row in kept:
        writer.add_row(row)
    return writer, removed, breath


# [D10, owner ruling 2026-11-18] Whether breath may be used while engaged in melee is a setting of the Mod
# Configuration Tool (MCT, Workshop 2927955021). The table above still ships unlocked (that IS the "on" state,
# so a player without MCT, or without memreader Plus, keeps what the published version does). When the setting
# is OFF the battle script script/battle/mod/flyer_breath.lua puts CA's two locks back by hand: every
# BREATH_SWITCH_POLL_MS it disables (unit:disable_special_ability, CA's battle_unit API) each removed ability on
# a unit that is in melee (row engaged_in_melee; unit:is_in_melee) or not flying (row grounded;
# unit:is_currently_flying) and enables it again when neither holds. Only the rows the table dropped are put
# back, per ability (:func:`breath_switch_lua`). A multiplayer campaign battle reads the setting too: MCT hands
# every player the host's settings. A multiplayer battle outside a campaign stays on: MCT shares nothing there,
# so the players' values can differ (docs/DECISIONS.md D14).
BREATH_SWITCH_DEFAULT_ON = True        # the published behaviour (maintainer's choice under D10)
BREATH_SWITCH_POLL_MS = 100            # one battle tick (10 a second)
BREATH_SWITCH_MCT_MOD = "flyer_dive_takeoff"
BREATH_SWITCH_MCT_OPTION = "breath_while_engaged"
BREATH_SWITCH_LUA_PATH = "script/campaign/flyer_dive/data/breath_rows.lua"
BREATH_SWITCH_LOCKS = {"engaged_in_melee": "in_melee", "grounded": "not_flying"}


def breath_switch_lua(removed):
    """The generated Lua data module the breath switch reads: the rules' constants and, per breath ability
    the shipped table unlocks, the locks the OFF setting puts back (``removed`` = the rows
    :func:`breath_usage_writer` dropped). Sorted, so the bytes depend on the rows only. A flag with no lock is
    a refusal."""
    locks = {}
    for r in removed:
        flag = r["invalid_usage_flag"]
        if flag not in BREATH_SWITCH_LOCKS:
            raise RuntimeError(f"[air_dive_rules] REFUSING: removed usage flag {flag!r} has no breath lock")
        locks.setdefault(r["special_ability"], set()).add(BREATH_SWITCH_LOCKS[flag])
    if not locks:
        raise RuntimeError("[air_dive_rules] REFUSING: no breath ability to switch")
    lines = ["-- generated by build_air_dive_minimod.py from air_dive_rules (D10); do not edit",
             "return {",
             f"    default_on = {str(BREATH_SWITCH_DEFAULT_ON).lower()},",
             f"    poll_ms = {BREATH_SWITCH_POLL_MS},",
             f'    mct_mod = "{BREATH_SWITCH_MCT_MOD}",',
             f'    mct_option = "{BREATH_SWITCH_MCT_OPTION}",',
             "    abilities = {"]
    for key in sorted(locks):
        flags = ", ".join(f'"{lock}"' for lock in sorted(locks[key]))
        lines.append(f'        ["{key}"] = {{ {flags} }},')
    lines += ["    },", "}", ""]
    return "\n".join(lines).encode("utf-8")


def tsv_dicts(text):
    """Rows of one staged TSV text (column names, ``#`` marker, rows) as
    dicts of strings; empty cells are ''."""
    lines = text.splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"))) for line in lines[2:] if line.strip()]


# [AIR-DIVE-W16 2026-11-12] THE IMPACT. ENGINE-W1 (static read of the 9.0.5
# exe, air-dive-engine-w1_scratch/air_dive_engine.md) found why a landing
# flyer pushes men over but hardly hurts them: the engine's own collision
# attack (a native melee roll on every enemy the attacker runs into while
# moving >= 1 m/s on an attack/charge order) is capped per weapon by
# ``melee_weapons.collision_attack_max_targets``, and 1,117 of CA's 1,280
# melee weapons -- every dragon, griffon, pegasus, wyvern -- carry 0. CA's
# non-zero rows are chariots, sphinxes, abominations, the dread abyssal
# terror: the precedents. Three data levers, measured one on top of the
# other in game (§C11 AIR-DIVE-W16), stage by stage:
#   "A" none (the W1-W15 dive);
#   "B" collision attack on every flyer's melee weapon (:func:`collision_attack`);
#   "C" B + the flyer entity pushes men over more easily
#       (``battle_entities.dealt_collision_knocked_*_threshold_multiplier``
#       x KNOCK_FACTOR by body size, in :func:`tuned_cells`);
#   "D" C + a hidden passive, on only while charging (CA's
#       ``unit_is_not_charging`` auto-deactivate flag, template
#       CHARGE_PASSIVE_TEMPLATE), that makes the flyer heavier and its push
#       stronger (CHARGE_PASSIVE_STATS).
# IMPACT_STAGE is the stage every emitter ships; build_air_dive_minimod
# --impact-stage builds the others for the comparison.
IMPACT_STAGES = ("A", "B", "C", "D")
# [AIR-DIVE-W16] measured (§C11 AIR-DIVE-W16, two runs per stage, level lanes):
# B is what ships. The collision attack fires for every flyer tried, the
# cavalry-class pegasus knights included, and lifts the light and multi-model
# flyers (manticore 1.5 s loss 2.1% -> 5.0%, griffon knights 5 s 8.8% ->
# 14.9%, pegasus knights 5 s 3.0% -> 9.1%) while the star dragon, already
# at 12-13% from the plough, stays there. C measured no change over B (knocks
# and losses within run-to-run noise). D roughly doubled the pegasus knights
# again (5 s 13.6%) through a stat the player cannot see, at an unchanged
# price -- left for a user ruling, not shipped.
# [D59 2026-11-21] owner: flyers carry NO collision attack (that is the chariot / anti-infantry monster
# damage); their damage is the engine's mass x speed impact only. B is withdrawn; A ships.
IMPACT_STAGE = "A"
# [D15, d15-1118] Braced-spear cost of a dive. D4's "twice the game's own reflection damage" (the
# removed REFLECTION_FLYER_DAMAGE_FACTOR) is replaced by D15: once per model per dive, at the dive's
# contact with a bracing charge_reflection soldier, a share of the model's own maximum health.
# [stage 5] SHIPPED: pipelines/dive_cost_asm.py generates the shipped dive site table with these numbers
# (the dv_cost cave judges the contact, script/campaign/flyer_dive/lib/dive_cost.lua takes the share
# through unit:reduce_hitpoints_unary); the probe (reflect_probe_*) only records it.
# DIVE_COST_WINDOW_TICKS: battle ticks (10 a second) after the touchdown in which a contact counts.
# First guess from series 4 run 3: every flyer's impact and collision damage on the braced line fell
# within 3 s of the first driver sample on the ground (d15-1118 lane, impact_at_dive.py).
DIVE_COST_WINDOW_TICKS = 30
# DIVE_COST_SHARE: share of the model's own maximum health per paying model, by body size. 3% for every
# size: measured under the standard setup and accepted by the owner on 2026-11-19 (docs/DECISIONS.md
# D15, docs/HISTORY.md D15-STD-1119); kept per size so that a later measurement can set them apart.
# [D25 / D31, brace-solver-1120] The owner's 10% (D25: 「提到 10%」) is the default, the same for every size; an
# MCT slider over DIVE_COST_PERCENT_RANGE (whole percent) replaces it for every size, 0 takes no cost
# (script/campaign/flyer_dive/lib/brace_rule.lua). This table is what a battle without MCT uses.
DIVE_COST_PERCENT_DEFAULT = 10
DIVE_COST_PERCENT_RANGE = (0, 25)
DIVE_COST_SHARE = {s: DIVE_COST_PERCENT_DEFAULT / 100 for s in ("small", "medium", "large", "very_large")}
# [d15-1118, maintainer] The probe applies the cost through the game's own battle-script call
# unit:reduce_hitpoints_unary(p, false) (CA: lib_battle_script_unit.lua kill_proportion), once per flyer
# unit per recorder tick, p = the paying models' shares summed / unit:initial_number_of_men() (CA's doc of
# kill_proportion: the proportion is of "the unit's starting number of soldiers"). Only with cost=1 in the
# autotest command file. A call is refused (logged, not made) for p <= 0 or p > DIVE_COST_MAX_CALL, and p is
# capped so the unit keeps DIVE_COST_KEEP_UNARY of its health: whether the call can kill the last model is
# not readable statically (its command executor was not found), so a dive cost never takes the last
# DIVE_COST_KEEP_UNARY -- a floor (set as the size of one 3% cost; with the 10% default a cost that would go
# below it is cut to leave it).
DIVE_COST_MAX_CALL = 0.5
DIVE_COST_KEEP_UNARY = 0.03
# Recorder ticks (100 ms each) the unit's health is read after a call. The call only queues a command
# (0x142ea4778); a single-player battle runs one simulation tick per 100 ms, so the effect is expected on the
# next reading. Five readings allow for a queue delay of several ticks; no drop within them is the report's
# "command not executed" FAIL (e.g. the two flags at 0x142f0f633 / 0x142f0f63c that skip the submit).
DIVE_COST_FOLLOW_TICKS = 5
# [stage 5] Only a contact in front of the bracing soldier pays: the flyer's position lies within the game's
# own bracing_attack_angle (kv rule, 80 in 9.0.5) of the soldier's facing, the test the game makes in its
# contact engage 0x14307c404 (0x14307c556..0x14307c63c: cos(angle x pi/180) against the facing +0xb0 and the
# vector to the other entity). The bracing flag itself (+0x68 bit 3, set at 0x143090af0) does not depend on
# where the charger comes from, and the damage calculator's doubling does not test the angle; so this is the
# maintainer's reading of the owner's "only while standing braced", switchable here. The angle value is read
# from the installed game's data when the site table is generated, never written here.
DIVE_COST_FRONT_ARC = True
# [D25 / D29 / D31, brace-solver-1120] A braced line against a dive, inside the engine's own pair solver
# 0x14317768c (docs/HISTORY.md PAIR-SOLVER-1120, PAIR-PROBE-1120; cave dv_brace, pipelines/dive_brace_asm.py).
# Where the engine counts a body's brace (it multiplies that body's mass by its brace multiplier) and the other
# body is a flyer in a landed dive, the braced mass is multiplied again by BRACE_MASS_K and the flyer's size-tier
# share of the velocity correction is raised to at least BRACE_SHARE_MIN.
# The solver (lane read; the numbers re-read in game by PAIR-PROBE-1120): per contact with a resting soldier the
# flyer keeps 1 - F of its momentum, F = s * (1 + e) * M' / (m + M'); s the flyer's share (0.8 / 0.2 / 0.1 / 0 for
# size-tier gaps 1-4), e the restitution 0.3 (read in game), m the flyer's mass, M' = soldier mass x brace (x k).
# Target (owner's brief through the supervisor): a star dragon (m 4425, gap 3) against Empire spearmen braced at
# 5.43 (M' = 100 x 5.43 = 543) gets the braking the pegasus knights (m 1300, gap 1, s 0.8) get today:
#   pegasus today: 0.8 x 1.3 x 543 / (1300 + 543)  = 0.306   (the lane's "24.5% per contact" is this x 0.8)
#   dragon today:  0.1 x 1.3 x 543 / (4425 + 543)  = 0.0142  (x 0.8: 1.1%)
#   s* = 0.8, the engine's own share one tier apart; then F_dragon = F_pegasus when k x 543 / 4425 = 543 / 1300,
#   k = 4425 / 1300 = 3.40 -> dragon 0.8 x 1.3 x 1846 / (4425 + 1846) = 0.306 (x 0.8: 24.5%).
#   The same defaults, other flyers against that soldier: pegasus 0.306 -> 0.610, manticore (1700, gap 2)
#   0.063 -> 0.541, griffon knights (1725, gap 3) 0.031 -> 0.538. (That was D31's first default, k 3.4 / s* 0.8.)
# [D32 / D33, release-1120] Measured in game, k 3.4 / s* 0.8 stopped a manticore in 0.2 s (docs/HISTORY.md
# BRACE-AB-1120); the owner asked for one step lighter (D32) and the shipped defaults are k 2.0, s* 0.5, cost 10%
# (D33; measured twice, BRACE-LIGHT-1120: manticore 2-3 m, star dragon 6-13 m into the line before it stops).
# With M' = 543 x 2.0 = 1086 and the share max(s, 0.5):
#   dragon          0.5 x 1.3 x 1086 / (4425 + 1086) = 0.128   (today 0.0142)
#   pegasus         0.8 x 1.3 x 1086 / (1300 + 1086) = 0.473   (today 0.306; its own share 0.8 is above s*)
#   manticore       0.5 x 1.3 x 1086 / (1700 + 1086) = 0.253   (today 0.063)
#   griffon knights 0.5 x 1.3 x 1086 / (1725 + 1086) = 0.251   (today 0.031)
# The dragon no longer matches the pegasus; a big flyer goes a few metres into the line instead of stopping dead.
# The cave reads both from one u32 the battle script writes (brace_word: k in hundredths in the low 16 bits, s* in
# hundredths in bits 16-23; 0 = off), so a game Lua number (float32) never carries float bits; every value of
# the word stays below 2^24, exact in a float32.
BRACE_LINE_DEFAULT_ON = True
BRACE_MASS_K = 2.0
BRACE_MASS_K_RANGE = (1.0, 10.0)        # MCT slider; 1.0 = the engine's own braced mass
BRACE_MASS_K_STEP = 0.1
BRACE_SHARE_MIN = 0.5
BRACE_SHARE_MIN_RANGE = (0.0, 1.0)      # MCT slider; 0 = the engine's own share
BRACE_SHARE_MIN_STEP = 0.05
BRACE_WORD_SCALE = 100                  # hundredths
# MCT option keys, in the breath switch's MCT mod (BREATH_SWITCH_MCT_MOD) and its one section
# [D51] "reflect" replaces D15's "cost" (a new key: a saved cost percentage is never read as a factor)
BRACE_MCT_OPTIONS = {"on": "braced_line_on", "k": "braced_line_mass", "share": "braced_line_share",
                     "reflect": "braced_line_reflect"}


def brace_word(k, share):
    """The u32 the battle script writes for dv_brace when the switch is on; refuses values outside the sliders'
    ranges (lib/brace_rule.lua computes the same word in game)."""
    if not (BRACE_MASS_K_RANGE[0] <= k <= BRACE_MASS_K_RANGE[1]
            and BRACE_SHARE_MIN_RANGE[0] <= share <= BRACE_SHARE_MIN_RANGE[1]):
        raise ValueError(f"[air_dive_rules] REFUSING: brace k {k!r} / share {share!r} outside the sliders' ranges")
    return int(k * BRACE_WORD_SCALE + 0.5) | (int(share * BRACE_WORD_SCALE + 0.5) << 16)
# [D51] Charge Reflection on flyers (cave dv_reflect, pipelines/dive_reflect_asm.py; replaces D15's dive cost):
# at the engine's own reflection multiply (0x142e600af, damage factor x kv charge_reflect_damage_multiplier 2.0)
# the factor is multiplied once more by REFLECT_FLYER_FACTOR when the charger being hit is, or rides, a flyer.
# 1.0 = the base game. The battle script writes it as a u32 in hundredths (reflect_word; 0 = off), exact in a
# float32. MCT slider over REFLECT_FLYER_FACTOR_RANGE in steps of REFLECT_FLYER_FACTOR_STEP, under the braced-line
# master switch (off = the base game).
REFLECT_FLYER_FACTOR = 2.0
REFLECT_FLYER_FACTOR_RANGE = (1.0, 4.0)
REFLECT_FLYER_FACTOR_STEP = 0.25


def reflect_word(factor):
    """The u32 the battle script writes for dv_reflect when the switch is on; refuses values outside the slider's
    range (lib/brace_rule.lua computes the same word in game)."""
    if not REFLECT_FLYER_FACTOR_RANGE[0] <= factor <= REFLECT_FLYER_FACTOR_RANGE[1]:
        raise ValueError(f"[air_dive_rules] REFUSING: reflection factor {factor!r} outside the slider's range")
    return int(factor * BRACE_WORD_SCALE + 0.5)


# [D56 / D57] The SFO submod (pipelines/build_sfo_submod.py) runs the entity rule on SFO's rows with these
# columns left as SFO has them: SFO's own flyer tuning stays (owner, 2026-11-21: "Keep SFO's numbers").
SFO_KEEP_ENTITY_COLUMNS = ("mass", "flying_charge_speed")
# The tables whose SFO rows are laid over the installed ones for that build, and the only ones it ships.
SFO_TABLES = ("land_units_tables", "battle_entities_tables", "mounts_tables", "melee_weapons_tables")


COLLISION_ATTACK_TABLE = "melee_weapons_tables"
# a flyer weapon CA also gives to a non-flyer is cloned under this suffix
# and the flyer's land unit repointed (the ground unit keeps CA's weapon)
WEAPON_CLONE_SUFFIX = "_dive"
ANCHOR_MASS_RATIO = 1.5      # anchors within x1.5 of the flyer's mass ...
ANCHOR_MIN = 3               # ... at least this many, else every same-size row
# the push: dealt-collision knock thresholds x this (lower = men fall at a
# slower push). CA's own lowered rows: rollers / skullcrackers / mechanical
# steed 0.2 (down) 0.22 (back), the rogue idol 0.15; every flyer is 1.0
# (5 small ones 1.4 and two large ones 4.0 on flying). Scaled by body size
# so a pegasus does not bowl men over like a dragon.
KNOCK_FACTOR = {"small": 1.0, "medium": 0.9, "large": 0.8, "very_large": 0.6}
KNOCK_FIELDS = ("dealt_collision_knocked_flying_threshold_multiplier",
                "dealt_collision_knocked_down_threshold_multiplier",
                "dealt_collision_knocked_back_threshold_multiplier")
# the charge passive (stage D): CA's always-on-while-charging passive
CHARGE_PASSIVE_TEMPLATE = "wh3_dlc24_unit_passive_bears_bulwark"
CHARGE_PASSIVE_KEY = "flyer_dive_charge_impact"
CHARGE_PASSIVE_UID = 991797001
CHARGE_PASSIVE_FLAG = "unit_is_not_charging"
# stat_mass x1.5: CA's own charge passives (murderous charge, momentum) use
# 1.5; the knock modifiers x0.7 (CA's pump-harder wagon goes to 0.02).
CHARGE_PASSIVE_STATS = (
    ("stat_mass", 1.5, "mult"),
    ("scalar_dealt_collision_knocked_flying_threshold_modifier", 0.7, "mult"),
    ("scalar_dealt_collision_knocked_down_threshold_modifier", 0.7, "mult"),
    ("scalar_dealt_collision_knocked_back_threshold_modifier", 0.7, "mult"),
)


def stage_at_least(want, stage=None):
    """True when ``stage`` (default IMPACT_STAGE) includes stage ``want``."""
    stage = IMPACT_STAGE if stage is None else stage
    if stage not in IMPACT_STAGES or want not in IMPACT_STAGES:
        raise RuntimeError(f"[air_dive_rules] REFUSING: impact stage {stage!r}/{want!r} "
                           f"not one of {IMPACT_STAGES}")
    return IMPACT_STAGES.index(stage) >= IMPACT_STAGES.index(want)


def knock_cells(row, declared=(), stage=None):
    """[AIR-DIVE-W16] ``{field: value}`` lowering a flyer entity's dealt-
    collision knock thresholds (stage C and up); ``{}`` otherwise."""
    if not is_flyer(row) or not stage_at_least("C", stage):
        return {}
    size = row["size"]
    if size not in KNOCK_FACTOR:
        raise RuntimeError(f"[air_dive_rules] REFUSING: {row['key']}: body size "
                           f"{size!r} has no KNOCK_FACTOR")
    out = {}
    for field in KNOCK_FIELDS:
        if field in declared:
            continue
        value = round(float(row[field]) * KNOCK_FACTOR[size], 3)
        if value != float(row[field]):
            out[field] = value
    return out


def body_entity(unit, mounts, entities):
    """The battle entity that flies for one land unit row: its mount's entity
    when it rides one, else its man_entity (None when unknown)."""
    mount = unit.get("mount")
    if mount:
        m = mounts.get(mount)
        return entities.get(m["entity"]) if m else None
    return entities.get(unit.get("man_entity"))


def flyer_units(land_units, mounts, entities):
    """``{land unit key: its flying body entity row}`` -- every land unit
    whose body :func:`is_flyer` (data, never a hand list)."""
    out = {}
    for u in land_units:
        e = body_entity(u, mounts, entities)
        if e is not None and is_flyer(e):
            out[u["key"]] = e
    return out


def _by_key(rows):
    return rows if isinstance(rows, dict) else {r["key"]: r for r in rows}


def collision_anchors(land_units, mounts, entities, weapons):
    """CA's non-zero collision attacks: ``[(size, mass, targets, cooldown)]``,
    one per (weapon, body) pair a land unit carries."""
    by_key = _by_key(weapons)
    seen = set()
    for u in land_units:
        w = by_key.get(u["primary_melee_weapon"])
        e = body_entity(u, mounts, entities)
        if w is None or e is None or int(w["collision_attack_max_targets"]) <= 0:
            continue
        seen.add((w["key"], e["key"], e["size"], float(e["mass"]),
                  int(w["collision_attack_max_targets"]),
                  float(w["collision_attack_max_targets_cooldown"])))
    out = [(s, m, t, c) for _w, _e, s, m, t, c in sorted(seen)]
    if not out:
        raise RuntimeError("[air_dive_rules] REFUSING: the installed game has no "
                           "non-zero collision_attack_max_targets left to anchor on")
    return out


def _median_up(values):
    """Median, a half rounded up."""
    import math
    v = sorted(values)
    n = len(v)
    mid = v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0
    return int(math.floor(mid + 0.5))


def collision_attack(size, mass, anchors):
    """``(collision_attack_max_targets, _cooldown)`` for a flyer body: the
    median of CA's rows of the same body size whose mass is within
    ANCHOR_MASS_RATIO of it (every same-size row when fewer than ANCHOR_MIN),
    half rounded up. A size CA never anchors is a refusal."""
    same = [a for a in anchors if a[0] == size]
    if not same:
        raise RuntimeError(f"[air_dive_rules] REFUSING: no CA collision-attack "
                           f"anchor of body size {size!r}")
    mass = float(mass)
    near = [a for a in same
            if mass / ANCHOR_MASS_RATIO <= a[1] <= mass * ANCHOR_MASS_RATIO]
    use = near if len(near) >= ANCHOR_MIN else same
    return _median_up(a[2] for a in use), _median_up(a[3] for a in use)


def flyer_weapon_plan(land_units, mounts, entities, weapons, stage=None,
                      anchors=None, mass_of=None):
    """[AIR-DIVE-W16] The collision attack of every flyer (stage B and up).

    ``land_units`` may mix installed rows with our own and donor rows (each a
    dict with key / primary_melee_weapon / man_entity / mount), ``mounts``
    and ``entities`` {key: row}, ``weapons`` installed + shipped weapon rows.
    ``anchors`` default: CA's own rows among the given ones.
    ``mass_of`` (row -> mass) default the row's own mass: the mass the collision
    attack is sized on [AIR-DIVE-BRACE-W1: the uncut mass].
    Returns ``(cells, clones, repoint)``:
      * ``cells`` {weapon key: {field: value}} -- weapons only flyers carry,
        changed in place;
      * ``clones`` {new weapon key: (source weapon key, {field: value})} --
        a weapon also carried by a ground unit is copied, so the ground unit
        keeps its weapon;
      * ``repoint`` {land unit key: new weapon key} -- every flyer land unit
        on a cloned weapon (its emitter must name the clone).
    A weapon whose flyers want different values gets the largest (a weapon
    has one row); a weapon that already has a collision attack keeps it.
    """
    if not stage_at_least("B", stage):
        return {}, {}, {}
    by_key = _by_key(weapons)
    if anchors is None:
        anchors = collision_anchors(land_units, mounts, entities, by_key)
    flyers = flyer_units(land_units, mounts, entities)
    users = {}
    for u in land_units:
        users.setdefault(u["primary_melee_weapon"], set()).add(u["key"])
    want = {}
    for u in land_units:
        if u["key"] not in flyers:
            continue
        wk = u["primary_melee_weapon"]
        if wk not in by_key:
            raise RuntimeError(f"[air_dive_rules] REFUSING: flyer {u['key']} names "
                               f"melee weapon {wk!r}, which nothing ships")
        e = flyers[u["key"]]
        t, c = collision_attack(e["size"], mass_of(e) if mass_of else e["mass"], anchors)
        old = want.get(wk)
        want[wk] = (t, c) if old is None else max(old, (t, c))
    cells, clones, repoint = {}, {}, {}
    for wk, (t, c) in sorted(want.items()):
        if int(by_key[wk]["collision_attack_max_targets"]) > 0:
            continue
        new = {"collision_attack_max_targets": t,
               "collision_attack_max_targets_cooldown": float(c)}
        if users[wk] <= set(flyers):
            cells[wk] = new
        else:
            ck = wk + WEAPON_CLONE_SUFFIX
            if ck in by_key:
                raise RuntimeError(f"[air_dive_rules] REFUSING: {ck!r} already exists")
            clones[ck] = (wk, new)
            for k in sorted(users[wk]):
                if k in flyers:
                    repoint[k] = ck
    return cells, clones, repoint


def charge_passive_units(land_units, mounts, entities, stage=None):
    """[AIR-DIVE-W16] land units that get CHARGE_PASSIVE_KEY (stage D)."""
    if not stage_at_least("D", stage):
        return []
    return sorted(flyer_units(land_units, mounts, entities))


CHARGE_PASSIVE_TABLES = (
    "unit_abilities_tables", "unit_special_abilities_tables",
    "special_ability_to_special_ability_phase_junctions_tables",
    "special_ability_phases_tables", "special_ability_phase_stat_effects_tables",
    "special_ability_to_auto_deactivate_flags_tables",
    "land_units_to_unit_abilites_junctions_tables",
)


def _one(rows, replay, field, value, table):
    hits = [(dict(r), dict(x or {})) for r, x in zip(rows, replay) if r[field] == value]
    if len(hits) != 1:
        raise RuntimeError(f"[air_dive_rules] REFUSING: {value!r}: {len(hits)} rows "
                           f"in installed {table}, expected exactly 1")
    return hits[0]


def _with(src, cells, table):
    row, raw = dict(src[0]), dict(src[1] or {})
    for field, value in cells.items():
        if field not in row:
            raise RuntimeError(f"[air_dive_rules] {table} has no column {field}")
        row[field] = value
        raw.pop(field, None)
    return row, raw


def charge_passive_rows(db_pack, land_unit_keys, tag="air_dive_impact"):
    """[AIR-DIVE-W16] ``{table: [(row, raw)]}`` of the hidden charge passive
    (CHARGE_PASSIVE_KEY), cloned from CHARGE_PASSIVE_TEMPLATE's installed
    rows, and one ability junction row per land unit in ``land_unit_keys``."""
    # [FLYER-FIX-1117] self-contained build: the stat-effects schema dbw_resist registered in the main mod
    # is not recorded (no shipped stage reads it), so stage D is refused by flyer_db until it is
    import flyer_db as idb
    got = {t: idb.decode_round_trip_with_replay(db_pack, t, tag)
           for t in CHARGE_PASSIVE_TABLES}
    tk = CHARGE_PASSIVE_TEMPLATE
    us_rows = got["unit_special_abilities_tables"][0]
    if any(int(r["unique_id"]) == CHARGE_PASSIVE_UID for r in us_rows):
        raise RuntimeError(f"[air_dive_rules] REFUSING: unique_id {CHARGE_PASSIVE_UID} installed")
    for t, f in (("unit_abilities_tables", "key"), ("unit_special_abilities_tables", "key")):
        if any(r[f] == CHARGE_PASSIVE_KEY for r in got[t][0]):
            raise RuntimeError(f"[air_dive_rules] REFUSING: {CHARGE_PASSIVE_KEY} installed in {t}")
    flags = [r for r in got["special_ability_to_auto_deactivate_flags_tables"][0]
             if r["special_ability"] == tk]
    if [r["deactivate_flag"] for r in flags] != [CHARGE_PASSIVE_FLAG]:
        raise RuntimeError(f"[air_dive_rules] REFUSING: template {tk} is no longer "
                           f"'off unless charging' ({flags})")
    pj_t = "special_ability_to_special_ability_phase_junctions_tables"
    pj = _one(got[pj_t][0], got[pj_t][2], "special_ability", tk, pj_t)
    ph = _one(got["special_ability_phases_tables"][0], got["special_ability_phases_tables"][2],
              "id", pj[0]["phase"], "special_ability_phases_tables")
    ua = _one(got["unit_abilities_tables"][0], got["unit_abilities_tables"][2], "key", tk,
              "unit_abilities_tables")
    us = _one(us_rows, got["unit_special_abilities_tables"][2], "key", tk,
              "unit_special_abilities_tables")
    if not us[0]["passive"] or float(us[0]["active_time"]) != -1.0:
        raise RuntimeError(f"[air_dive_rules] REFUSING: template {tk} is no longer an "
                           "always-on passive")
    key = CHARGE_PASSIVE_KEY
    out = {
        "unit_abilities_tables": [_with(ua, {
            "key": key, "requires_effect_enabling": False, "is_hidden_in_ui": True,
            "is_hidden_in_ui_for_enemy": True, "is_unit_upgrade": False},
            "unit_abilities_tables")],
        "unit_special_abilities_tables": [_with(us, {
            "key": key, "unique_id": CHARGE_PASSIVE_UID,
            "additional_melee_cp": 0.0, "additional_missile_cp": 0.0},
            "unit_special_abilities_tables")],
        pj_t: [_with(pj, {"special_ability": key, "phase": key}, pj_t)],
        "special_ability_phases_tables": [_with(ph, {
            "id": key, "is_hidden_in_ui": True, "phase_display": None,
            "imbue_contact": None}, "special_ability_phases_tables")],
        "special_ability_phase_stat_effects_tables": [
            ({"phase": key, "stat": stat, "value": value, "how": how}, {})
            for stat, value, how in CHARGE_PASSIVE_STATS],
        "special_ability_to_auto_deactivate_flags_tables": [
            ({"deactivate_flag": CHARGE_PASSIVE_FLAG, "special_ability": key}, {})],
        "land_units_to_unit_abilites_junctions_tables": [
            ({"ability": key, "land_unit": k, "culture": "*"}, {})
            for k in sorted(land_unit_keys)],
    }
    return out


def installed_impact(db_pack, stage=None, tag="air_dive_impact"):
    """[AIR-DIVE-W16] The installed game's impact rows for one stage:
    ``({table: [(row, raw)]}, repoint {land unit: weapon}, report)``.
    melee_weapons: every flyer weapon :func:`flyer_weapon_plan` changes
    (installed row + cells, other cells replayed) and its clones; stage D
    adds :func:`charge_passive_rows` for every installed flyer land unit."""
    import flyer_db as idb
    ent = {r["key"]: r for r in idb.decode_round_trip(db_pack, "battle_entities_tables", tag)[0]}
    mounts = {r["key"]: r for r in idb.decode_round_trip(db_pack, "mounts_tables", tag)[0]}
    land = idb.decode_round_trip(db_pack, "land_units_tables", tag)[0]
    w_rows, _h, w_replay = idb.decode_round_trip_with_replay(db_pack, COLLISION_ATTACK_TABLE, tag)
    cells, clones, repoint = flyer_weapon_plan(land, mounts, ent, w_rows, stage)
    by_key = {r["key"]: (r, x) for r, x in zip(w_rows, w_replay)}
    weapons = [_with(by_key[k], c, COLLISION_ATTACK_TABLE) for k, c in sorted(cells.items())]
    weapons += [_with(by_key[src], dict(c, key=ck), COLLISION_ATTACK_TABLE)
                for ck, (src, c) in sorted(clones.items())]
    out = {COLLISION_ATTACK_TABLE: weapons} if weapons else {}
    passive = charge_passive_units(land, mounts, ent, stage)
    if passive:
        out.update(charge_passive_rows(db_pack, passive, tag))
    report = {"weapons_changed": len(cells), "weapons_cloned": len(clones),
              "land_units_repointed": len(repoint), "charge_passive_units": len(passive)}
    return out, repoint, report


def weapon_repointed_land_rows(land_rows, repoint, db_pack, tag="air_dive_impact",
                               owned=()):
    """[AIR-DIVE-W16] ``land_rows`` [(row, raw)] (the renamed-table land units
    this emitter already ships whole) with ``primary_melee_weapon`` set from
    ``repoint`` {land unit: cloned weapon}, plus the installed row, whole,
    of every repointed land unit not among them. Keys in ``owned`` are shipped
    whole by another emitter, which must repoint them itself through
    ``repoint`` (one row, one owner) -- they are skipped here."""
    import flyer_db as idb
    out, have = [], set()
    for row, raw in land_rows:
        new = repoint.get(row["key"])
        if new is not None:
            row, raw = _with((row, raw), {"primary_melee_weapon": new}, "land_units_tables")
        out.append((row, raw))
        have.add(row["key"])
    missing = sorted(set(repoint) - have - set(owned))
    if missing:
        rows, _h, replay = idb.decode_round_trip_with_replay(db_pack, "land_units_tables", tag)
        by_key = {r["key"]: (r, x) for r, x in zip(rows, replay)}
        for k in missing:
            if k not in by_key:
                raise RuntimeError(f"[air_dive_rules] REFUSING: repointed land unit "
                                   f"{k!r} is not installed")
            out.append(_with(by_key[k], {"primary_melee_weapon": repoint[k]},
                             "land_units_tables"))
    return out


# [AIR-DIVE-W16] ld_mod.pack: the impact over everything the pack ships.
# ADAPTER INPUT: impact_assembly is the Lore Disasters build's final-assembly
# pass; this repository's build applies the impact to installed rows only
# (installed_impact) and does not call it.
# A flyer's weapon and land unit can be shipped by any lane (measured on the
# built ld_mod.pack 2026-11-12: 516 of 519 flyer land units are shipped by us,
# 314 of them whole in ld_resist_both, 117 in flyer_dive_takeoff, the rest by our
# generators and 40 donor closures; 27 of the flyer weapons are donor rows),
# so the rule runs once, at final assembly, over the shipped fragments plus
# the installed game: a changed row is rewritten inside the fragment that
# ships it (one row, one owner); installed rows nobody ships go into
# IMPACT_FRAGMENT. The collision-attack anchors are CA's own rows only.
IMPACT_FRAGMENT = "flyer_dive_impact"
IMPACT_READ_TABLES = ("land_units_tables", "battle_entities_tables",
                      "mounts_tables", COLLISION_ATTACK_TABLE)


def _db_table_of(path):
    parts = path.replace("/", "\\").split("\\")
    if len(parts) == 3 and parts[0].lower() == "db":
        return parts[1]
    return None


def impact_assembly(fragment_lists, db_pack, catalog=None, stage=None,
                    tag="air_dive_impact"):
    """[AIR-DIVE-W16] Apply the impact (IMPACT_STAGE) to the final pack.

    ``fragment_lists``: lists of (pack path, bytes) -- every DB fragment the
    pack ships (generated and donor); rewritten IN PLACE (same paths, same
    keys and row counts). ``catalog`` {logical path: item}: the generated
    catalog, its rows refreshed for a rewritten fragment. Returns
    ``({pack path: writer} of the new IMPACT_FRAGMENT fragments, report)``.
    Fails closed when a flyer land unit the pack fields ends without a
    collision attack, a ground unit ends on a weapon the rule changed, or a
    flyer land unit lacks the charge passive (stage D)."""
    import flyer_db as idb
    import flyer_db as db_writer
    from flyer_db import _decode_db_table_bytes
    from packfile import DBTableReader
    inst = {}
    for t in IMPACT_READ_TABLES:
        rows, _h, replay = idb.decode_round_trip_with_replay(db_pack, t, tag)
        inst[t] = {r["key"]: (r, x) for r, x in zip(rows, replay)}
    anchors = collision_anchors(
        [r for r, _x in inst["land_units_tables"].values()],
        {k: r for k, (r, _x) in inst["mounts_tables"].items()},
        {k: r for k, (r, _x) in inst["battle_entities_tables"].items()},
        {k: r for k, (r, _x) in inst[COLLISION_ATTACK_TABLE].items()})
    shipped = {t: {} for t in IMPACT_READ_TABLES}     # key -> (list, index, row)
    decoded = {}                                      # (list id, index) -> (rows, raw, header)
    for li, entries in enumerate(fragment_lists):
        for i, (path, data) in enumerate(entries):
            table = _db_table_of(path)
            if table not in IMPACT_READ_TABLES:
                continue
            rows, raw = _decode_db_table_bytes(data, table, path, capture_raw=True)
            decoded[(li, i)] = (rows, raw, DBTableReader.parse_binary_header(data))
            for row in rows:
                shipped[table][row["key"]] = (li, i, row)
    merged = {t: {k: r for k, (r, _x) in inst[t].items()} for t in IMPACT_READ_TABLES}
    for t in IMPACT_READ_TABLES:
        merged[t].update({k: v[2] for k, v in shipped[t].items()})
    land = list(merged["land_units_tables"].values())
    mounts, ents = merged["mounts_tables"], merged["battle_entities_tables"]
    weapons = merged[COLLISION_ATTACK_TABLE]
    # [AIR-DIVE-BRACE-W1] sized on the uncut mass: an installed body's own (vanilla) mass, any other
    # body's mass before tuned_cells cut it -- the shipped rows here already carry the cut
    inst_ent = inst["battle_entities_tables"]
    cells, clones, repoint = flyer_weapon_plan(
        land, mounts, ents, weapons, stage, anchors=anchors,
        mass_of=lambda e: float(inst_ent[e["key"]][0]["mass"]) if e["key"] in inst_ent else uncut_mass(e))
    # rewrite shipped rows in their own fragments
    edits = {}                                        # (li, i) -> {key: cells}
    for key, c in cells.items():
        if key in shipped[COLLISION_ATTACK_TABLE]:
            li, i, _r = shipped[COLLISION_ATTACK_TABLE][key]
            edits.setdefault((li, i), {})[key] = c
    for key, new in repoint.items():
        if key in shipped["land_units_tables"]:
            li, i, _r = shipped["land_units_tables"][key]
            edits.setdefault((li, i), {})[key] = {"primary_melee_weapon": new}
    for (li, i), by_key in sorted(edits.items()):
        path, _data = fragment_lists[li][i]
        table = _db_table_of(path)
        rows, raw, header = decoded[(li, i)]
        schema = dict(db_writer.SCHEMAS[table])
        schema["guid"] = header.get("guid")
        w = db_writer.DBTableWriter(table, schema=schema)
        for row, rr in zip(rows, raw):
            c = by_key.get(row["key"])
            if c:
                row, rr = _with((row, rr), c, table)
            w.add_row(row, raw_fields=rr or None)
        fragment_lists[li][i] = (path, w.build())
        logical = path.replace("\\", "/")
        if catalog is not None and logical in catalog:
            from collections import OrderedDict
            catalog[logical]["rows"] = [OrderedDict(r) for r in w.rows]
    # installed rows nobody ships
    new_rows = {}
    for key, c in sorted(cells.items()):
        if key not in shipped[COLLISION_ATTACK_TABLE]:
            new_rows.setdefault(COLLISION_ATTACK_TABLE, []).append(
                _with(inst[COLLISION_ATTACK_TABLE][key], c, COLLISION_ATTACK_TABLE))
    for ck, (src, c) in sorted(clones.items()):
        base = (inst[COLLISION_ATTACK_TABLE][src] if src in inst[COLLISION_ATTACK_TABLE]
                else (weapons[src], None))
        new_rows.setdefault(COLLISION_ATTACK_TABLE, []).append(
            _with(base, dict(c, key=ck), COLLISION_ATTACK_TABLE))
    for key, new in sorted(repoint.items()):
        if key not in shipped["land_units_tables"]:
            new_rows.setdefault("land_units_tables", []).append(
                _with(inst["land_units_tables"][key], {"primary_melee_weapon": new},
                      "land_units_tables"))
    passive = charge_passive_units(land, mounts, ents, stage)
    if passive:
        for t, rows in charge_passive_rows(db_pack, passive, tag).items():
            new_rows.setdefault(t, []).extend(rows)
    writers = {}
    for t, rows in new_rows.items():
        w = db_writer.DBTableWriter(t)
        for row, rr in rows:
            w.add_row(row, raw_fields=rr or None)
        writers[f"db/{t}/{IMPACT_FRAGMENT}"] = w
    # the fail-closed check on the final state
    final_w = dict(weapons)
    for ck, (src, c) in clones.items():
        final_w[ck] = dict(weapons[src], key=ck, **c)
    for k, c in cells.items():
        final_w[k] = dict(weapons[k], **c)
    flyers = flyer_units(land, mounts, ents)
    changed = set(cells) | set(clones)
    missed, ground = [], []
    if stage_at_least("B", stage):
        for u in land:
            wk = repoint.get(u["key"], u["primary_melee_weapon"])
            if u["key"] in flyers:
                if int(final_w[wk]["collision_attack_max_targets"]) <= 0:
                    missed.append(u["key"])
            elif wk in changed:
                ground.append(u["key"])
    if missed or ground:
        raise RuntimeError(f"[air_dive_rules] REFUSING: impact missed flyer land "
                           f"units {missed[:10]} ({len(missed)}), ground units on a "
                           f"changed weapon {ground[:10]} ({len(ground)})")
    if passive and set(passive) != set(flyers):
        raise RuntimeError("[air_dive_rules] REFUSING: charge passive does not "
                           "cover every flyer land unit")
    report = {"weapons_changed": len(cells), "weapons_cloned": len(clones),
              "land_units_repointed": len(repoint), "charge_passive_units": len(passive),
              "fragments_rewritten": len(edits),
              "flyer_land_units": len(flyers)}
    return writers, report


# --------------------------------------------------------------------------
# [AIR-DIVE-TAKEOFF-W1 2026-11-12] Take-off from melee, for every flying unit,
# both sides, AI included (user rulings 2026-11-12, CONTENT_LEDGER §C8-57 and
# §C8-58). Static read + in-game measurement:
# air-dive-takeoff-w1_scratch/takeoff_gate.md. A flyer asked to take off waits
# on a 3.0 s timer (FC+0x44, 30 ticks) that the per-flight-controller update
# 0x143053bd4 re-arms every tick its engaged check 0x143026588 says busy --
# which it does for any contact, struck or not.
#
# THE RULE [D3, user ruling 2026-11-17, docs/DECISIONS.md; implemented D3-1118]:
# a flying MODEL that was hit by a melee attack within the last N seconds
# cannot take off; N by that model's body size (TAKEOFF_PIN_WINDOWS), decided
# for each model on its own. Two code caves do it (one records every damaging
# melee hit -- the damage applier's own type 0: weapon hits, splash attacks,
# matched combat -- on the flying entity it lands on, one answers the timer of
# each model in place of the engaged check; FLYER-TAKEOFF-HITS 2026-11-16);
# their source, emulator check, sites and the generated site table live in
# pipelines/pin_cave_asm.py, installed at runtime through memreader Plus (the
# site loader: every pattern exactly once, original bytes checked, owned).
# It replaces the rules of §C8-57 (one byte patch: the timer always ran),
# §C8-58 and §C8-78 (whole-unit "more than half" and "last model" windows).
# / 近战中起飞：每个飞行兵模按自己的体型，最近 N 秒内近战挨打就不能起飞（D3）。
TAKEOFF_OWNER = "flyer_takeoff"
TAKEOFF_FEATURE = "takeoff"                       # the agreement feature name
TAKEOFF_BUILD = "6ae2a00b"                       # the build it was measured on
TAKEOFF_SITE_LUA_PATH = "script/campaign/flyer_dive/data/takeoff_site.lua"
# [D3] battle ticks (10 a second: the tick counter ran 15..745 over a 73 s battle) a flying
# model of each body size stays down after a melee hit; smaller waits longer ("越小等越久").
# A ridden unit uses its mount's size: the entity that carries the flight controller is the
# mount (measured, TAKEOFF_SIZE_CODES). After the window the 3.0 s timer still has to run out.
# [D37] one second (10 ticks) more for every size (owner 2026-11-20): was 30 / 35 / 40 / 45.
TAKEOFF_PIN_WINDOWS = {"very_large": 40, "large": 45, "medium": 50, "small": 55}
# [D3-1118] What the engine keeps at flying entity +0x74 for each battle_entities size.
# Measured 2026-11-18 (ingame_1118 item2_1, flyer_size_probe_report HOLDS; again in item6_1 and
# item6_2): harpies 1, pegasus knights 2, feral manticore 3, star dragon 4, every model, both
# reads. For the pegasus knights (ridden) the entity read is the pegasus: its +0xb4 reads 1300.0,
# the mount entity's mass (wh_main_flying_pegasus_blood), not the rider's 100.0.
TAKEOFF_SIZE_CODES = {"small": 1, "medium": 2, "large": 3, "very_large": 4}
# [D3-1118] A model whose +0x74 holds none of the four codes gets the longest window (the
# strictest of the four): an unreadable size never lets a model out earlier than the rule lets
# any size out, and it still leaves once the blows stop (the stock check would pin it for as long
# as anything touches it). The cave counts these answers (``unsized`` in the battle log).
TAKEOFF_PIN_WINDOW_UNKNOWN_SIZE = max(TAKEOFF_PIN_WINDOWS.values())
# [D11, gapfix-1118] Closing the take-off gap. Measured in game 2026-11-18 (series 4 run 1, traced
# caves, 3856 entity-ticks): every entity-tick had exactly one flight update; the update asked the
# take-off check on every update in phase 1 (1522/1522) and in phase 2 with the countdown FC+0x44
# above 0 (683/683), and on none in phase 2 with the countdown at 0 (0/18); every recorded melee hit
# came AFTER that tick's update (65/65). So a model hit at countdown 0, ordered away (phase 1 -> 2)
# before its next update, was lifted by that update (state machine 0x14301b534, phase-2 branch
# 0x14301b8d4: lift when FC+0x44 == 0) without the gate 0x143053ce3 asking the rule. The stamp cave
# therefore raises a 0 countdown to TAKEOFF_GAP_RAISE_TO when it records a melee hit on a model in one
# of TAKEOFF_GAP_RAISE_PHASES: the next update sees a countdown above 0, does not lift, and asks the
# rule (held -> the engine re-arms 30). The countdown is decremented only after the gate (0x143053d8b),
# so a 1 still reaches the gate as 1. Only a 0 is ever written over (lock cmpxchg 0 -> 1).
TAKEOFF_GAP_RAISE_TO = 1
TAKEOFF_GAP_RAISE_PHASES = (1, 2)       # FC+0x90: 1 on the ground, 2 take-off requested (0x14304cea0)
# [D39, owner 2026-11-21] Every model of a fighting flying unit waits at least the game's own 3.0 s after the
# away order, touching an enemy or not; a model hit within its size window still waits that out first.
# "Fighting" is judged by hits, like D3: a melee hit on any model of the unit within the last
# TAKEOFF_UNIT_WINDOW ticks. The stamp cave also stamps the unit; while a model is on the ground (flight
# phase TAKEOFF_UNIT_HOLD_PHASE) the hold cave answers "held" for a unit stamp younger than the window, so the
# engine keeps the countdown at 30 and the away order starts from a full 3.0 s. After the order (phase 2) only
# the model's own window holds. / 部队在挨打：地面兵模的倒计时保持满 3 秒，撤离令后每个兵模至少等 3 秒。
TAKEOFF_UNIT_WINDOW = 30                # ticks; the game's take-off timer (FC+0x44 re-armed to 30)
TAKEOFF_UNIT_HOLD_PHASE = 1             # FC+0x90 == 1: on the ground, no take-off requested yet


def takeoff_pin_window(size):
    """[D3] Battle ticks a flying model of body size ``size`` stays down after a melee hit; an
    unknown size is a refusal."""
    if size not in BODY_SIZES or size not in TAKEOFF_PIN_WINDOWS:
        raise RuntimeError(f"[air_dive_rules] REFUSING: body size {size!r} has no take-off window "
                           f"(sizes {BODY_SIZES})")
    return TAKEOFF_PIN_WINDOWS[size]


def takeoff_window_table():
    """[D3-1118] The windows the hold cave indexes, in the order of the engine's size codes
    (1, 2, 3, 4), then the unknown-size window. Refused unless the codes are exactly 1..4 over
    BODY_SIZES."""
    if (set(TAKEOFF_SIZE_CODES) != set(BODY_SIZES)
            or sorted(TAKEOFF_SIZE_CODES.values()) != [1, 2, 3, 4]):
        raise RuntimeError(f"[air_dive_rules] REFUSING: size codes {TAKEOFF_SIZE_CODES} are not "
                           f"1..4 over {BODY_SIZES}")
    by_code = sorted(TAKEOFF_SIZE_CODES, key=TAKEOFF_SIZE_CODES.get)
    return [takeoff_pin_window(s) for s in by_code] + [TAKEOFF_PIN_WINDOW_UNKNOWN_SIZE]

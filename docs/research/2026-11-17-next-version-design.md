# Flyer Dive & Take-off — design for the next version (2026-11-17)

Research lane, read-only. No game run, no tests, no build. Probes I wrote are in
`D:/Projects/.worktrees/wh3-flyer-dive/update-1117/scripts/` (run with `python -P`).
Installed tables were exported with RPFM 4.7.4 from a copy of the installed `db.pack`
into `update-1117/rpfm_tsv/db/` (schema file dated 2026-10-12; every table I needed decoded).
"Flyer repo" = `D:/Projects/wh3-flyer-dive`. "Ledger" = `D:/Projects/lore_disaster/docs/CONTENT_LEDGER.md`.
The exe read is build `0x6ae2a00b` (checked by `scripts/funcof.py`, which prints the PE timestamp).

---

## 1. Impact damage to a flyer that dives into braced infantry

### What is true today (evidence)

**The attribute names in the brief are UI names, not data attributes.**
- `charge_reflector` / `charge_reflector_vs_large` are keys of the unit-card bullet list
  (`ui_unit_bullet_point_enums`), not attributes. Their text in `local_en.pack`
  `text/db/ui_unit_bullet_point_enums__.loc`: "Charge Defence Against All" / "Charge Defence Against
  Large Foes", tooltip "...will negate the enemy's charge bonus" (`scripts/loc_probe.py`).
  In `lore_disaster/mod/tools/vanilla/vanilla_source_ref.json` they sit in each unit's `bullet_points` list.
- The installed DB attributes are `charge_defense`, `charge_defense_vs_large` and `charge_reflection`
  (installed `unit_attributes_tables`, version 5). Text (`unit_attributes__.loc`):
  - `charge_defense`: "Expert Charge Defence — when bracing, negates the charge bonus of any attacker."
  - `charge_defense_vs_large`: "...negates the charge bonus of any large attacker."
  - `charge_reflection`: "Charge Reflection — When bracing, this unit causes additional damage when attacking charging enemies."
- So only `charge_reflection` deals damage. The two `charge_defense*` attributes only remove the attacker's charge bonus.

**Who carries them** (`scripts/reflect_census.py`: main_units → land_units.attribute_group →
unit_attributes_to_groups_junctions):

| attribute | main units | castes | can_brace |
|---|---|---|---|
| `charge_reflection` | 136 | melee inf 90, missile inf 10, monstrous inf 2, lord 19, hero 15 | 136/136 true |
| `charge_defense_vs_large` | 146 | melee inf 76, missile inf 14, monstrous inf 10, lord 25, hero 21 | 146/146 true |
| `charge_defense` | 62 | melee inf 32, lord 16, hero 8, monster 4, monstrous inf 1, missile inf 1 | 61 true, 1 false |

- `charge_reflection` by key race token: hef 16, chs 16, skv 14, lzd 12, cst 11, cth 9, tmb 8, wef 8,
  emp 7, def 6, bst 5, ksl 4, brt 4, vmp 3, grn 3, sla 3, kho 2, pro 2, chd 1, nur 1, nor 1.
  Every one of the 136 also carries a `charge_defense*` attribute. 134 of 136 are on small bodies.
- Examples with `charge_reflection` + `charge_defense_vs_large`: `wh_main_emp_inf_spearmen_0`,
  `wh_main_emp_inf_spearmen_1`, `wh_main_emp_inf_halberdiers`, `wh2_main_hef_inf_spearmen_0`,
  `wh2_dlc09_tmb_inf_tomb_guard_1` (`scripts/attr_of.py`). Not reflectors: `wh_main_emp_inf_swordsmen`,
  `wh_dlc04_emp_inf_free_company_militia_0`, `wh2_main_hef_inf_white_lions_of_chrace_0`;
  `wh_main_dwf_inf_longbeards` has only `charge_defense_vs_large`.
- 39 ability phases add or remove these attributes (`special_ability_phase_attribute_effects_tables`);
  four add `charge_reflection`: `wh2_dlc13_item_abilities_shield_of_aeons`,
  `wh3_dlc20_item_abilities_the_armour_of_morkar`, `wh3_dlc26_character_passive_belly_stance`,
  `wh3_dlc27_character_passive_supernatural_mist`.

**The game's own numbers** (installed `_kv_rules_tables`; descriptions from the Assembly Kit
`raw_data/db/_kv_rules.xml`, `scripts/ak_desc.py`):

| key | value | CA description |
|---|---|---|
| `charge_reflect_damage_multiplier` | 2 | Charge reflection damage multiplier |
| `charge_reflect_min_charge_factor_threshold` | 0.7 | Charge reflection threshold factor |
| `bracing_charge_reflector_bonus` | 2 | Additional bracing bonus (multiplied to mass) for charge reflectors |
| `bracing_attack_angle` | 80 | half-angle where a bracing entity performs a bracing attack vs an incoming charger |
| `bracing_calibration_ranks` / `_multiplier` | 8 / 4 | full bracing multiplier at 8 ranks |
| `bracing_max_multiplier_clamp` | 10 | max bracing multiplier |
| `bracing_immovable_by_small_entity_mass` | 600 | braced mass beyond which small entities cannot push it |
| `impact_reflection_final_damage_modifier` | 1 | "for pikes": multiplied to the combat damage |
| `impact_reflection_velocity_bonus_damage_modifier` | 3 | "for pikes": x relative speed = damage bonus |
| `impact_reflection_knockback_chance` | 75 | "for pikes": knockback chance on hit |
| `impact_reflection_attack_cooldown_timer` | 0.5 | same defender not hit again by the same pikeman for 0.5 s |
| `unit_braced_status_threshold` | 0.75 | share of entities braced for the unit to count as braced |
| `refusal_chance_vs_charge_reflectors` | 0 | cavalry refusal vs charge reflectors |
| `collision_damage_maximum` / `_modifier` / `_normaliser` | 70 / 0.6 / 0.8 | collision damage formula |

**Two engine paths** (static reads, build 6ae2a00b):
1. *Impact reflection* `0x1430afae4`, only caller `0x14325bf46` inside `0x14325bbec`: a melee roll by the
   braced soldier back at the charger; the charger is knocked flying/down/back by its impact speed against
   10.5 / 7 / 4 m/s, each on a 50 % roll, else knocked back on 75 %; damage × `impact_reflection_final_damage_modifier`
   (`lore_disaster` worktree `air-dive-continuous-w1_scratch/static_notes.md` items 1–2).
   `0x14325bbec` is called from `0x14326a6ba` and `0x14326ae9b` (functions `0x14326a2bc` and `0x14326a958`,
   `scripts/callers.py`, `scripts/funcof.py`); those two have no direct callers (indirect calls). I did not
   resolve which attack path reaches them.
2. *Charge-reflection damage multiplier* in the combat damage code around `0x142e60000`: reads
   `charge_reflect_damage_multiplier` at `0x142e60052` and the 0.7 threshold at `0x142e60091`; after three
   boolean virtual checks on the two combatants and a "charge factor" (`call 0x143065f3c`) ≥ 0.7, the damage
   factor is multiplied by 2 (`mulss xmm8, xmm7` at `0x142e600af`; `scripts/wdis.py 142e5ff80 0x1a0`).
   Which check is "has charge_reflection / braced" and which is "the other one is charging" is **not verified**.

**Does it fire on our dive today? Measured: the impact reflection does not.**
- The AIR-DIVE-BRACE-W1 probe hooked the entry of `0x1430afae4` and logged every call whose reflector or
  charger (or its mount) has a flight controller (`lore_disaster/mod/tools/evidence/air_dive_brace_w1_20261114/brace_probe_asm.py:1-6`,
  record format `F ...` in `brace_probe.lua:5`).
- Over the 533 run folders in `D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1_scratch/runs/`,
  527 report `BATTLE ... on` (the probe installs only when all nine caves incl. `bp_refl` are found,
  `brace_probe.lua:61-63`); 6 report `off`. **`F` records: 0** (counted over all `ld_brace_probe_slice.txt`).
- The targets were braced reflectors: lanes used `wh_main_emp_inf_spearmen_1` and `wh_main_emp_inf_halberdiers`
  (both `charge_reflection` + `charge_defense_vs_large`) plus militia (`jobs_a.txt` line 3).
  Example run `A1_dragon`: the `N` record at 32,500 ms counts 41 braced of 44 enemies within 10 m,
  bracing multiplier max 5.43.
- The ledger says the same (§C11 AIR-DIVE-BRACE-W1 三/四, lines 46220 and 46225: "冲击反弹 0 次").
- Caveat: there is no positive control for this logger in game (no ground-cavalry run was logged, because the
  logger only records flyer participants). So "0" is strong but not proof that the logger can see a reflection.
- **When the dive did not run through our holds, the native bounce happened.** Test-only prototype P
  (AIR-DIVE-CONTINUOUS-W1, ledger lines 45728–45741): with the star dragon's contact attack routed as a
  state-55 action, against braced halberdiers / spears "0.7 秒处动作被打断（状态 33，槽位 540），并被弹回 4 米——这是原版的拒马反弹".
  Median depth −4.6 / −4.1 m, target loss in 1.5 s 0.8 % / 2.5 %. Flyer HP was not recorded in that batch.
  AIR-DIVE-RELEASE-W1 saw similar stops after allowing moving attacks, "没有单独证明" (ledger line 46127);
  BRACE-W1 later explained those stops as the contact-engage state lock and removed them (`dv_contact`).

**Flyer HP measurements that exist.**
- Only the take-off lane logged flyer HP (`F <ms> <lane> <flyer hp> ...`, `air_dive_autotest.lua:84-85`).
  Runs `air-dive-takeoff-w1_scratch/runs/bsp*` (vs `wh_main_emp_inf_spearmen_0`, a reflector) and `bsw*`
  (vs `wh_main_emp_inf_swordsmen`). Lanes: 1 star dragon, 2 griffon knights, 3 pegasus knights, 4 sun dragon
  (ledger line 45598). Flyer unary-HP loss in the first 1.5 s after first melee contact (`scripts/flyer_hp.py`):
  - vs spearmen (14 lanes × 7 runs): star dragon 0–0.8 %, griffon knights 0–1.1 %, **pegasus knights 0–5.9 %**
    (bspsP 5.9 %, bspsT 5.6 %, bspcP 2.1 %, bspsS 1.7 %), sun dragon 0 %.
  - vs swordsmen: every lane 0–0.7 %.
  - This difference cannot be credited to reflection: the spear weapon has `bonus_v_large` 15
    (`wh_main_emp_spear_0`; sword 0, installed `melee_weapons_tables`). The cycle scenario also lets the target attack.
- The damage-applier logger (FLYER-TAKEOFF-HITS, `air-dive-brace-w1_scratch/hits/runs/H1–H4`, 90 s each, swordsmen /
  chaos lord / giant / chosen) logged 410 damage calls on flyers, **all type 0 (melee)**; no type 5 (impact)
  and no type 6 (collision attack) on a flyer. No braced reflector was in those runs.
- Ledger line 45598: 90-s cycle fights, end-of-battle flyer/target loss vs spearmen: star dragon 11 % / 39 %,
  griffon 12 % / 69 %, pegasus 35 % / 22 %, sun dragon 22 % / 39 %; vs swordsmen 1 % / 57 %, 1 % / 58 %, 14 % / 45 %, 11 % / 42 %.

**Why the shipped dive skips the bounce (likely, not proven).** The shipped caves hold a fast landed flyer:
`dv_skip` (no standing contact attack while fast, dispatcher entry `0x143259794`), `dv_contact` (no melee engage),
plus five re-path holds (`dive_cave_asm.py:13-95`). The prototype that produced the bounce routed the contact
attack through the action starter; the shipped holds never start that standing attack. I could not tie
`0x14325bbec` statically to the dispatcher (indirect calls), so this link is an inference.

**The mod's own collision attack is not a risk of double damage to the flyer.** `IMPACT_STAGE = "B"` gives the
flyer's weapon `collision_attack_max_targets` (`air_dive_rules.py:888`, `flyer_weapon_plan`); that attack damages
the people the flyer runs into (engine `0x143060e44`, damage type 6), not the flyer. Reflection damage would be
a separate hit on the flyer. The two would add up on one contact: flyer hurts front rank (type 6) and front rank
hurts flyer (reflection). That is how the game treats a ground charger into pikes, so it is not "double damage".

### Recommendation

Use the game's own impact reflection, not a new damage source. Smallest change: **let a frontal contact with a
braced body end the hold, so the engine's own reflection runs.** In `dive_cave_asm.py` add one more condition to
the contact test (the same place `dv_contact` already reads the touched body at `+0x18` for FLYER-FIX-1117):
if the touched body is braced (body `+0xbc` bracing multiplier > 1, or the immovable bit `0x10` of `+0x6c`;
both fields from the static read, `static_notes.md` item 1) **and** the flyer approaches inside the body's
bracing arc (`bracing_attack_angle` 80° half-angle, read from `_kv_rules`, not hard-coded), the cave does not
hold: the engage, the contact attack and the reflection go through as in vanilla, the window closes (as
`_window_close`). All numbers stay CA's (`charge_reflect_*`, `impact_reflection_*`, `bracing_*`).

What this means for the player, from prototype P: a frontal dive into braced spears / halberds is stopped and
thrown back about 4 m and takes the reflection hit; a dive from the flank or rear, into unbraced troops, or into
non-reflectors is unchanged. This partly undoes AIR-DIVE-BRACE-W1, whose aim was that braced spears do not stop
the dive (21/78 early stops before that fix). The spec already says the stopper should be "原版拒马、反弹、碰撞分层，
原版值不改" (`lore_disaster/docs/ARCHITECTURE.md` 支柱二 item 2 and the "被谁截停" row), so this is consistent
with the spec, but it is a visible change that needs the user's yes.

Next-best options, if the user wants the dive to carry on and still hurt the flyer:
1. *Charge-reflection multiplier only.* Keep the holds; rely on the braced front rank's ordinary melee hits once
   contact begins, doubled by `charge_reflect_damage_multiplier` when the engine counts the flyer as charging.
   Cost: zero code if it already applies; but I could not verify the "charging" check (above), and the holds
   suppress the flyer's engage, so the spearmen may not swing during the slide. Must be measured first.
2. *Data: a passive on reflector infantry.* Rejected: invents a mechanic and numbers; also conflicts with
   §C8-61 "不做隐藏被动".
3. *Engine collision damage* (`0x142e3f2f8`, mass ratio × relative speed, uses the braced multiplier `+0xbc`
   per the engine read). Already native; the H1–H4 logs show it never produced type-5 damage on a flyer vs
   unbraced troops. Whether it does vs braced reflectors is unmeasured; it would need no change if it does.

### Open points for the user

- Should a frontal dive into braced reflectors be **stopped and bounced** (vanilla reflection, option above),
  or should the flyer **carry on and only take damage**? The game has no native mechanic for "carry on and get hurt";
  the second needs option 1 to be true in game, or an invented rule.
- Only `charge_reflection` units (136), or also `charge_defense*`-only units such as Longbeards? Vanilla
  reflection damage is tied to `charge_reflection`; the bracing mass bonus ×2 is tied to `charge_defense*`
  (`static_notes.md` item 1).

### Work list for the implementation lane

1. Probe first (test-only, no shipping change): reuse `brace_probe_asm.py` `bp_refl` plus the FLYER-TAKEOFF-HITS
   applier logger (`hits/hit_probe_asm.py`), add a positive control lane (ground `wh_main_brt_cav_knights_errant_0`
   or similar into braced spearmen; the logger must be widened to log non-flyer chargers for that lane).
2. If option 1 shows the ×2 already applies during the slide with a measurable flyer loss: stop, report numbers.
3. Else implement the braced-front release in `mod/tools/pipelines/dive_cave_asm.py`: extend the `dv_contact`
   source (and the `_fast_test`/`_window_test` callers that hold `dv_skip`) with a `_braced_front(body, flyer)` test;
   add field anchors for `+0xbc` / `+0x6c` like the existing anchors; Unicorn cases (braced front → pass + window
   closed; braced flank/rear → hold; unbraced → hold; ridden flyer; null body) and mutants.
4. Regenerate `mod/script/campaign/lore_disasters/data/ld_flyer_dive_site.lua` (`--write-site`); magic
   `LDFLYDV2` → `LDFLYDV3`; the agreement format changes with the cave source (mixed versions will not pair).
5. Battle log: new counter "braced front released".
6. README (both languages): one line on the reflection rule.

### In-game checks needed

- Lanes: star dragon, feral manticore, griffon knights (`wh2_dlc15_hef_inf_mistwalkers_griffon_knights_0`),
  pegasus knights; targets `wh_main_emp_inf_spearmen_1` (braced, still, facing the flyer), `wh_main_emp_inf_halberdiers`,
  `wh_main_emp_inf_swordsmen` (control), plus a flank approach (target turned 90°). Three runs each, shipped vs candidate.
- Log per 100 ms: flyer unary HP and men, target HP; per call: damage applier type and call site on the flyer;
  reflect rolls (`bp_refl`); touchdown speed, travel, stop time.
- Pass: candidate shows reflect rolls > 0 only on braced frontal lanes; flyer loss in the first 1.5 s above the
  swordsmen control; flank lanes unchanged from shipped.

---

## 2. Take-off from melee: window by body size

### What is true today (evidence)

- Rule: multi-model unit held while more than half of its living flying entities were struck by melee
  (damage type 0) in the last 15 ticks (1.5 s); exactly one living entity → its last 30 ticks (3.0 s)
  (`air_dive_rules.py:1410` `TAKEOFF_PIN_WINDOW_TICKS = 15`, `:1416` `TAKEOFF_PIN_WINDOW_SINGLE_TICKS = 30`;
  ledger §C8-58, §C8-78).
- Cave: `pin_hold` at `0x143053cfb` loops the unit's living flight entities (unit `+0x184` count / `+0x188` array)
  and compares each entity's stamp with the window at buffer `+0` (multi) or `+40` (single)
  (`pin_cave_asm.py:47-63`, layout `:65-74`, constants `WINDOW_AT=0`, `WINDOW_SINGLE_AT=40`). Magic `LDFLYPN2`.
  The cave reads no size today.

**Recorded hits (the only full per-hit logs):** `air-dive-brace-w1_scratch/hits/runs/H1–H4`, damage-applier
logger, every call on a flyer with tick, entity and type; 90-s cycle fights (attack 8 s, leave, attack again
6 s later). Lanes: star dragon (very_large), feral manticore (large), Dieter on undead manticore (large,
single), Bretonnian pegasus knights (24 models, medium). `scripts/hit_gaps.py` computes gaps between melee hits
and, for each window W, the share of in-melee samples (hp file `F` lines, flyer in melee) at which the rule would hold.

| opponent | flyer | hits | gap median / p75 / max | held share at W = 1.0 / 1.5 / 2.0 / 3.0 / 4.0 / 5.0 / 6.0 s |
|---|---|---|---|---|
| swordsmen | star dragon | 21 | 2.3 / 5.3 / 24.7 s | 31 / 41 / 52 / 68 / 82 / 92 / 95 % |
| swordsmen | feral manticore | 46 | 1.1 / 1.6 / 15.1 s | 45 / 59 / 67 / 77 / 83 / 88 / 89 % |
| swordsmen | Dieter | 20 | 1.3 / 4.9 / 24.3 s | 29 / 40 / 50 / 65 / 77 / 88 / 89 % |
| chosen | star dragon | 40 | 0.8 / 1.8 / 15.6 s | 39 / 49 / 56 / 68 / 78 / 87 / 91 % |
| chosen | feral manticore | 59 | 0.6 / 1.6 / 9.8 s | 47 / 59 / 68 / 79 / 86 / 92 / 92 % |
| chosen | Dieter | 35 | 0.9 / 1.7 / 15.7 s | 40 / 51 / 58 / 68 / 77 / 85 / 87 % |
| giant | star dragon | 3 | 5.2 / 6.2 / 6.2 s | 7 / 11 / 15 / 22 / 30 / 36 / 37 % |
| giant | feral manticore | 3 | 35.4 / 42.6 / 42.6 s | 6 / 8 / 11 / 17 / 22 / 28 / 28 % |
| giant | Dieter | 7 | 13.3 / 19.9 / 30.0 s | 11 / 16 / 22 / 33 / 44 / 55 / 60 % |
| chaos lord | star dragon / Dieter | 2 / 2 | — | dragon ≤ 18 %, Dieter 10–50 % |
| any of the four | pegasus knights (24) | 22–64 | — | **0 % at every window** |

- For the pegasus knights, the largest share of living models struck within the window at any in-melee sample
  was 17–27 % (1.5 s), 21–33 % (3 s), 29–45 % (6 s) (`hit_gaps.py`, last block). **The "more than half" test
  never passed for a 24-model unit, whatever the window.** For multi-model units the window length is nearly
  irrelevant; the half threshold decides.
- Caveats: one run per opponent; "in melee" is the unit's `is_in_melee`, which includes moments the flyer is
  leaving; the H runs used the older stamp cave, but the logger is independent of it.

**Who is in each size class** (installed `battle_entities`, `fly_speed > 0`, not fauna; land units by
`air_dive_rules.body_entity`; `scripts/flyer_sizes.py`):

| size | flying entities | land units | multi-model land units | entity mass range | examples |
|---|---|---|---|---|---|
| small | 17 | 24 | 21 | 80–2000 | fell bats, harpies, furies (5), carrion, onyx crowmen; also Valkia, Azazel, Malagor (single) |
| medium | 18 | 91 | 19 | 700–2100 | pegasus (4 rows), dark pegasus, jade longma, hellsteed, screamers, rot flies, Tzeentch discs, warhawk |
| large | 37 | 128 | 44 | 200–6000 | great eagle, manticore (4), terradon (4), ripperdactyl, vargheist, phoenixes, chimera, morghast, Nagash, gyrocopter |
| very_large | 65 | 199 | 9 | 1600–20000 | dragons (18), griffons (2), terrorgheist (4), wyvern, coatl, daemon princes, celestial lion, taurus, lammasu |

Hippogryph: `wh_dlc07_brt_mnt_hippogryph_blood` large; Beaquis and the hero hippogryph very_large (`flyer_sizes.py`
family counts: hippogryph large 1 / very_large 2). Carrion: base small, RoR and boss large.
Body size is not creature size: Valkia and Azazel are small, Nagash large.

**What the game's own data says about size and interruption** (`scripts/size_cols.py`, medians over flyers):

| size | mass | `hit_reactions_ignore_chance` | `knock_interrupts_ignore_chance` | `acceleration` |
|---|---|---|---|---|
| small | 200 | 0 | 0 | 8.0 |
| medium | 1300 | 25 | 15 | 7.5 |
| large | 1600 | 50 | 50 | 8.0 |
| very_large | 3800 | 70 | 50 | 6.0 |

- Also `interrupt_mass_ratio_clamp_hit_reaction` 0.4 ("attacker/defender mass ratio where no hit reactions will be
  triggered"), `_knockdown` 0.5, `_knockback` 0.35 (`_kv_rules`, AK text): a 100-mass spearman cannot interrupt a
  5,900-mass star dragon at all (ratio 0.017).
- Reading: vanilla makes big bodies **harder to interrupt** by blows (bigger = shorter hold), but slower to start
  moving (very_large acceleration 6 vs 8; bigger = longer hold).
- Real flight: launch effort rises with size (wing loading); large flyers need a run-up. No source checked in this lane.
- Tabletop: I did not find or check any Warhammer rule for leaving close combat by flying. **Not verified.**
- Gameplay (from the table): a single monster fighting infantry is struck every 0.6–2.3 s (median), so it is held
  most of the time with any window ≥ 3 s; against a giant or lord, blows come 5–35 s apart, so any window up to
  6 s lets it leave between blows.

### Recommendation

**Bigger = longer, applied to the single-model window; keep multi-model at 15 ticks.**

| body size | single-model window | multi-model window |
|---|---|---|
| small | 15 ticks (1.5 s) | 15 ticks (1.5 s) |
| medium | 20 ticks (2.0 s) | 15 ticks (1.5 s) |
| large | 30 ticks (3.0 s, today) | 15 ticks (1.5 s) |
| very_large | 40 ticks (4.0 s) | 15 ticks (1.5 s) |

Alternative ("smaller = harder to leave", following vanilla `hit_reactions_ignore_chance`): single-model small
30 / medium 30 / large 25 / very_large 20 ticks, multi-model 15.

Reasoning for the user: the window only matters for single-model units; 24-model units were never held at any
window up to 6 s, because fewer than half the models are ever struck at once. A large body needs more effort to
take off and is the classic target for tying up with infantry, so it should stay pinned longer: at 4 s a
dragon fighting infantry is held 78–82 % of melee time instead of 68 % at 3 s. Against a giant or a lord it can
still leave between blows (held 30 % at 4 s), which keeps take-off useful. If the user wants small swarm units
to be harder to pull out, the lever is the "more than half" share, not the window (open point).

### Open points for the user

- Direction: bigger-longer (recommended) or smaller-longer (alternative). Both tables above.
- Multi-model units are practically never held today (0 % in all four opponents). Should the multi-model rule
  use a lower share (for example "a quarter of living models")? That is a rule change, not a window change.
- Size for a ridden unit: the mount's body size (as `body_entity` and `MASS_FACTOR` use), not the rider's. Assumed.

### Work list for the implementation lane

1. `mod/tools/lib/air_dive_rules.py`: replace the two constants with `TAKEOFF_PIN_WINDOWS = {size: (multi, single)}`
   over `BODY_SIZES`; refuse an unknown size.
2. Find the size at the cave. First choice: the engine's own size field. The engine read names "推人者体型档
   [实体+0x74]" (`air-dive-engine-w1_scratch/air_dive_engine.md` §一.1); it is not verified that it holds the
   `battle_entities.size` class nor which object `实体` is. Verify with a test-only reader on one entity of each
   size before using it, and add a field anchor in `pin_cave_asm.py` `ANCHORS` that pins the engine code reading it.
   Fallback if it does not hold the size: a per-unit window written by Lua (a generated `unit key → size` table
   from `battle_entities` via `body_entity`; 442 installed land units plus donor rows) into a unit-keyed table the
   cave reads; this needs the unit pointer from Lua (not verified available through memreader Plus).
3. `mod/tools/pipelines/pin_cave_asm.py` `pin_hold`: index a 4 × 2 window table at buffer `+40..+71` by the size
   tier; magic `LDFLYPN3`; Unicorn cases per size and per living count; mutants (wrong tier index, single/multi swapped).
4. `mod/script/campaign/lore_disasters/lib/ld_flyer_takeoff.lua` `arm`: write the 8 windows.
5. Regenerate `ld_flyer_takeoff_site.lua`; update `tests/test_flyer_takeoff_site.py` counts; README (both languages).

### In-game checks needed

- Reuse the FLYER-TAKEOFF-HITS series (`air_dive_autotest --scenario engage --cmd scenario=cycle,fight_ms=90000,cycle_away_ms=8000`)
  with the applier logger, plus one medium single (`wh_main_brt_cha_paladin_0` on a pegasus, or a disc herald) and
  one small single (Valkia or Malagor). Opponents: swordsmen, chosen, giant.
- Record: per hit tick and entity; per leave order, seconds to take-off (`track.py`); held/free answers per size.
- Also read the size field per entity once (step 2) on a battle with one entity of each size.

---

## 3. Balance submod: breath in melee and the mass cut

### What is true today (evidence)

**Breath in melee.**
- `air_dive_rules.breath_usage_writer` (`air_dive_rules.py:833-846`) writes the whole installed
  `special_ability_to_invalid_usage_flags_tables` under the vanilla path `db\special_ability_to_invalid_usage_flags_tables\data__`
  minus the breath rows; `build_air_dive_minimod.usage_entries` (`build_air_dive_minimod.py:281-287`) ships it.
- Today (`scripts/breath_count.py`, installed game): 73 breath abilities found; 703 installed rows → 671 kept,
  32 removed (20 `engaged_in_melee`, 12 `grounded`) on 20 abilities (e.g. `wh2_main_unit_abilities_star_dragons_breath`,
  `wh2_dlc10_unit_abilities_frost_wyrm_breath`, `wh3_main_daemon_arms_abilities_blue_fire`).
- Also used by `pipelines/build_pin_on_hit_probe.py:50` (test pack) and `tests/test_air_dive_breath.py:100`.
- This part touches no other table, so it splits cleanly.

**Mass cut.**
- `tuned_cells` adds `mass` = installed mass × `MASS_FACTOR` (large 0.85, very_large 0.75), with `MASS_SIZE_OVERRIDE`
  (celestial lion and boss lion cut as large) and `MASS_CUT_MACHINES` (11 bodies untouched)
  (`air_dive_rules.py:159-174`, `:511-515`, `:557-559`).
- It is written into the same fragment as every other flyer cell: `db\battle_entities_tables\ld_air_dive`
  (`build_air_dive_minimod.py:129-162`).
- `scripts/mass_rows.py` over the installed table: the rule ships 137 rows; 93 carry a `mass` cell; **0 rows change
  only mass.** Every mass row also carries charge speed, deceleration, charge distances, locomotion repoint, turn
  clips and jump chance. The rows must be split by duplication, not by moving rows.
- The collision attack is already independent: it is sized on `uncut_mass` (`air_dive_rules.py:518-522`,
  `impact_assembly` `mass_of` at `:1290-1292`); the BRACE-W1 test showed the cut changed only `battle_entities`,
  the weapons table was byte-identical (ledger line 46289).

**DB load order (measured in this project).** RESIST-W2 (ledger line 44914): two packs ship the same row; the
row from the pack whose **name sorts first** wins, independent of the order in `used_mods.txt`. Caveat from the
same line: pack name and fragment name both sorted a < b in that test, so which of the two decides was not separated.

**Main-mod behaviour measured with the cut in place (dependencies).**
- Early stops: rounds 3 and 4 of BRACE-W1. Round 3: groups without the cut 3/78 early stops, with the cut 10/104,
  all four celestial-lion stops in cut groups (ledger line 46305). Round 4 (120 lanes each): "早停变多来自质量下调，集中在天狮"
  (line 46359); the lion at ×0.75 stopped below 2 m/s inside 15 m in 8/16 lanes against 1/16 uncut
  (`air_dive_rules.py:128-131`); `MASS_SIZE_OVERRIDE` exists only because of the cut (line 46390).
- Impact: no measurable change from the cut: knocked down in 1.5 s, median 18 → 21; target HP loss 0.041 → 0.041
  (line 46306).
- The shipped release pack and all FLYER-FIX-1117 runs (`A/C/R/F` lanes) ran with the cut (that pack is built by
  the same `tuned_cells`). The 20 m slide window was set from target depth + touchdown distance
  (`dive_cave_asm.py:184-188`), which does not depend on mass.
- Not measured: whether the cut changes how often a landed flyer is struck or interrupted (mass enters
  `interrupt_mass_ratio_clamp_*`), i.e. take-off behaviour. Removing the cut makes flyers heavier again: expect fewer
  early stops (the direction measured above) and no impact change.

### Recommendation

One build script, two outputs, from one run over the installed game, so the two packs can never disagree.

- Main pack (`ld_air_dive.pack`, unchanged name): `tuned_cells` **without** the mass cell; no usage-flag table.
- Submod pack, proposed name **`flyer_dive_balance.pack`** (no `ld_`; "f" sorts before "l", so its rows win the
  measured name-order rule against `ld_air_dive.pack`):
  - `db\battle_entities_tables\flyer_dive_balance`: the 93 mass-cut rows, each **the main pack's full row plus the
    mass cell** (installed row + main cells + mass), under the installed GUID. When both packs load, these rows win
    and differ from main only in `mass`, so main's other values stay intact.
  - `db\battle_entity_locomotion_constants_tables\flyer_dive_balance`: the two `ld_flyer_*` rows, byte-identical
    copies of main's, so the repointed `locomotion_constants` never dangles if the submod is loaded alone.
  - `db\special_ability_to_invalid_usage_flags_tables\data__`: the breath table as today (vanilla path).
- Submod alone (main missing): the breath part works by itself; the mass rows would also apply main's charge speed,
  deceleration 30, jump chance 0 and the locomotion repoint without the renamed tables and caves. That combination
  was never measured, so the submod **must declare the main mod as a Workshop required item**, and its README must
  say "requires Flyer Dive & Take-off".
- Version coupling risk: if main changes a cell and the submod is not rebuilt, the submod's stale full rows silently
  win. Publish both from the same build every time; add a build stamp (below) so a mismatch is logged.

### Open points for the user

- Pack name: `flyer_dive_balance.pack` (proposed). Any name works if it sorts before `ld_air_dive.pack`.
- The celestial-lion exception moves with the cut into the submod. Without the submod the lion is uncut (2000), which
  removes the early stops that exception was made for.
- Alternative carrier for the mass cut without duplicated rows: a visible passive with `stat_mass` × 0.85 / 0.75
  on flyer land units (junction rows add, never override). Not recommended: §C8-61 rejected hidden passives; a visible
  one changes the unit card; and `flyer_db` has no recorded schema for `special_ability_phase_stat_effects_tables`
  (`air_dive_rules.py:1116-1118`).

### Work list for the implementation lane

1. `mod/tools/lib/air_dive_rules.py`: split `tuned_cells(row, declared=())` into the main cells and a new
   `balance_cells(row)` (mass only); `tuned_cells` no longer adds `mass`. Keep `mass_factor` / `uncut_mass` (the
   collision attack still sizes on the uncut mass; with main alone uncut = installed). Move `MASS_*` and the breath
   helpers under a "balance submod" heading in the docstring.
2. `mod/tools/pipelines/build_air_dive_minimod.py`: `main()` takes `--out` and new `--balance-out`; `db_entries`
   produces main rows without mass; new `balance_entries(db_pack)` produces the submod rows (main row + mass),
   the two locomotion rows and `usage_entries()`; `usage_entries` leaves the main output. Fragment constant
   `BALANCE_FRAGMENT = "flyer_dive_balance"`.
3. Build stamp: write the same short hash (sha256 of the main `battle_entities` fragment) into a tiny Lua in each
   pack (`script/battle/mod/flyer_dive_balance_stamp.lua` in the submod, the main value in `ld_flyer_dive.lua`
   or a sibling file); the battle log writes "balance submod built for a different main version" on mismatch.
4. `mod/tools/pipelines/build_pin_on_hit_probe.py:50`: take the breath table from the balance entries (or drop it).
5. Tests (new or moved; not run in this lane):
   - main pack: no `mass` cell in any `battle_entities` row; no `special_ability_to_invalid_usage_flags_tables` file;
   - submod rows == main rows for the same keys except `mass`, and `mass` == installed × factor (move the
     assertions at `tests/test_air_dive_charge_speeds.py:125-127`);
   - submod pack name and every submod fragment name sort before the main pack / fragment names;
   - submod locomotion rows byte-identical to main's;
   - the two packs' file paths are disjoint except declared overlaps (none expected);
   - `tests/test_air_dive_breath.py` targets the balance output.
6. README (both languages): new section "Balance submod (optional)": what it changes, requires the main mod, load order
   note; remove "breath-ability usage flags" from the main pack description.
7. Workshop: a second item; required item = 3840651516; tags as main.

### In-game checks needed

- Main pack alone: re-run the BRACE-W1 round-4 style lanes (spear + halberd, single-model flyers, celestial lion,
  star dragon, manticore) and compare early stops and 1.5-s impact against the shipped pack.
- Both packs: confirm in-battle mass reads the cut values (entity `+0xb4` per the engine read) and charge speed reads
  main's value (the row merge works as designed); swap pack names once to confirm the name-order rule for these two.
- Submod alone: one smoke battle to make sure nothing crashes; it will not be supported.
- Breath: one flyer with a breath in melee, both with and without the submod (`air_dive_autotest --scenario engage`).

---

## 4. Second carry-through: mass and speed only?

**Direct answer.** Before, a landed flyer was "carried" (our caves hold off the engine's stop, engage and re-path)
while it was fast and within 20 m of the first hold; the bug was that a re-charge from melee became fast again
and re-opened those holds. The fix (`80953c6`) ends the holds at the first melee engage, so a second charge from
the ground is now plain vanilla — and vanilla does decide that charge by mass, speed and bracing, which is what the
user describes. A pure speed (or momentum) test cannot replace the state rules safely: for several flyers the dive
arrival speed and the ground charge speed differ by 0–1.5 m/s, and a speed threshold would also cut the end of
every first dive. Keep the state rules; a "time since touchdown" bound is a sound extra safety net.

### What is true today (evidence)

**The speed test.** `_fast_test` (`dive_cave_asm.py:284-314`): the entity is in state 30 or 33 (`+0x26c`), or state 0
on the ground (`+0x104 == 0`), **and** its planar velocity squared `(+0xe0)² + (+0xe8)²` is greater than
`SKIP_SPEED²` read from buffer `+16`; `SKIP_SPEED = 2.0` m/s (`dive_cave_asm.py:199`). Velocity is the entity's
own world velocity in m/s (`static_notes.md` item 6: `+0xe0/+0xe4/+0xe8` = velocity, correlation 1.000 with position
deltas). Every hold uses it: `dv_skip`, `dv_keep`, `dv_engage`, `dv_reorder`, `dv_reorder_move`, `dv_attack_move`,
`dv_tick_move`, `dv_contact`, `dv_settle` (docstring `:12-95`); the re-path holds also require "on the ground but
still in flight movement" (`+0x104 == 0`, `+0x710 != 0`). Then `_window_test` (`:317-...`): only within
`SLIDE_RELEASE_M = 20` m of the first ground hold.

**Why the second carry happened** (commit `80953c6` message; ledger §C11 FLYER-FIX-1117 二): the window ended only
by 20 m or by a new air charge. A first charge stopped before 20 m left it open; a re-charge from that melee made the
flyer faster than 2 m/s again, and every hold returned until 20 m from the FIRST hold, dragging the enemy. 2 m/s is
far below any ground charge (installed flyer `charge_speed` 3.0–16.0, median 9.5, `scripts/speed_sep.py`).

**The fix (state rules, `80953c6`):** (1) `dv_contact` does not carry a touched body that is already engaged with
another unit (`+0x324 == 1`, its order target's unit differs); (2) `_window_close`: any engage the engine takes for
a landed flyer closes its window for good; (3) `dv_through`: an air re-charge ordered while engaged keeps it closed.
Measured (ledger FLYER-FIX-1117 table): scenario A releases at 20 m 28 → 0, high-speed attack holds 230 → 0; final A
0 releases; first-charge engage holds unchanged (R: 142 / 145), "新的一次俯冲照旧带人".

**Speeds.**
- Dive touchdown speed, single-model, round-3 RG medians (`air_dive_brace_w1_20261114/r3_slide.txt`): lammasu 13.9,
  chimera / cockatrice / dragon / frost wyrm / taurus / terrorgheist / celestial lion 14.7–14.9, wyvern 15.9,
  manticore 17.4, Bloodthirster / storm dragon 17.0, great eagle 18.9 m/s. Star dragon in SPEED runs 13.7–15.0
  (`speed_proof.txt`). The rule's arrival speed is 0.9 × flying charge speed (`air_dive_rules.py:459-470`), 2.9–18.0 m/s.
- Ground re-charge from melee, star dragon (the only single-model flyer in the FLYER-FIX-1117 runs; movement
  recorder unit-centre speed): max ground speed after first melee 9.8–13.2 m/s in A/C/R/F (`scripts/speed_runs.py`).
  Its ground `charge_speed` is 9.5, flying charge 15, touchdown ~15.
- Multi-model units: the recorder's unit-centre speed is not usable (values of 40–480 m/s come from the centre jumping
  as models die and spread). No per-entity ground re-charge speed was recorded for longma or pegasus.
- Installed ground `charge_speed` against the dive arrival speed, all 137 shipping flyers (`speed_sep.py`): margin
  (arrival − ground charge) minimum −0.1 (thunderbarges, sky junk), median 4.5 m/s; 3 flyers ≤ 0, 15 ≤ 2 m/s:
  burning chariot 0.7, six Tzeentch disc rows 1.2, boss phoenix 1.3, onyx crowmen 1.5. Jade longma: arrival 16.2,
  ground charge 11.0.

**Mass side.** The engine's own collision decides by mass and speed: pair solver with mass impulses and restitution
0.3, an integer tier split (share 1.0 / 0.8 / 0.2 / 0.1 / 0 for tier gaps 0–4), braced soldiers get a mass multiplier
up to 10 (×2 more for `charge_defense*`), and ≥ 600 braced mass is immovable for small entities
(`static_notes.md` items 1 and 3; `_kv_rules` above). Knocks: collision speed thresholds 10.5 / 7 / 4 / 3 m/s with
the pusher's `dealt_collision_knocked_*` multipliers (`air_dive_engine.md` §一.1). Vanilla ground cavalry measured by
the project: 1,200–1,500 mass at 10.6–11.2 m/s stopped in 0.6–0.8 s against every braced or heavy target and went
9–13 m into militia ("先停、后接战"; `ARCHITECTURE.md` 支柱二 item 1).

### Assessment

- **(a) stops the dragging case:** a threshold at the flyer's own ground `charge_speed` would stop the longma case
  (16.2 vs 11.0) but not cleanly in general: charge speed can be raised by abilities and slopes (not measured), and for
  15 flyers the margin is ≤ 2 m/s.
- **(b) keeps the first dive:** no. Today the first dive is held down to 2 m/s. A threshold at ground charge speed
  (median 9.5) would hand over to vanilla as soon as the bodies slow the flyer to ~9.5 m/s, cutting the low-speed end
  of every dive. How many metres that costs was never measured.
- **(c) no carry on a ground charge:** only with a per-entity threshold above the ground charge speed — the same
  trade-off as (b). Momentum (mass × speed) does not help: both charges are made by the same body, so mass cancels and
  only speed remains.
- **"Hold only within N ticks of touchdown":** a physical event (the `+0x104` 2 → 0 change at landing) that a ground
  re-charge never has. Measured first-dive stop times: median 2.4–3.0 s, travel up to ~55 m before the 20 m bound
  (`r3_slide.txt`). A bound of about 40 ticks (4 s) after touchdown would cover the dive and end any later carry.
  It needs the cave to stamp the touchdown tick (it stores a first-hold point today, not a time).
- **Does the engine alone do what the user expects once the holds are off?** Yes for the second charge: after the fix
  a ground re-charge from melee is never held, so mass, speed, bracing and the tier rule decide it as for any ground
  charger. For the first dive, no: without holds, touchdown zeroes the flyer's speed (W8: 0.0 m after touchdown with
  vanilla slot 104; `ARCHITECTURE.md` 支柱二 item 4), so there would be no carry at all.

### Recommendation

Keep the three state rules. Optionally add the touchdown-age bound as a second safety net (a flyer is carried only
within N ticks of its last touchdown and within 20 m). Do not replace the state rules with a speed or momentum
threshold. Tell the user: the second charge already is "mass and speed only" — it is the engine's own charge.

### Open points for the user

- Add the touchdown-age bound (extra safety, one more cave change and a new agreement), or leave the fix as it is?

### Work list for the implementation lane (only if the bound is wanted)

1. `dive_cave_asm.py`: store the battle tick in the slide entry when the window opens on the ground (16-byte entries
   today: key, x, z; widen to 32 bytes or reuse a field); `_window_test` passes when `now − tick > N`.
2. `air_dive_rules.py`: `SLIDE_RELEASE_TICKS` with its evidence; emulator cases and mutants; magic `LDFLYDV3`;
   regenerate the site table. Mixed versions will not pair in multiplayer (agreement format follows the cave source).

### In-game checks needed

- Per-entity velocity log (`+0xe0/+0xe8`, the brace probe's `T` record) for jade longma riders, pegasus knights,
  griffon knights, a Tzeentch disc herald and the star dragon: first dive (touchdown speed and speed at each
  hold release) and a ground re-charge from melee (peak speed), scenarios `recharge` and `assist` from `80953c6`.
- From that, the share of first-dive travel that happens below each candidate threshold, and the drag distance of the
  target in R/A/C with and without the bound.

---

## What I could not verify

- Which of the three checks before the ×2 in `0x142e60000` means "braced / charge_reflection" and which means
  "target is charging"; whether a landed, held flyer counts as charging there.
- The static link between the shipped `dv_skip` / `dv_contact` holds and the impact-reflection caller `0x14325bbec`
  (reached only through indirect calls).
- That the `bp_refl` logger can see a reflection in game at all (no positive control was run).
- Flyer HP in the prototype-P bounce runs (not logged).
- That engine field `+0x74` holds the `battle_entities.size` class, and on which object.
- Whether Lua can obtain unit pointers through memreader Plus for a per-unit window table.
- Whether pack name or fragment name decides DB row priority (the measured test had both a < b).
- Any Warhammer tabletop rule for flying out of close combat (not searched).
- Real-flight sources for launch effort vs size (not searched).
- Per-entity ground re-charge speeds for multi-model flyers (only unit-centre data exists, which is unusable).
- The RPFM schema is from 2026-10-12 while the game was updated 2026-11-04; all tables I used decoded, but I did not
  re-encode them byte-for-byte.

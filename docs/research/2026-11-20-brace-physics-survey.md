# 2026-11-20-brace-physics-survey

> 来源：只读的离线车道（静态读 `Warhammer3.exe` 9.0.5 与游戏数据，没开游戏），2026-11-20，由主模组仓库的会话派出；原件与脚本、反汇编在仓库外的 `D:/Projects/.worktrees/wh3-flyer-dive/brace-physics-1120/`。数据侧的离线普查（各单位质量、`_kv_rules` 的架势与冲锋反制数值、MCT 能调什么）。主管没有逐条重读；其中 `scalar_bracing` 的三行是主管自己另从表的原始字节读出来的（`docs/HISTORY.md` BRACE-READ-1120）。
> 车道的报告是英文原文，一字未改。

---

`REPORT.md` was not written. The harness refused a Write of a `.md` report file ("Subagents should return findings as text, not write report files"). I did not work around it with a shell write. The full report is below, and you can paste it into `REPORT.md`.

`knobs.json` is written (36 entries). So are two evidence files from read-only reads of the installed `db.pack` today (`_kv_rules` rows, unit and flyer masses):
- `D:/Projects/.worktrees/wh3-flyer-dive/brace-physics-1120/knobs.json`
- `D:/Projects/.worktrees/wh3-flyer-dive/brace-physics-1120/evidence_kv_rules_and_unit_masses.json`
- `D:/Projects/.worktrees/wh3-flyer-dive/brace-physics-1120/evidence_flyer_and_defence_masses.json`

Nothing in the repository or the game was touched. Addresses are as the repository records them for exe 9.0.5 (`6ae2a00b`); I did not read the exe myself. HISTORY sections are cited by name because I did not line-check the HISTORY numbers.

# A. Knobs

**Brace and push, `_kv_rules`.** Values read from the installed `db.pack`; none is shipped by the mod today.

| Key | Vanilla |
|---|---|
| `bracing_calibration_ranks` | 8 |
| `bracing_calibration_ranks_multiplier` | 4 |
| `bracing_max_multiplier_clamp` | 10 |
| `bracing_charge_reflector_bonus` | 2 |
| `bracing_immovable_by_small_entity_mass` | 600 |
| `bracing_attack_angle` | 80 |
| `unit_braced_status_threshold` | 0.75 |
| `collision_speed_delta_threshold_knocked_flying / down / back / step_back` | 10.5 / 7 / 4 / 3 |
| `collision_damage_maximum / modifier / normaliser` | 70 / 0.6 / 0.8 |

- **The ×2 term.** `bracing_charge_reflector_bonus` is very probably the SPEC's ×2 for `charge_defense`. The name and value match, and the UI calls `charge_defense` "charge_reflector". This is unverified; no record ties the key to the term by address.
- **The 600 threshold.** It applies to small pushers only, so it does not touch medium or larger flyers.
- **The multiplier site.** The multiplier is stored per soldier at entity `+0xbc` (`0x143090af9`). The test `test_bracing_update_reads_no_enemy` pins that it does not depend on who charges. So a change there hits every charger, not just flyers.
- **Not recorded.** The offsets of the `bracing_*` values, the formula and the cap order, the collision tier table address, and the kv object's runtime address.

**Reflection damage.**
- `charge_reflect_damage_multiplier` is 2 (kv object `+0x6670`), applied at `0x142e600af` (`mulss xmm8,xmm7`).
- `charge_reflect_min_charge_factor_threshold` is 0.7. `bracing_attack_angle` is 80, and the damage calculator's use of it is not recorded.
- In game the ×2 hit the braced soldier's ordinary attack on the charger: 151 times against knights and 58 against flyers, always 2.0.
- The four `impact_reflection_*` values have no recorded effect. That path (`0x1430afae4`) never fired in any recorded game, including the cavalry control.

**Flyer-only data the mod already ships.**
- Mass cut: large ×0.85, very large ×0.75, read in battle at `+0xb4` (star dragon 4425).
- `deceleration` is 30.
- `collision_attack_max_targets` (stage B).
- Stage C `dealt_collision_knocked_*` multipliers exist but are not shipped.

**Mod constants.**
- `SKIP_SPEED` is 2.0 m/s in a buffer word (+16) that Lua already writes at arm. It is runtime-writable.
- `SLIDE_RELEASE_M` (20 m) and `COMMIT_M` (5 m) are immediates in the caves, so build-time only.
- The D15 share (3%) is pure Lua at `dive_cost.lua:152-155`.

# B. Why bracing barely stops a big flyer today

**What removes the vanilla stop.**
- The vanilla stop is a contact → melee-order switch followed by a brake at deceleration 30, whatever the mass. A vanilla flyer without the caves travels 0.0 m and stops at touchdown in 18/18 runs.
- `dv_contact` holds the switch while the flyer is landed, in flight movement and above `SKIP_SPEED`, within 20 m. Early stops on spear and halberd lanes: 21/78 → 9/78.
- `dv_through`, `dv_keep`, `dv_skip`, the re-path caves and `dv_settle` keep the speed at all. The bounce was seen only in a prototype that did not use the holds.

**What is then too weak.**

Braced soldiers: Empire spearmen and halberdiers have entity mass 100, High Elf spearmen 150, Longbeards 200.

| Flyer body (after cut) | Mass |
|---|---|
| Pegasus | 1300 |
| Manticore | 1700 |
| Griffon | 1725 |
| Wyvern | 2250 |
| Sun dragon | 3000 |
| Star dragon | 4425 |

- At the measured maximum multiplier of 5.43 a spearman is 543. At the cap of 10 it is 1,000, below every flyer including the pegasus.
- Stopping the cut star dragon needs about ×44. This is arithmetic under an unverified one-soldier-versus-one-body model, and that model is not recorded.
- Recorded dive: the star dragon slid about 19 m and lost 0 health in the slide.
- The mass cut doubled early stops, 8/120 → 16/120 (p = 0.131); for the celestial lion 1/16 → 8/16 (p = 0.0155).

**Is the hold a "conditional check that forces an outcome"? No decision.**
- Yes:
  - The "keeps going" result comes from a flyer-state, speed and 20 m test, not from comparing the two bodies.
  - `dv_through` picks a different engine branch for flyers.
  - The D15 cost caves are an explicit condition set.
- No:
  - None of the holds looks at the target's type, braced state or mass.
  - Anything below 2 m/s falls back to the vanilla engage and brake.
  - Vanilla ground cavalry stop first by collision and engage 0.4–0.8 s later; the holds give flyers that same order of events.

# C. Designs

1. **Heavier bracing.**
   - Touches: kv `bracing_charge_reflector_bonus`, `bracing_calibration_ranks_multiplier` and `bracing_max_multiplier_clamp`, or a new cave at `0x143090af9` scaling `+0xbc`.
   - Side effect: global to all chargers and the AI. Stopping pegasus-class flyers needs more than 13×. The cap is not the active limit today, since the measured maximum is 5.43.
   - D15: stays at 3%, or goes to 10% in script.
   - Measure: front-rank `+0xbc`, penetration depth, early stops, and a knights-into-spears control.
2. **Stronger reflection.**
   - Touches: kv `charge_reflect_damage_multiplier`, or a cave at `0x142e600af`.
   - Side effect: global, hitting every cavalry charge into spears. A flyer-only variant is not available from the records, because attacker identity at that site is unverified.
   - It cannot deliver 10% alone. D15-ANALYSIS arithmetic (not measured) gives 5-second star dragon loss of 1.16% at ×2, 3.2% at ×8 and 5.9% at ×16, against 10.09%, 35% and 68% for the manticore. My extrapolation puts 10% for the star dragon near ×28, where the manticore is far past dead.
   - The star dragon's doubled hits came after the dive, not at contact.
   - D15: keep the script at 10%, or pair it with a moderate multiplier.
   - Measure: per-hit damage via the existing `rf_cgate` / `rf_cmul` ring, plus the knights control.
3. **Raise `SKIP_SPEED`.**
   - Once collisions slow the flyer below V, the engine contact stop and its 30 m/s² brake apply again.
   - Touches: only the buffer word at +16. No DB or kv change.
   - Side effect: flyers only, but every landed dive against any target ends earlier. The stop is abrupt, about 0.2 s from 6 m/s. Early-stop data exists only for V = 2.
   - D15: independent.
   - Measure: V in {2, 4, 6, 8}, depth at stop, release speed, early stops, and a militia control.
4. **Deeper flyer-only mass cut.**
   - Touches: `MASS_FACTOR`.
   - Side effect: none on ground units, but flyers hit lighter and stop more. It cannot be an MCT setting, since DB values are fixed at load.
   - D15: independent.
   - Measure: early stops and the impact table.

Options 3 plus the scripted deduction need no vanilla value changed and no unrecorded address. Options 1 and 2 are global balance changes the owner should be told about before any default is set.

# D. MCT

**What exists.**
- One MCT option exists today, a checkbox. Numeric MCT types (slider, dropdown) are not used anywhere in this repository, so they are unverified here.
- The caves already take tuning from Lua through a buffer: `SKIP_SPEED`, the front-arc switch, and the takeoff pin table.
- All recorded writes target a `game_alloc` buffer. No write to other engine memory is recorded.

**What can be written.**
- **New caves.** Scaling the reflection factor (`0x142e600af`) or the bracing multiplier (`0x143090af9`) by a buffer value works exactly like `SKIP_SPEED`, and the evidence supports it. Each needs an emulator check and an agreement marker bump.
- **kv memory.** Writing the kv object directly needs the object address, the `bracing_*` offsets, and proof that memreader Plus can write engine memory. None is recorded.
- **kv rows in the pack.** These are fixed at load and are not MCT-tunable. `flyer_db_schemas.json` has no `_kv_rules_tables` schema. A test pack once shipped a `_kv_rules` row (`break_off_ignore_collision_time`), but its writer is not in this repository.
- **Pure Lua.** The share scales in `dive_cost.lua` with no engine write, and the keep floor must rise with it.

**Settings I would expose.**

| Name | Range | Default |
|---|---|---|
| `dive_cost_percent` | 0–25 | 10 (owner's choice) |
| master switch | on / off | on |
| `brace_strength` | 1.0–4.0 | 1.0 until the owner gives a number |
| `reflection_strength` | 1.0–4.0 | 1.0 until the owner gives a number |
| `release_speed` | 1–10 m/s | 2 |

The owner gave no numbers for the physics items, so those defaults need his decision.

**Multiplayer (D14).**
- A multiplayer campaign battle follows the host's settings.
- A multiplayer battle outside a campaign must arm the caves with the shipped defaults, because the cave values run in the lockstep simulation and differing values would diverge movement.
- Whether `reduce_hitpoints_unary` applies identically on two machines is unverified, and no two-player battle was ever run.

# E. Unknowns, most design-changing first

1. The bracing multiplier's formula, term order and which term is the active limit. The research doc cites a `static_notes` file that is not in this repository.
2. How the pairwise collision uses mass and `+0xbc`: per soldier, summed, or as a ratio.
3. Whether memreader Plus can write engine memory outside its own buffer, and where the kv object lives.
4. Reflection is driven by hit count, so it cannot give "10% per contact", and one multiplier cannot suit both a star dragon and a manticore.
5. Whether the impact-reflection path is pike-only and whether its four values do anything.
6. Behaviour at `SKIP_SPEED` above 2: abruptness, animation, early-stop rate.
7. Global side effects on ground cavalry and the AI, other mods' `_kv_rules` rows, and the missing write schema.
8. The mass cut already does part of the stopping, so any new strength stacks on it and moves the 8/120 and 16/120 baselines.
9. 10% for multi-model flyers breaks the 3% assumptions in the keep floor and call cap. Pay counts recorded were 2–6 models per dive, and the front-arc refusal has never been seen in game.
10. The mass table assumes `battle_entities.mass` is the mass the engine uses. That is supported by the `+0xb4` read, and ridden flyers use the mount's mass.

Two small gaps:
- The ×5.43 maximum comes from the research doc, and its run folder is not in the repo.
- I did not re-check any exe signatures.

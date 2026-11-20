# 2026-11-20-brace-collision-reading

> 来源：只读的离线车道（静态读 `Warhammer3.exe` 9.0.5 与游戏数据，没开游戏），2026-11-20，由主模组仓库的会话派出；原件与脚本、反汇编在仓库外的 `D:/Projects/.worktrees/wh3-flyer-dive/brace-collision-1120/`。离线读碰撞代码的第一份报告。主管逐行重读过的部分与补做的普查记在 `docs/HISTORY.md` BRACE-READ-1120；其余是车道自己的读法，没有复核。报告里「飞兽在配对处理里被体型差、质量和标志位挡住」这一句，被第二份报告否定。
> 车道的报告是英文原文，一字未改。

---

# Report: where the brace value is used, and what a flyer-only cave can reach

I read the executable statically. No game was started, nothing in the repository or game folder was changed, and I wrote only inside the lane folder.

- **Build check.** `Warhammer3.exe` has PE TimeDateStamp `0x6ae2a00b`, which is the recorded `6ae2a00b`. I ran `dive_cave_asm.py --check-exe` and all 11 repository sites matched exactly once. `keystone` and `unicorn` are not installed, so I assembled no cave and ran no emulator check.
- **Headline result.** The value at entity `+0xbc` does not drive the flyer's deceleration in any code I read. Its only collision-path reader is the collision damage formula. Its only other effect is the "immovable by small entity" bit. The proposal in D is built exactly as you asked, but it will most likely change how much damage a diving flyer deals to a braced soldier, not whether the flyer stops.
- **Citation convention.** Offsets for the kv rules object are *value offsets*: the loader's struct offset plus `0x60`. Evidence file names below are in `brace-collision-1120/`.

## A. Where the brace value is used

**Writer, the brace update.** The function starts at `0x1430907e0`; `rbx` is the model entity and `r10` is its unit at entity `+0x2e8` (`d_brace_update_fn.txt`).
- **Gate.** The function runs only if entity `+0x108` has bit `0x10`, entity `+0x2e0` is 0 (not ridden), and unit `+0x3d1c` bit `0x10` is clear.
- **Reset.** If none of unit attributes 3, 4 or `0x27` is present (and `[unit+0x50]+0x1d1` is 0), the multiplier resets to 1.0. That happens at `0x14309088f` and `0x143090b15`.
- **Formula, in order.**
  1. Rank term: `1 + clamp01((ranks-1)/(kv[+0x10b8]-1)) * (kv[+0x1120]-1)`. The two kv values are `bracing_calibration_ranks` and `bracing_calibration_ranks_multiplier`.
  2. Multiplied by a unit-level factor (see B).
  3. Multiplied by `kv[+0x1188]` (`bracing_charge_reflector_bonus`) if attribute 3 or 4 is present. The repository's SPEC names these charge_defense and charge_defense_vs_large; I did not re-read the id-to-name mapping.
  4. Clamped: below 1.0 becomes 1.0, otherwise `min(kv[+0x1258], value)`. The clamp key is `bracing_max_multiplier_clamp`.
- **Stores.** `0x143090af9` writes the result to `+0xbc`, and `0x143090b02` writes its inverse to `+0xc0`.
- **The 600 rule.** At `0x143090aca` through `0x143090aeb`, `result × entity[+0xb4]` is compared with `kv[+0x11f0]` (`bracing_immovable_by_small_entity_mass`). If it is at least that, bit 16 of entity `+0x6c` is set (`bts [rbx+0x6c],0x10`).
- **Offset proof.** I derived every kv offset from the loader at `0x1405c02e0`. Each key's `lea rcx,[rsi+X]` plus `0x60` equals the offset the engine reads. For `bracing_attack_angle`, X is `0xff0` and the engine reads `+0x1050` at `0x14307c556`, which the repository's `test_d15_stage5.py` also pins. The full table is in `kv_offsets.json`.
- **Check constants.** The "1.0" in the formula is the float at `0x14392dcc8`, which I read as 1.0. The mass-ratio threshold at `0x14392dcc4` is 0.0.

**Reader R1, the only float read of `+0xbc` in the collision path: `0x142e3f3c6`, `mulss xmm6,[rax+0xbc]`.** It sits in the function at `0x142e3f2f8` (`d_fn_142e3f2f8.txt`).
- **Which function.** This is the collision damage calculation. It reads `kv+0x1530`, `+0x1598`, `+0x1600` and `+0x1668`, which are `collision_damage_normaliser`, `_modifier`, `_armour_penetration_ratio` and `_maximum`.
- **Bodies.**
  - `rdi` = participant B, the receiver. `rsi` = participant A, the other body.
  - Both are objects with vtable `0x143ae0278`. Slot 1 is `mov rax,[rcx+8]`, which returns the entity (`d_vtable_143ae0278.txt`, `d_vslots_damage.txt`).
  - A's entity is `[rsi+8]`; B's entity is returned in `rax`.
- **Computation.**
  1. `xmm8` is A's mass (`[A_entity+0xb4]`); `xmm6` is B's mass.
  2. If `bl` is set, `xmm6 ×= [B_entity+0xbc]` at the reader. `bl` is set only when B is braced and the front-arc boolean passed in at `[rsp+0xf8]` is true.
  3. The braced test is vtable slot 10, `0x1408fc020`, which reads entity `+0x68` bit 3. The boolean comes from the driver `0x142e3f5cc`, which tests whether A is in front of B by B's facing.
  4. Then `xmm8 = massA / xmm6` if `xmm6 > 0.0`, otherwise 0.
  5. That ratio is multiplied by the relative speed `|vA − vB|`.
- **Call chain.** `0x143061144` (per-mover update) calls `0x1430ad710` at `0x143061921`, which calls `0x142e3f5cc`, which calls `0x142e3f2f8` at `0x142e3f713`.
  - At `0x143061921`, `r8` is the neighbour entity (A) and `r9` is the updating entity (B).
  - `0x143061144` runs its neighbour loop only if the mover's speed squared is at least `kv[+0x1c80]` squared (`collision_speed_delta_threshold_step_back`).
  - A bounded crawl from `0x143061144` (depth 4, 216 functions) and from `0x143060e44` (depth 4, 227 functions) reached R1 and no other `+0xbc` float read. From `0x1430731c8` (depth 3, 143 functions) it found none. The crawl follows direct calls only; virtual calls are not followed.

**Consumers of the derived bit 16**, which is where the stored value reaches the push logic:
- Pairwise collision `0x1430731c8`, at `0x143073439` through `0x143073487` (and the mirror at `0x1430734a9`). It tests bit 16 with `test r13d(0x10000)`. If the other body is in another unit and the other body's size tier `[+0x74]` is at most 1, it sets `byte [rdi+0x1b0]=1`.
- Pair resolution `0x142f8c6f4`, at `0x142f8c838` (`bt ecx,0x10`). It also uses bits `0xf`, `0x13` and `0x16`, and the tier at `+0x74`.
- The pair-priority function `0x142f95da0` compares raw masses at `+0xb4`, at `0x142f95f73` and `0x142f95fea`, with no brace term. I did not establish which of its two bodies is which.

**What I could not prove.** There are about 108 float reads of `+0xbc` between `0x142d00000` and `0x143400000` (`d_scan_bc_143.txt` covers `0x143…`). Many belong to other classes: `0x143119c88` and `0x142fda7ec` are transform matrices. I cannot prove every one is non-entity. The whole-image census is incomplete. Beyond that, no reader of the inverse at `+0xc0` was found in the trees I crawled.

## B. Where `scalar_bracing` enters

How far I got:
- **Name and id.** The string `scalar_bracing` is at `0x143759018` in the `.debug` section. A static initializer at `0x14014f4cc` through `0x14014f4e4` registers it as stat enum id 42 (`0x2a`), in a global at `0x143df45b8`. `d_stat_enum_ids.txt` lists the whole enum; `stat_mass` is 61. The enum table is 82 entries of stride `0x18` from `0x143df41e0`, searched by id at `0x141445ecc`.
- **No code reader of the id.** Only the initializer touches that global, so ids reach the unit by immediates or computation that I did not trace. I did not find the unit-level field where the stat total is stored.
- **The candidate, not proven.** The brace update reads three unit-level floats at `0x14309096c`, `0x143090974` and `0x14309097c`: `xmm8 = max(unit[+0x3934] + unit[+0x3938], unit[+0x393c])`.
  - They are the only unit-level floats read before the rank term, and the result feeds the multiplier directly.
  - I could not tie them to `scalar_bracing`. `+0x3934` is also read at about 50 other sites. One example is `0x1405ab2fa`, where it is added when a speed exceeds the threshold at `+0x391c`, which looks like a different stat.
- **If those fields are the stat**, the order proven above applies. The stat multiplies the rank term, then the ×2 attribute bonus, then the clamp. The clamp, the `bracing_max_multiplier_clamp` kv value, is the ceiling for the stat's contribution.
- **Hard negative.** Ids 3 and 4 are attributes, not stats, in the code I read; `mov edx,0x2a` sites such as `0x143075e39` are attribute `0x2a` tests. Do not confuse the two.

## C. Can the charger be identified at that site

Yes, at R1 (`0x142e3f3c6`).
- **The other body.** `rsi` is A, and its entity is `[rsi+8]`. A cave should first check `[rsi] == 0x143ae0278`, the vtable written by the constructor `0x1430a2b78`, and otherwise leave the value untouched. That avoids calling a virtual function from the cave.
- **Flyer and landed-dive test.** The existing caves already test this on an entity:
  - `mov r11,[ent+0x2e0]; test; cmovne` for a ridden flyer.
  - `[r11+0x128]` non-null (flight controller).
  - `[r11+0x104] == 0` (landed).
  - `[r11+0x710] != 0` (flight movement).
  - `_fast_test`: planar velocity at `+0xe0`/`+0xe8` squared above `SKIP_SPEED²`, with state 30 or 33 (or state 0 on the ground).
- **Cheapest safe test.** Flight controller plus `+0x104 == 0` plus `+0x710 != 0`, read through the mount if ridden. The engine reaches "landed but still in flight movement" only in a landed dive, so no speed test is needed.
- **Adding the speed test.** Using `xmm0` and `xmm1` costs about eight instructions. It matches what `dv_contact` does and costs no more safety.
- **Which body is the charger.** `bl != 0` already means A is in front of B within the facing test, so no further front-arc check is needed.

## D. Cave design (not built)

**Hook.** Address `0x142e3f3c6`. Stolen bytes: `F3 0F 59 B0 BC 00 00 00`. Pattern: `F3 0F 59 B0 BC 00 00 00 0F 2F 35 ?? ?? ?? ?? 76 07 F3 44 0F 5E C6 EB 04 45 0F 57 C0`. It matches exactly once (`sigcount.py`).
- **Resume.** `0x142e3f3ce`, the `comiss`.
- **Patch size.** The site is 8 bytes. Existing caves steal 7 to 10 bytes (`dv_skip` 7, `dv_keep` 8, `dv_through` 9). The memreader Plus minimum patch size is not verified.

**Registers.**
- **Live at the site.** `rax` (B's entity), `rdi`, `rsi`, `xmm6`, `xmm8`, `bl`, `r14` (kv rules).
- **Free.** From the instructions after the site, the volatile registers (`rcx`, `rdx`, `r8` to `r11`, `xmm0`, `xmm1`) and flags are dead there.
- **Recommendation.** Save and restore `r10`, `r11`, `rcx` and `xmm0`/`xmm1` anyway, as the other caves do (`pushfq` plus pushes), so the cave never depends on liveness I read by hand.

**Cave body.**
1. Redo the original `mulss xmm6,[rax+0xbc]`.
2. `mov r10, BUF`; require `[r10+MODE_AT] == 1`, else resume.
3. Require `[rsi] == 0x143ae0278`, load `r11 = [rsi+8]`, and follow the mount via `+0x2e0`.
4. Apply the flyer test: `[+0x128]` non-null, `[+0x104] == 0`, `[+0x710] != 0`, and optionally `_fast_test`.
5. Read the factor from `[r10+BRACE_F_AT]`. If its bits equal `0x3F800000`, resume untouched. Otherwise `mulss xmm6,[r10+BRACE_F_AT]`.
6. Resume.

**The factor.**
- **Buffer.** It lives in the buffer Lua writes, like `SKIP_SPEED` at `+16`. The buffer layout has no free word below `+64`; counters occupy `+20` to `+60` and the slide table starts at `+64`. A new word goes at `+4160` (`BUFFER_BYTES` grows), and the buffer magic `FLYDIVE3` should change too. Per `CLAUDE.md`, the multiplayer marker must also change, and MCT settings follow the host (D14).
- **Factor 1.0.** The compare against `0x3F800000` skips the multiply, so every path is byte-for-byte vanilla. The `mulss` by 1.0 would also be exact in IEEE float.

**Emulator checks (Unicorn plus Keystone, neither installed here).**
- *Positive:* a landed fast flyer A against braced B gives `xmm6 == vanilla × f`.
- *Negative controls:*
  - A ground charger (flight controller null, own and via mount) leaves `xmm6` identical to vanilla.
  - A flyer in the air (`+0x104 != 0`).
  - A flyer on the ground in ground movement (`+0x710 == 0`).
  - A slow flyer.
  - Mode 0.
  - A bad vptr.
  - A null A entity.
  - Factor 1.0 on every case.
- *Mutants:*
  - Drop the flight-controller test.
  - Drop the landed test.
  - Flip the bit compare.
  - Wrong displacement.
  - Wrong register.
- *Other checks:* register and flag preservation, and a ridden-flyer positive.

**What this does and does not do (important).** At R1 the multiplier raises B's effective mass, so `massA / (massB × brace × f)` falls. That lowers the collision damage the diving flyer deals to the braced soldiers. The records and my reading give no evidence that the flyer's deceleration depends on it. The 600 rule applies only when the other body's tier `[+0x74]` is at most 1, so it does not touch large flyers. The flyer's stop in the pair-resolution code is decided by tier differences, raw mass at `+0xb4` and flags.

## E. The reflection site `0x142e600af`

Yes, the target is reachable. The function is the melee damage calculation at `0x142e5fcb0` (`d_fn_142e5fcb0_damage.txt`).
- **Roles.** `rdi` is the target participant, the charger being hit. `rbx` is the attacker participant, the braced soldier. Both use vtable `0x143ae0278`.
- **The block `0x142e6004c` through `0x142e600af`.**
  - `xmm7 = [r12+0x6670]` (`charge_reflect_damage_multiplier`).
  - Gates: `[rdi]` vfunc `+0x48`, `[rbx]` vfunc `+0x38` (attribute `0x27`, per `0x1430b7a61`), `[rdi]` vfunc `+8` entity non-null, and `[rbx]` vfunc `+0x50` (braced).
  - Then `0x143065f3c(rdi's entity)` must be at least `[r12+0x66d8]` (`charge_reflect_min_charge_factor_threshold`, 0.7).
  - The site is `mulss xmm8,xmm7`, bytes `F3 44 0F 59 C7`, unique by signature `F3 44 0F 59 C7 40 84 ED 74 12 48 8B 07 48 8B CF FF 50 08`.
- **Where the target is.** `rdi` is callee-saved and still live there. The target entity is `[rdi+8]`, valid when `[rdi] == 0x143ae0278`. The repository's HISTORY records (docs/HISTORY.md:1993) matched "charger = `[rdi+8]`, braced = `[rbx+8]`" by pointer in game, and this confirms it statically.
- **Second factor design.**
  - Steal 8 bytes (`F3 44 0F 59 C7 40 84 ED`, the `mulss` plus `test bpl,bpl`); the cave redoes the `test` and resumes at `0x142e600b7`, just before the `je`.
  - After the original `mulss`, apply the same flyer-in-landed-dive test to `[rdi+8]`. If it is a flyer, `mulss xmm8,[r10+REFL_F_AT]`; otherwise leave it.
  - `xmm0` and `xmm1` are free there. `xmm6` and `xmm7` are dead after the site and `xmm8` is live.
- **Caveat from the records.** The multiplier acts per hit and not per contact. The records' arithmetic (`docs/HISTORY.md` D15-ANALYSIS) says it cannot deliver a 10% loss for every flyer size from one factor. I did not re-derive that.

## F. What remains unknown, and the measurement that would close it

1. **What actually decelerates the diving flyer once the holds let it through.** Not read. The pair-resolution functions `0x142f8c6f4` and `0x142f95da0` are the candidates; I read only parts. In game: log each tick the flyer's speed, the pair-resolution result for the flyer and soldier, and `[+0x74]` of both. That is a passive probe, with no state change.
2. **Whether R1 affects the flyer at all.** Log `xmm6`, `xmm8` and `bl` at `0x142e3f3c6` for flyer pairs, with and without braced soldiers. Check whether the damage result at `[rsi+4]` changes with a test factor.
3. **The unit-level field behind `scalar_bracing`.** Read unit `+0x3934`, `+0x3938`, `+0x393c` on a braced soldier's unit with and without Glamour of Hoeth (×3) or defensive stance (×1.25), and compare with entity `+0xbc` before and after.
4. **Who reads `+0xc0`.** Not found in the crawled trees. A whole-class write-access census would answer it.
5. **Roles in `0x142f95da0`.** Which of `rdi` and `r14` is the pusher.
6. **Virtual and indirect readers.** The census follows direct calls only, so readers behind virtual calls (for example vtable `+0x4b0`) are not covered.
7. **The memreader Plus minimum patch size** for an 8-byte site.
8. **The emulator and cave assembly.** None of D's bytes were assembled or run, because `keystone` and `unicorn` are missing.

## Files written

All in `D:/Projects/.worktrees/wh3-flyer-dive/brace-collision-1120/`:
- `sites.json` (29 sites, bytes read live from the exe) and `kv_offsets.json`.
- Disassembly dumps: `d_brace_update_fn.txt`, `d_fn_142e3f2f8.txt`, `d_fn_142e3f5cc.txt`, `d_fn_1430ad710.txt`, `d_fn_143060e44.txt`, `d_pairwise_1430731c8.txt`, `d_fn_142e5fcb0_damage.txt`, `d_fn_142f8c6f4.txt`, `d_fn_142f95da0.txt`, `d_kv_loader_bracing.txt`, `d_vtable_143ae0278.txt`, `d_vslots_damage.txt`, `d_scan_bc_143.txt`, `d_stat_enum_ids.txt`.
- Helper scripts: `exedis.py`, `func.py`, `crawl.py`, `dispscan.py`, `readers.py`, `nearpair.py`, `sigcount.py`, `kvmap.py`, `statenum.py`, `strscan.py`, `ptrscan.py`, `refscan.py`, `refrange.py`, `callers.py`, `flagscan.py`, `consts.py`, `vt.py`, `pads.py`, `mk_sites.py`.

# 2026-11-20-brace-response-reading

> 来源：只读的离线车道（静态读 `Warhammer3.exe` 9.0.5 与游戏数据，没开游戏），2026-11-20，由主模组仓库的会话派出；原件与脚本、反汇编在仓库外的 `D:/Projects/.worktrees/wh3-flyer-dive/brace-response-1120/`。离线读「大体型撞进人堆后怎么减速」的报告，2026-11-20 16:02 回来。**主管一条都没有复核**（回来后四分钟主人就下令交接）；接手的会话要自己重读它点到的地址再用。
> 车道的报告是英文原文，一字未改。

---

I did not find any code that slows or stops a large body by the mass of the small bodies it hits. Mass does decide three things, and none of them touches the large body's velocity. So there is no spot where "mass × brace" can be dropped in to make braced spearmen physically stop a flyer. This was static reading of `Warhammer3.exe` only, nothing run. It reached the engine's mass formulas but not what applies the result to the pusher, so "not found" is not "proven absent". Files are in `D:/Projects/.worktrees/wh3-flyer-dive/brace-response-1120/`.

## 1. The response step

**What mass does decide (READ):**

1. **Collision damage.** `0x142e3f2f8` is the damage formula, which the supervisor already finished.
2. **Knockback severity of the struck body.** `0x142f8d520` computes `(K + c) · m1 · v / (m1 + m2)` (READ `0x142f8d520`..`0x142f8d55b`).
   - It is the classic elastic-impulse formula. `K` is 1.0 at `0x14392dcc8`; it returns 0 if `m1+m2 < 1.19e-7`.
   - It is called from seven sites: `0x143072c97`, `0x14308315c`, `0x143087153`, `0x1430ab15b`, `0x1430adfac`, `0x14325b7ad` and `0x14326d02f`. I read four of them.
   - At `0x143082fd0` (call at `0x14308315c`) the roles are READ:
     - `m1` is the attacker's mass times the attacker unit's stat `max(unit[+0x39d0]+unit[+0x39d4], unit[+0x39d8])` (`0x143083129`..`0x143083141`).
     - `m2` is the struck body's raw `[+0xb4]` (`0x143083149`).
     - The result goes into `0x14305d4fc`, which looks up a reaction on the struck body from an animation table.
   - At `0x1430adef8` (call at `0x1430adfac`) the impulse is compared with four `kv` thresholds (`+0x5288`, `+0x52f0`, `+0x5358`, `+0x53c0`) to pick a reaction level 0 to 5. Its `m2` is `[rsi+0xb4]` (`0x1430adf95`).
   - Nothing in these functions writes the pusher's velocity (READ for the first two).
3. **Pair priority.** This is `0x142f95da0`, described in section 3. Mass is only a floor and a tie-break there.

**The only velocity or position writes I found in the pair path** are in the order-change code (`0x14305dcac`, `0x143075dd8`, `0x14305abb4`). That is the known engage brake. I found no physical push that changes the pusher's velocity.

**Where bodies "cannot be pushed" and why a flyer is excluded (READ):**
- The mark is `mov byte [rdi+0x1b0], 1` at `0x143073480` for `rdi`, and `0x143073500` for `rsi`.
- A body skips the mark if it has bit 15, or bit 19, or the two flag words differ in bit 22. It also skips if it has bit 16 and the other body is in another unit with `tier <= 1` and `tier <= its own` (`0x143073449`..`0x143073467`).
- A large flyer has `tier >= 3`, so it never passes that test. The braced body is therefore marked like any other.
- Size tiers (small 1, medium 2, large 3, huge 4) come from the repo's `HISTORY.md:1552`. I did not re-measure them.

## 2. Does mass enter the stopping, and how

No for the stopping. In the three places above, mass appears as a ratio inside the damage formula, a ratio inside the knockback impulse, and a threshold plus tie-break in priority. The brace value `+0xbc` appears only in the damage formula, plus the bit 16 flag derived from it (brace × mass ≥ 600).

A correction to the previous lane: its REPORT.md says the flyer's stop in pair resolution "is decided by tier differences, raw mass at `+0xb4` and flags". I found no stop there. The masses are priority comparisons, which sit mostly in the yield mechanism below.

## 3. The two named functions

**`0x142f95da0(X=rcx, Y=rdx)` returns a bool: "X has priority over Y" (INFERRED name, READ structure).** Who calls it:
- `0x142f8cb24` calls it as `(A,B)` then `(B,A)` (`0x142f8cb74`, `0x142f8cb81`). If exactly one side has priority, it calls `0x142f8c8ec(mgr, loser, winner)`.
- `0x142f71ab0` does the same dance (`0x142f71ace`, `0x142f71ae5`).
- If `0x142f8c8ec` accepts, `0x142f7071c(mgr, loser, winner)` appends a record of both bodies' positions and facing to a pool at `mgr+0xd0`. Call this the yield list.
- The yield list is steering-avoidance bookkeeping, not an impulse. I did not find who consumes it. That is the largest hole.

The decision tree, READ at `0x142f95e21`..`0x142f96046` (the field and vtable-slot meanings are INFERRED):
- `X.vf270()` is true and `Y.vf270()` is false: X wins.
- Both true: X wins if `[X.vf88()+0xd98]` is non-zero, or if `X.+0x108` bit 4 is clear (`0x142f95f09`..`0x142f95f19`). Otherwise the larger tier wins, and on equal tiers the one with the smaller `[+0xa0]` loses.
- Neither is true: the one with `+0x108` bit 4 wins; if both have it and X's `[+0x4a8]` test fails and Y's passes, X wins if `X.mass / Y.mass > 0.1` (`0x142f95f73`..`0x142f95f8b`; 0.1 at `0x14392df14`).
- Otherwise, a moving body beats a stationary one. Between two stationary bodies in different units, X wins only if its tier is higher by 2 or more and `[X+0x23c] < 0.5`. In the same unit, a tier difference above 1 wins.
- The tie-break `Y.mass >= X.mass` (`0x142f95fea`) applies only when the tiers are equal.

Effect on the braced case: a flyer has a mass ratio far above 0.1 against a spearman, so it wins priority. Brace never enters. Raising the spearman's mass to 10× the flyer's is impossible within the brace cap.

**`0x142f8c6f4(mgr, B=rdx, A=r8)` returns a bool: "pair eligible for the soft-contact handling".** Its only caller is `0x143073673`, inside the pairwise function `0x1430731c8`. READ details:
- It requires `mgr.vf28` and `vf20` to accept both bodies, and `esi != 9` from `0x142f73784` or `0x142f73af8`.
- It then applies the same bit 15, 16, 19 and 22 tests. Every path ends in `|tier(A) − tier(B)| <= 1` (`0x142f8c8d3`..`0x142f8c8e6`), apart from a few early returns of 0.
- The caller (`0x143073678`) does `cmp al,1; jne 0x143073542`, which skips the rest of the pair work. So for flyer against infantry (tier difference ≥ 2) the pair is normally skipped on this branch.

## 4. Proposal (design only)

**No place exists where `mass B × brace B` replaces `mass B` and makes the flyer stop.** The three mass sites do not decelerate the pusher. The closest levers:

**Lever A: the brace flag, through the existing 600 rule. This is the only brace-dependent lever on the pusher.**
- The smallest place is the pusher-tier load `mov r8d,[rsi+0x74]; mov edx,[rsi+0x6c]` at `0x14307343c`.
  - Bytes are `44 8B 46 74 8B 56 6C`, 7 bytes, and the pattern is unique in the executable (`sites.json`).
  - The mirror is `0x1430734ac`, `44 8B 47 74 8B 57 6C`; I read its bytes but did not run a uniqueness scan on it.
- The cave redoes both loads. If `rsi` is a flyer in a landed dive, it sets `r8d = 1`.
  - Flyer test: `[+0x128] != 0`, `[+0x104] == 0`, `[+0x710] != 0`, reading through `[+0x2e0]` if ridden. This is what the existing caves use (`dive_cave_asm.py` lines 200 to 204).
- Live registers: `rdi`, `rsi`, `ecx` (loaded at `0x143073439`), `r15d = 1`, `r12d = 0`. `r8d` and `edx` are overwritten by the stolen loads, so the cave sets them. `rax` is free at `0x14307343c`; I did not trace the others.
- Effect: a braced body with brace × mass ≥ 600 stays unmarked against that flyer. The same tier gates are at `0x142f8c84e` and `0x142f8c886` in `0x142f8c6f4`.
- Limits:
  - It is a switch, not a tunable strength. The threshold is the global `kv` value, so a flyer-only strength is not possible this way.
  - A spearman reaches 600 only if his multiplier is at least 6 (Empire spearmen 100 × 6).
  - Whether skipping the mark stops the flyer is not proven (see unknowns).

**Lever B: make the struck body's mass count the brace in the knockback severity.**
- The place is `movss xmm3,[rsi+0xb4]` at `0x1430adf95`, and the same for the other callers (`0x143083149`, `0x143087129`, `0x143072c64`).
- It would keep braced soldiers from being knocked down. The history shows upright soldiers are what trigger the engage brake, so this may be counterproductive. I did not verify that.

**Lever C: the flyer's own order.** This is the engine's real brake: the melee order at `0x14305dcac` / `0x143075dd8` with `deceleration`. The repo's existing caves (`dv_contact` and the others) hold that off. A tunable stopping rule would have to be added there, which the owner has said he does not want as a "condition".

## 5. Unknowns and passive probes

All probes log only and change no state.

1. **What the `+0x1b0` mark does to a body** (set at `0x143073480` and `0x143073500`; read at `0x14307e54b` and `0x14307e71d`, where it appears to feed `+0x710`; also `0x143062c49` and `0x143121d6d`). Probe: for flyer-versus-braced pairs, log `[+0x1b0]`, `[+0x710]` and speed for both bodies each tick.
2. **Who reads the yield list at `mgr+0xd0`.** Probe: log records appended at `0x142f7071c`, with loser, winner, tiers and masses, and check whether the flyer is ever the loser.
3. **Whether Lever A would stop anything.** Probe: log the bit 16 flag on braced bodies at `0x143073449` and the cave's would-be override, without applying it. A second useful reading is whether `0x142f8c6f4` returns 0 for flyer versus infantry (`0x143073678`).
4. **What bits 15, 19, 22 and the vtable slots `+0x28`, `+0x248`, `+0x250`, `+0x260`, `+0x270` mean.** They are INFERRED only. Probe: log the flags and slot results for a flyer, a spearman and a cavalry body.
5. **What removes flyer speed inside an enemy block** (13 of 78 dives in the history were slowed within 20 m). Probe: log the flyer's speed, `+0x23c`, `+0x180` and `+0x394` against distance in the block.
6. **The other three impulse callers** (`0x1430ab15b`, `0x14325b7ad`, `0x14326d02f`). Not read. I did not confirm whether any of them recoils the attacker; the four I read do not.
7. **Virtual-call readers.** The census follows direct calls only, so other users of the brace multiplier could hide behind vtable calls.

Files in `D:/Projects/.worktrees/wh3-flyer-dive/brace-response-1120/`: `sites.json` (28 sites with bytes read live, plus the uniqueness result for the tier-load pattern), the scripts `stores.py`, `fnat.py`, `fnstart.py` and `mk_sites.py`, and the dumps `d_fn_*.txt` for `0x143082fd0`, `0x14325b54c`, `0x14306287c`, `0x14307e438` and others.

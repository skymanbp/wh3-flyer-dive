# Decisions

Rulings by the mod's owner, newest last. A ruling is quoted in the owner's own words where one
was given. An entry marked *assessment* is the maintainer's answer to a question the owner
asked, not a ruling; it stands until the owner says otherwise. Decisions made before this file existed are in the Lore Disasters repository,
`docs/CONTENT_LEDGER.md`: §C8-57 and §C8-58 (take-off from melee), §C8-78 (single-model window),
§C8-88 (this mod developed on its own), and the batch records §C11 AIR-DIVE-* and FLYER-*.

Research behind the 2026-11-17 rulings: `docs/research/2026-11-17-next-version-design.md`.

## 2026-11-17

### D1 · Balance changes move to an optional submod

> 「这次把submod也做了，把接战中吐息和质量调整之类的平衡调整挪出来，单独作为一个submod发布。」
> Asked what exactly moves: 「只挪吐息和质量」.

- The main pack keeps the dive, the take-off rule, the per-flyer charge speeds and the
  collision attack.
- Two things leave it for the submod `flyer_dive_balance.pack`: breath attacks usable while
  engaged in melee, and the mass cut for large (×0.85) and very large (×0.75) flyers, with its
  exceptions (the celestial-lion override, the machine bodies left untouched).
- The submod requires the main mod. Both packs come out of one build run so they cannot disagree.

### D2 · Workshop pages carry one language per page version

> 「steam创意工坊是可以分开做中文/英文（不同语言）版本的。不用在同一个页面做两个版本。」

Each Workshop item gets a separate title and description per language (English, Simplified
Chinese). The texts are kept in `workshop/<item>/<language>/`.

### D3 · Take-off from melee: per model, by body size

> 「对于起飞，我们可以按照体型进行分档，不同体型起飞所需的"未被击中"时间改成不同的。」
> On the direction: 「越小等越久」. On multi-model units: 「按照单个兵模来算，这个兵模xx秒内被攻击击中就不能起飞。具体时间看上一条」.

One rule replaces the two earlier ones ("more than half of the living models struck within
1.5 s", and "the last living model struck within 3.0 s"):

**A flying model that was hit by a melee attack within the last N seconds cannot take off.**

| body size | N |
|---|---|
| very large | 3.0 s |
| large | 3.5 s |
| medium | 4.0 s |
| small | 4.5 s |

- Decided for each model on its own: in a unit of many models, the ones struck recently stay
  down and the others may lift off.
- Unchanged: only melee hits count; every flying unit, both sides, AI included; multiplayer
  through the same agreement. A ridden unit uses its mount's body size.
- Why this direction: the game's own data makes small bodies the easiest to interrupt
  (median chance to ignore a hit reaction: small 0 %, medium 25 %, large 50 %, very large 70 %),
  and no size becomes easier to pull out than it is today (3.0 s).
- Why per model: in the recorded fights a 24-model unit was never held under the old rule at any
  window up to 6 s, because at most 17–45 % of its models were struck at once.

### D4 · A dive into braced spears hurts the flyer, and does not stop it

> 「趁着这次更新，把这个impact damage to flyers也做了吧。」 Asked which form: 「照冲，但受伤」.

- A flyer that dives head-on into braced infantry carrying the game's `charge_reflection`
  attribute (136 units, spears and halberds for the most part) takes one reflection hit.
- **The hit is twice the game's own reflection damage** (owner, later the same night:
  「提高飞行部队受伤数值，让冲锋反制对飞行单位的威胁提高。可以直接翻倍伤害。」). The factor 2 is the
  mod's one number here; everything under it (the braced soldier's weapon, the game's
  `charge_reflect_*` and `impact_reflection_*` values) stays the game's.
- Scope of the doubling: the reflection hit this rule gives a diving flyer. A flyer's ordinary
  charge along the ground is left to the game unless the measurement shows both go through one
  engine path, in which case the owner is told before it ships.
- Whether the dive is stopped stays decided by mass and speed, as before. The vanilla bounce
  (the charger thrown back) is not brought back.
- No native mechanic does exactly this. Order of work: measure first (a ground-cavalry positive
  control and the flyer lanes), then choose the mechanism from the measurement. If it cannot be
  done without the bounce, the question goes back to the owner.

### D5 · Second carry-through: no change (assessment, not a ruling)

> 「落地之后，飞行单位能否再次把步兵撞飞/撞穿应该也只看质量和速度……之前我们是怎么改的？应不应该是我说的这样？我也不确定，你需要研究和评估」

The answer below was given to the owner on 2026-11-17; he raised no objection.

- Fix in `80953c6`: the dive's special handling ends at the first melee engage (a body already
  in melee is never carried; any engage closes the slide window; an air re-charge ordered while
  engaged keeps it closed).
- After that fix a second charge from the ground is the game's own charge: mass, speed and
  bracing decide it. That is the behaviour the owner described.
- A speed threshold cannot replace those rules: for 15 flyers the dive's arrival speed and the
  ground charge speed differ by 2 m/s or less (burning chariot 0.7, the Tzeentch discs 1.2), and
  a threshold would also cut the slow end of every first dive.
- Not added: a "carried only within a few seconds of touchdown" bound. No remaining fault was
  measured after the fix, and it would change the multiplayer agreement for nothing.

# Decisions

Rulings by the mod's owner, oldest first. A ruling is quoted in the owner's own words where one
was given. An entry marked *assessment* is the maintainer's answer to a question the owner
asked, not a ruling; it stands until the owner says otherwise.

Two parts:

* **E1–E8, before 2026-11-17.** Made while the mod was still built inside the Lore Disasters
  repository. Copied here word for word from that repository's ledger (in Chinese, as written),
  so this file is complete on its own. The old section numbers are kept in each heading because
  the code comments and `docs/HISTORY.md` still cite them.
* **D1 onward, from 2026-11-17.** Written here.

Old number → entry here: §C8-45 item 3 → E1, §C8-57 → E2, §C8-58 → E3, §C8-59 → E4, §C8-60 → E5,
§C8-61 → E6, §C8-78 → E7, §C8-88 → E8, §C8-112 → D1–D5. A citation of the form `§C11 <NAME>`
points at the section of that name in `docs/HISTORY.md`; "ARCHITECTURE「飞兽俯冲统一规格」" is
`docs/SPEC.md`.

## Before 2026-11-17 (imported)

### E1 · 空军俯冲冲锋：做换动作的完整版（原 §C8-45 第 3 条，2026-11-09 用户裁定）

> 原条目另有三条与飞行模组无关（兵模数量、军队容量、递增攻势），留在主模组的台账里，这里只收第 3 条。

空军俯冲冲锋：直接做换动作的完整版——逐个飞行骨架换上带前向位移的空对地冲锋动作（动画表 `FLY_CHARGE_AIR_TO_GROUND` 103 号、`FLY_CHARGE_LAND` 104 号槽位），配合 `battle_entities.flying_charge_speed` 等数据调整；做成本模组内容，并可另出独立小模组。调研报告 `research_1109/air_dive_charge.md`。承载步 ccm 125。

### E2 · 近战中起飞：引擎补丁给全体飞行单位（2026-11-12 用户裁定）（原 §C8-57）

> 编号说明：integrate-1113（2026-11-13）合并时改号，车道 `air-dive-takeoff-w1 / air-dive-mp-dive-w1` 原记 §C8-49；该车道的提交说明与冻结证据仍写旧号。

1. 用户原话（经协调者转达）：起飞补丁用于**全部飞行单位**（双方、含 AI）。
2. 做法：经 memreader Plus 的 `handle:patch` 在 `0x143053d05`（9.0.5）把交战判定后的条件跳转 `0f 84 80 00 00 00` 改为无条件跳转 `e9 81 00 00 00 90`：起飞前的 3.0 秒计时不再被交战判定一直按满，总是倒数。特征码须恰好命中一次、原字节相符才写，可撤回。单一源 `tools/lib/air_dive_rules.py`（TAKEOFF_*），主包与独立小模组 `ld_air_dive.pack` 同发（小模组以 memreader Plus 为声明前置）。
3. 联机：补丁改的是各端都执行的战斗模拟代码。战役里经 memreader 协商步骤，各端一致才装；战役外的联机战斗撤回；单机直接装。经过与实测见 §C11 AIR-DIVE-TAKEOFF-W1。
4. 2026-11-12 同日被 §C8-58 取代：这一版「计时一律倒数」的字节补丁不再发货，改为「过半模型挨打才按住」。

### E3 · 近战起飞改为「过半模型挨打才按住」并发货；飞兽加速度下限撤回（2026-11-12 用户裁定）（原 §C8-58）

> 编号说明：integrate-1113（2026-11-13）合并时改号，车道 `air-dive-takeoff-w1 / air-dive-mp-dive-w1` 原记 §C8-50；该车道的提交说明与冻结证据仍写旧号。

1. 用户裁定（经协调者转达）：飞行单位只有在**真的挨打**时才被按在近战里。多模型单位要**过半存活模型**在最近 1.5 秒（15 个战斗时刻）内被近战打中才按住；单模型单位（龙）看它那一个模型。这条规则发货，取代 §C8-57 的字节补丁（那一版挨着打也能在下令 3 秒后飞走，可以冲完就走、反复冲）。
2. 用户裁定：飞兽加速度下限 8 撤回，用原版加速度。
3. 做法：三个代码洞，经 memreader Plus 位点加载器安装——两个在近战命中结算处记「哪个飞行实体在哪个时刻挨了打」，一个在起飞计时处按「现存模型里过半在窗口内挨过打」回答。唯一源 `tools/pipelines/pin_cave_asm.py`，主包与独立小模组 `ld_air_dive.pack` 同发。只算近战武器命中；远程、爆炸、冲撞伤害不算。
4. 联机与 §C8-57 相同：战役里经 memreader 协商，各端一致才开；战役外的联机战斗一律关闭；单机直接开。经过、数字与未验证项见 §C11 AIR-DIVE-TAKEOFF-W1 九。

### E4 · 连贯俯冲定 K 方案；穿阵按飞兽自身动量待研究地面骑兵后再定（2026-11-12 用户裁定，经协调者转达）（原 §C8-59）

> 编号说明：integrate-1113（2026-11-13）合并时改号，车道 `air-dive-continuous-w1` 原记 §C8-51；该车道的提交说明与冻结证据仍写旧号。

1. 采用 §C11 AIR-DIVE-CONTINUOUS-W1 的 K 方案为设计：489 号冲阵动作从落地速度起步只减不加，飞兽减速度 30，去掉 W13 的体型加重。暂不发货：先补完缺的实机局（飞马骑士、狮鹫骑士的原版落地对照），并实测减速度 30 对飞兽平常移动（不冲锋时的停步与转向）的副作用；之后再接进 `air_dive_rules`（唯一源），小模组与主包同走这一处。
2. 穿阵：用户倾向按飞兽自身质量×速度定冲多远，但担心对重甲反大型精锐步兵（拒马的戟兵、大剑士、混沌勇士、铁锤卫士之类）或骑兵这种中型目标也一样冲散不对。故：(a) 先查原版地面骑兵冲锋的冲击与穿阵由什么决定（质量、速度、冲锋加成、目标质量、拒马/反大型、阵型、碰撞门槛、冲撞攻击），要数据与实机读数（骑士对民兵、对拒马长矛、对重步兵、对骑兵）；(b) 把按自身动量的方案做成测试包，量它对这几类目标的效果；(c) 引擎路线保留为正式选项：静态查清引擎在哪决定冲锋者继续走还是停下、能否做成看目标的规则，报告改动要做什么；这一步不写游戏内存。
3. 车道规矩：用户在玩任何别的游戏时不启动战锤（每次启动前查进程表，有 StarSavior.exe 等就等）。

### E5 · 飞兽俯冲收成一份规格：动作一次连贯、穿深看相对动量（2026-11-12 用户令，经协调者转达）（原 §C8-60）

> 编号说明：integrate-1113（2026-11-13）合并时改号，车道 `air-dive-continuous-w1` 原记 §C8-52；该车道的提交说明与冻结证据仍写旧号。

1. 动作：全部飞兽的移动与攻击动作重做成真的俯冲冲进敌阵；一并修原版起飞降落直上直下、飞在目标头顶不打的毛病。
2. 机制：冲多深、打多重按双方相对动量定，与原版地面骑兵一样（用户例：银盔质量 1000、速度 115 能冲过站定的 250 质量步兵；1300 质量、速度 100 的飞行怪物应冲过 100 质量步兵；飞马也应如此）。引擎路线是正式选项（网络防护风险、联机须同包已知），报告要做什么。
3. 交付顺序：(a) 现有全部飞兽改动逐条清点（做什么、证据、保留 / 改 / 撤及理由，明确答狮鹫骑士现有做法是否保留、喷吐与起飞要不要改）；(b) 统一规格写进 `docs/ARCHITECTURE.md` 一节（两根支柱、规则、谁管什么、数只在 `air_dive_rules`）并附步骤；(c) 继续原版骑兵实测与引擎研究（落地在哪结束冲锋、落地的飞兽能否接着按地面冲锋走、由原版规则判停）。
4. 暂不发货；K 仍是已采用未发货，到符合规格再发。车道规矩不变。

落地：规格与清点见 `docs/ARCHITECTURE.md`「飞兽俯冲统一规格（AIR-DIVE-SPEC）」，实测见 §C11 AIR-DIVE-CONTINUOUS-W1。

### E6 · 冲多深、打多重由碰撞算出，不按兵种事先定；不做隐藏被动（2026-11-12 用户裁定，经协调者转达）（原 §C8-61）

> 编号说明：integrate-1113（2026-11-13）合并时改号，车道 `air-dive-continuous-w1` 原记 §C8-53；该车道的提交说明与冻结证据仍写旧号。

1. 用户原话：「减速要不要只靠被冲部队来给，让飞行单位自然减速，而不是用减速动作（去掉速度清零、减速的动作）？…冲不冲穿交给质量和速度自然决定？冲击伤害也是？根据被冲的部队类型来决定有点舍本逐末了吧」；「应该由计算得出，而不是事先用兵种来决定。」
   落实：触地不清零速度、不放减速的动作，飞兽带着落地速度往前走，只被撞上的身体减速；穿深、穿不穿与冲击伤害由质量、速度与引擎自己的碰撞算法（含拒马质量倍数，那也是算出来的）得出。不写按兵种的深度目标，不按兵种设深度上限。这就是引擎路线：用运行时探针找到触地清零速度的那一处与强加冲阵 / 减速的那一处，绕开它们，其余交给原版碰撞。数据层的 R、M 两条不再做。
2. D 档（冲锋时自动开的隐藏被动）不发。用户原话：「我们不做隐藏被动」——通则：不做隐藏被动。
3. 协调者告诉用户：用户测到的冲锋没有改引擎（数据 + 动作；只有起飞是引擎补丁）。本车道核对属实：冲阵、冲撞攻击都是数据与动作，读数器只读内存；起飞补丁在起飞车道。
4. 车道规矩不变：GAME_LOCK；用户在玩任何游戏（StarSavior、Overwatch 等）时不启动战锤；memreader Plus 位点 + 联机协商照起飞补丁；不跑 pytest、不建包。若引擎工作被安全防护拦下，停下报告，不绕。

落地：`docs/ARCHITECTURE.md`「飞兽俯冲统一规格（AIR-DIVE-SPEC）」按本条改写；原版骑兵停下的原因（碰撞还是接战锁定）与探针结果见 §C11 AIR-DIVE-CONTINUOUS-W1。

### E7 · 单体飞兽挨打窗口放宽到 3 秒（2026-11-16 用户裁定）（原 §C8-78）

> 接 §C11 FLYER-TAKEOFF-HITS：记录洞补全后，单体飞兽面对巨人、领主仍会在两次出手之间飞走——这些单位几秒才出手一次，长过 §C8-58 的 1.5 秒窗口。

改 §C8-58 的规则本身：一个飞行单位**只剩一个存活模型**时，那个模型最近 **3 秒**（30 个战斗时刻）内被近战打中就按住；两个及以上存活模型的单位仍是「过半存活模型 1.5 秒内挨打」。「存活」按引擎自己的现存飞行实体表数（模型死亡即离表），所以多模型单位死到只剩一个模型时也按 3 秒。其余不变：只算近战（引擎伤害类型 0），全体飞行单位、双方含 AI，联机走同一条协商。

### E8 · 飞行模组独立开发，主模组与它解耦（2026-11-17 用户裁定）（原 §C8-88）

用户原话：「同步到独立出去的开发目录，以后这个飞行mod在那边开发，主mod解耦飞行mod（以后主mod不包含飞行mod的更改）。GitHub那边也记得建仓库推送。」

1. **飞兽俯冲 / 起飞模组（创意工坊 3840651516，`ld_air_dive.pack`）只在独立仓库开发**：`D:/Projects/wh3-flyer-dive`，GitHub `skymanbp/wh3-flyer-dive`。主仓库不再存它的文件，也不再与它双向同步。
2. **主包 `ld_mod.pack` 不含飞行模组的任何改动**：俯冲与近战起飞的脚本与代码洞位点表、改名飞行动作表、对原版 / 自建 / 捐赠方飞兽实体与坐骑的俯冲改写（冲锋速度、减速度、冲锋距离、转向动作、跳击、质量下调、冲撞攻击与冲锋被动）、喷吐技能接战可放的整表替换，全部退出主包。
3. **取代**用户令 `minimods-in-main-1113`（「主包必须包含全部小模组」）中飞行模组那一半；引擎抗性等其余小模组仍按该令与主包同源。
4. **判别规矩**（本批定）：某行改动只为俯冲模组而存在（速度、质量、动作表重指）→ 出主包；属于该单位自己的设计（例如月盘骑士身体 `ld_moncav_tze_disc` 的 large 体型与质量下限、加尔劳赫去马鞍的身体）→ 留主包。逐行处置见 §C11 FLYER-DECOUPLE。
5. **共用件留主包**：`lib/ld_cave_common.lua`（只剩引擎抗性战斗入口用的记录行）、memreader Plus、动作编解码库、DB 写入器与 schema、`entity_read` 读取器；测试驱动共用件改放 `tools/pipelines/battle_autotest_harness.py`（那是主模组仓库的文件；本仓库的驱动是 `air_dive_autotest.py`，只由 `flyer_run.py` 调用）。
6. 落地：2026-11-17，车道 flyer-decouple（§C11 FLYER-DECOUPLE，墓碑 §C10.7）。

## 2026-11-17

Research behind D1–D5: `docs/research/2026-11-17-next-version-design.md`.

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
- **Measured offline on 2026-11-18 (`docs/HISTORY.md` PROBES-1118; nothing run in game yet):** the
  installed game has 129 land units with `charge_reflection`, not 136. The game itself already hurts
  the charger, two ways: a braced `charge_reflection` soldier's ordinary attacks on a charger whose
  charge factor is 0.7 or more are multiplied by `charge_reflect_damage_multiplier` (2), and a separate
  impact reflection applies its own damage. So this rule may need no damage source of its own. What
  "twice the game's own" means under that mechanism is asked of the owner after the control run.
- **Measured in game on 2026-11-18 (`docs/HISTORY.md` INGAME-1118 series 4, part 3):** the multiplier is
  what the game applies. Knights charging braced spearmen: applied 151 times, always 2.0, always to the
  braced soldier's hit on the charger, never the other way. Flyers diving into braced spearmen: applied 58
  times at 2.0 to hits on the flyers, so a dive and a ground charge go through one engine path. It barely
  hurts a large flyer: health lost in the 5 seconds after first contact was 0 for the star dragon and the
  manticore, 0.4% for the griffon knights and 3.0% for the pegasus knights. **Nothing of D4 is built yet.**
  Two questions go to the owner before it is: what factor the flyers get on top of the game's 2, and whether
  it covers a dive only or any charge by a flying unit.

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

### D6 · This repository is the mod's only home: rules, records and memory live here

> 「创意工坊、mod相关内容等等的更新、新的上传规则，还有一些决定啥的，全部同步更新到飞行mod开发目录，以后飞行mod的修改我就在那边进行了，你把相关规则和记忆搬过去，同时让那边跟这里解耦。」
> The same night, on a misreading: 「飞行仓库不是已经有了吗？本地和GitHub都有啊？……我的意思是把新的规则、记忆、更新，等等，搬过去，不是新建啊」

- Nothing new is created: everything moves **into** this existing repository (local
  `D:/Projects/wh3-flyer-dive`, GitHub `skymanbp/wh3-flyer-dive`).
- Moved here: the working rules (`CLAUDE.md`), every earlier ruling (E1–E8 above), the batch
  records (`docs/HISTORY.md`), the dive specification (`docs/SPEC.md`), the Workshop procedure
  and rules (`docs/WORKSHOP.md`), the state of the work in flight (`docs/STATUS.md`), and the
  assistant's project memory and plan for this directory.
- Decoupled: building, re-deriving the staged tables and running the tests need only this
  repository and the installed game. The retired two-way sync with the Lore Disasters repository
  is deleted. The Lore Disasters ledger keeps one-line pointers to here.
- The main mod's own flying bodies and donor flyers get the dive through a separate adapter pack
  later (owner, the same evening: personal mods are decoupled 「并做对主mod的适配」; the adapter
  waits for the main mod's rename, because every key it would name changes then). Until then the
  data for it is kept in this repository as a recorded snapshot and the shipped packs do not
  contain it.
- Pushing to GitHub, uploading to the Workshop, editing a Workshop page and creating a new
  Workshop item each need the owner's go-ahead in the conversation, every time.

### D7 · The flyer mod's working data moves to this side, with a record here

> 「飞行mod相关的数据全部搬过去。记得在那边仓库补上记录」 (owner, 2026-11-17 night, when asked what to
> do with the scratch folders; in the same answer he chose to delete the scratch older than
> 2026-11-16, 16.9 GB, and to keep the unpacked donor mods.)

- The scratch folders of the flyer work (test runs, probe output, builds, upload staging) move
  from the Lore Disasters scratch area to `D:/Projects/.worktrees/wh3-flyer-dive/`.
- What moved, from where and how large is recorded in `docs/HISTORY.md` (section DATA-MOVE-1117).

### D8 · Push the main branch only; the next version's branches stay local

> 问：「现在推上去吗？」答：「只推主分支」 (owner, 2026-11-17 night)

- `main` (the published code plus the rules and records that moved in) is pushed to GitHub.
- `update-1117` and `rider-seat-1117` stay local until the owed in-game checks are done; pushing them is
  asked again then.
- The go-ahead covers this one push. Later pushes are asked each time (D6).

## 2026-11-18

### D9 · The next version drops `ld` from every name the mod ships

> 问：「飞行模组的包现在叫 ld_air_dive.pack，名字里带 ld。新版要不要顺手改掉包名？」答：「这一版就改」
> (owner, 2026-11-18, while the mod was four days old on the Workshop)

- Covers every name the mod ships or writes: the main pack's file name, the script paths and file names
  inside it, the DB fragment names, the keys the mod mints (renamed flight tables, rider tables, the
  levelled clip, the cloned melee weapons, the two locomotion rows), the memreader Plus owners, the cave
  buffers' marks, the log files written next to `Warhammer3.exe`, the agreement titles shown in
  multiplayer, and the comments inside the shipped scripts. Also the development environment variables
  `LD_*` and the test probes' names. The old → new table is in `docs/HISTORY.md` RENAME-1118.
- New names carry no `ld`, `LD` or "lore disaster". The main pack becomes `flyer_dive_takeoff.pack`: it
  still sorts after `flyer_dive_balance.pack`, so the submod keeps winning the rows both ship (D1).
- Not renamed: keys of the base game; keys and names of the Lore Disasters mod kept as adapter input
  (`mod/tools/data/main_mod_flyers.json`, the adapter rows of `air_dive_rules.py`); the external test-only
  reader `ld_entity_read`; vendored memreader Plus; the historical records (E1–E8 above,
  `docs/HISTORY.md`, `docs/research/`, `mod/tools/evidence/`).
- **Subscribers may have to tick the mod again once** after the update (the launcher remembers the pack by
  its file name). This goes into the release's change notes, together with: an old copy of
  `ld_air_dive.pack` left in the game's `data` folder must be deleted, or both versions load.
- Old and new versions do not pair in a multiplayer campaign (the memreader Plus owners changed); the
  change notes say so, as they do whenever the agreement changes.

### D10 · The balance submod is withdrawn; breath while engaged becomes an MCT switch

> 「飞行模组之前说要再做一个平衡性submod，我想了下，撤回，吐息和质量改动依旧是放在同一个飞行mod里，但是开不开接战中吐息可以用mct去调整」
> (owner, 2026-11-18)

- D1 is withdrawn. The mod ships **one pack**, `flyer_dive_takeoff.pack`. Breath attacks usable while
  engaged in melee, and the mass cut for large (×0.85) and very large (×0.75) flyers with its exceptions,
  go back into it. There is no `flyer_dive_balance.pack` and no second Workshop item.
- Whether breath can be used while engaged in melee is a setting in the Mod Configuration Tool (MCT).
  The mass cut is not a setting.
- Maintainer's choices under this ruling (they stand until the owner says otherwise): the setting
  defaults to **on**, which is what the published version does; a player without MCT gets the default;
  MCT is optional, not a requirement.
- How the switch works is not chosen yet. The published version unlocks breath by leaving rows out of
  a DB table, and a setting cannot change a DB table while the game runs. The mechanism is picked from
  a measurement (offline first, then in game). If none holds up, the question goes back to the owner.
- What follows from it: D9's reason for the pack name (it had to sort after the submod) no longer
  applies, and the name `flyer_dive_takeoff.pack` stays, because the branch, its in-game records and
  the rename table already use it. D2's Workshop texts lose the submod item.
- **Mechanism chosen (maintainer, 2026-11-18, from the offline work; the in-game check is owed):** the
  shipped table stays unlocked. That is the on state: it needs no script, no MCT and no memreader Plus,
  and it is what the published version does. When the setting is off, a battle script puts the game's
  two locks back by hand: every 100 ms of battle time, each of the 20 breath abilities a unit owns is
  disabled while the unit is in melee (and, for the 12 abilities whose `grounded` row was dropped, while
  it is not flying), and enabled again when no lock holds. Not chosen: changing the engine's own check
  with a code cave, which would tie a cosmetic-sized setting to memreader Plus and to the multiplayer
  agreement.
- **A multiplayer battle ignores the setting and stays on** (maintainer's call until the owner says
  otherwise): the two players' settings can differ, and a script disabling abilities has never been
  seen in a multiplayer battle. Changing this needs a two-player test.
  **Replaced by D14 (owner, 2026-11-18):** a multiplayer campaign battle follows the setting; only a
  multiplayer battle outside a campaign still stays on.
- The settings page is English, or Simplified Chinese when the client is Simplified Chinese (told by
  the game's own word for the breath ability type). One language per string.
- **Checked in game on 2026-11-18 (`docs/HISTORY.md` INGAME-1118 series 4, part 4):** without MCT the
  switch is on and a breath order given in melee is accepted; with a stand-in settings pack saying off the
  script locks the 20 abilities and the engine refuses the order; saying on, it is accepted again. With the
  damage recorder: on, the enemy took 51 hits (1,949 damage) from a source that appears only after the
  breath order; off, none. Still owed: one look with the real MCT (settings page, reading order). A
  multiplayer battle was not run.

### D11 · The next version is uploaded only when the braced-spear damage is in and the take-off gap is explained

> Asked how the next version should be uploaded: 「等「撞长矛受伤」做完一起传」
> Asked about the one-or-two-tick gap in the take-off rule: 「查清再发」 (owner, 2026-11-18)

- No upload of the next version until all of these are built and checked in game: D4 (a dive into
  braced spears hurts the flyer), D10 (one pack, the MCT switch), and the gap recorded in
  `docs/STATUS.md` (a flyer whose countdown had long run out is hit once, ordered away on the next
  tick and airborne one tick later). The gap must be explained by a measurement, and fixed if it is
  the mod's.
- This replaces the maintainer's earlier call that the gap need not hold the release.
- The upload itself is still asked when everything is ready.
- **The gap is explained and fixed (2026-11-18, `docs/HISTORY.md` INGAME-1118 series 4, parts 1 and 2).**
  Measured: every model gets one flight update per tick; the update asks the take-off rule in phase 1 and in
  phase 2 while the countdown is above 0, and never in phase 2 at countdown 0 (0 of 18); hits are recorded
  after that tick's update. So a model hit at countdown 0 and ordered away before its next update was lifted
  unasked. Fix: when the mod records a melee hit on a model whose countdown is 0 in phase 1 or 2, it raises
  the countdown to 1, so the next update asks the rule. Checked in game: 2 such hits, both raised, both then
  asked and held; 8 take-offs, none early. The exact ordering (hit, then the order in the same tick) did not
  occur in that run; for it the proof is the emulator cases plus the measured engine behaviour.
- Of the three conditions above, D10 and the gap are met. **D4 is not built**, so nothing is uploaded yet.

### D12 · No compatibility patch for other mods' ridden units for now

> Asked whether to make a patch for the six ridden units of two subscribed mods: 「先不做」 (owner, 2026-11-18)

- The six units (the sword-and-shield pegasus knights of `lbm`, five ridden vampire units of
  `kaylika_auri_lahmians`) are left as they are. Their riders may come off the mount in a dive; that
  was never looked at in game. The note stays in `docs/STATUS.md`.

### D13 · Branch `rename-1118` is pushed

> Asked which repositories to push: 「飞行模组分支推公开仓库」 (owner, 2026-11-18)

- `rename-1118` (at `0a3b2c4`) is on GitHub as a branch. `main` is unchanged and still the published
  version. For this branch it replaces D8's "stay local until the in-game checks are done".
- The go-ahead covered that one push. Commits made after it stay local until asked again.

### D14 · In multiplayer the breath setting follows the host

> 「多人模式的MCT设置是根据主机（房主）的设置走的，不会不同步，你正常做就行。」 (owner, 2026-11-18)

- This replaces D10's "a multiplayer battle ignores the setting and stays on". A multiplayer **campaign**
  battle reads the setting exactly like a single-player battle.
- Checked in MCT's own scripts (Workshop 2927955021, `groovy_mct.pack`, read on 2026-11-18): in a
  multiplayer campaign the host's settings are sent to every machine (`systems/sync/main.lua`:
  `MctMpInitialLoad` on the first load, `MctMpFinalized` whenever the host finalizes; each machine applies
  them with `set_finalized_setting`), and the other players' options are locked
  (`objects/options/obj.lua`, lock reason `mct_lock_reason_mp_client`). A campaign battle reads that
  campaign's saved settings (`systems/registry/main.lua`, `load_campaign_battle`).
- **Maintainer's call, told to the owner:** a multiplayer battle **outside** a campaign (custom, quick,
  ranked) still stays on. MCT shares nothing there: each machine reads its own global settings
  (`systems/registry/main.lua`, context `battle`); the sync code is campaign-only and its messages go
  through `CampaignUI.TriggerCampaignScriptEvent`. Two players with different settings would have the
  script lock abilities on one machine only. The battle script tells the two kinds apart with
  `bm:is_from_campaign()`, the call the take-off and dive scripts already use
  (`lib/cave_common.lua`, `start_battle`); if that call fails in a multiplayer battle, the battle counts
  as outside a campaign and stays on.
- Wording follows the client. The Chinese settings page says 多人战役 / 多人战斗 / 主机
  (`local_cn.pack`: 13 / 18 / 19 uses; 联机 2, 房主 0).
- Not verified: no two-player battle was run. What MCT does is read from its code, not seen in a
  multiplayer session.

### D15 · Braced-spear damage: the maintainer sets the size, a dive only

> Asked how much a dive into braced spears should hurt (D4): 「冲锋反制的伤害我不确定是怎么计算的。你给它加到确实能造成一些伤害，但是不会太超标的程度。这个伤害应该只能由有冲锋反制技能的部队在站定的条件下才能触发吧？」
> Asked whether it covers a dive only or any charge by a flying unit: 「只算俯冲（推荐）」 (owner, 2026-11-18)

- **Size:** the owner leaves the number to the maintainer, inside two bounds: it must really cost the
  flyer health, and it must not be excessive. The number is chosen from an in-game measurement and is
  reported to the owner, with the measured losses, before the version is uploaded. This replaces D4's
  "twice the game's own" as the rule for the size.
- **Scope:** a dive from the air only. A flying unit's charge along the ground after it has landed stays
  the game's. If a dive cannot be told apart from a ground charge at the point where the damage is
  computed, the owner is told before it ships.
- **The owner's question, answered** from the installed game's data and the series 4 measurement
  (`docs/HISTORY.md` PROBES-1118 part two, INGAME-1118 series 4 part three): yes. The game multiplies only
  hits made by a unit that has the `charge_reflection` attribute (129 land units) while that unit is
  bracing (game text: "When bracing, this unit causes additional damage when attacking charging enemies";
  rule values `unit_braced_status_threshold` 0.75, `bracing_attack_angle` 80), and only when the charger's
  charge factor is at least 0.7. In game it was seen in one direction only, the braced soldier's hit on
  the charger: 151 times against knights, 58 times against flyers. The mod keeps those conditions and
  changes only how much such a hit costs a diving flyer.
- **Direction of the mechanism (maintainer, 2026-11-18, from the series 4 records; `docs/HISTORY.md`
  D15-ANALYSIS-1118):** a larger multiplier alone is ruled out. In the recorded flyer battle the three
  larger flyers lost no health at all in the seconds they dived through the braced line (their first loss
  came 5 to 12 seconds after landing, in the melee that followed), and by arithmetic on the recorded hits a
  multiplier of 8 would cost the star dragon about 3% in five seconds and the manticore about 35%. So the
  cost is taken once per model per dive, at the dive's contact with a bracing `charge_reflection` soldier,
  as a share of the model's own maximum health; the game's own doubling stays as it is. How it is done and
  the share are fixed after an offline build and an in-game measurement.
- **The offline design stopped before building (2026-11-18, `docs/HISTORY.md` D15-DESIGN-1118):** the
  damage calculator's test cannot be the trigger, because at the dive contact of the star dragon and of the
  manticore the game's conditions did not hold. The contact is recognised by what does happen there: the
  flyer's own impact and collision damage on a bracing soldier. No way of originating the hit on the flyer
  could be shown safe offline. Three ways exist: calling the engine's damage routine from a hook, writing the
  model's health directly, or adding the cost to the model's next melee hit. The first two are tried in
  test-only packs, one run each, after a probe run, while a ready-made engine or battle-script way of
  damaging a unit is looked for. The third turns "at the contact" into "paid on the next hit" and is not
  used without the owner's word.
- **A ready-made way to take health was found (2026-11-18, `docs/HISTORY.md` D15-PROBE-1118):** the game's
  battle scripts have `unit:reduce_hitpoints_unary(proportion, hide_bodies)`, and CA's own scripts use it.
  The maintainer tries this first: the hook only recognises the dive contact and records it, and the mod's
  battle script takes the share off through the game's own command. It acts on a whole unit, so for a unit
  of several models the share is scaled by the number of models that pay. Second choice: the damage
  routine's own branch that hits the attacker back. Both stay in test-only packs until measured in game.
- Not verified: whether 80 is the whole front arc or half of it. Of D15 only the test-only probe is built
  (offline); the rule itself is not.
- **Built into the shipped pack, offline (2026-11-18 night, `docs/HISTORY.md` D15-SHIP-1118).** The share is
  3% of the model's own maximum health for every body size (a test value, not the final number). One
  condition was added by the maintainer and is not the owner's wording: the flyer must be inside the game's
  own bracing angle (80) of the soldier's facing (`DIVE_COST_FRONT_ARC`, one switch); the game's own
  doubling does not test that angle. Nothing of it has run in game yet, and every in-game number of
  2026-11-18 was taken on the old sloped map (`docs/HISTORY.md` TEST-STD-1118), so the losses are measured
  again under the standard setup and reported to the owner before any upload.
- **The owner accepted 3% for every body size (2026-11-19).** The losses measured under the standard setup
  (`docs/HISTORY.md` D15-STD-1119: star dragon 282 of 9,424 and manticore 153 of 5,103, each 3.0%; griffon
  knights 1.5% and pegasus knights 0.8% of the whole unit; nothing against swordsmen) were reported, and the
  owner was asked: 「飞行模组：飞兽俯冲撞上正面架矛的步兵时，每个撞上的飞兽模型扣自己血量上限的 3%（实测星龙一次扣
  282 / 9,424；撞剑士这类不架矛的不扣）。四种体型都用 3%，可以吗？」 Answer: 「就用 3%」. So 3% is the number
  that ships, no longer a test value. The front-arc condition was named in the question (「正面架矛」) and
  stays. Still owed before the upload: the shipped pack itself (the one without the recorder) once in the
  game, and the refusal outside the front arc, which has not been seen in game.

### D16 · Branch `rename-1118` is pushed again

> Asked which commits to push: 「飞行模组分支推公开仓库」 (owner, 2026-11-18)

- `rename-1118` is on GitHub at `76e1228` (pushed `0a3b2c4..76e1228`: the rulings D10–D13, the one pack
  with the breath switch, the take-off gap fix, D14). `main` is unchanged and still the published version.
- As before, the go-ahead covered that one push. Commits made after it stay local until asked again.

### D17 · The local commits are pushed (2026-11-19)

> Asked whether to push the commits that were only local, in the main mod's repository, here and in the
> toughness mod's repository: 「三个仓库都推」 (owner, 2026-11-19)

- Here that is branch `rename-1118`: everything after `76e1228`, up to and including the commit that records
  this entry (D15 from the first analysis to the shipped pack, the one test standard and runner, the three
  standard battles). `main` is unchanged and still the published version.
- As before, the go-ahead covered that one push. Commits made after it stay local until asked again.

### D18 · In-game runs go alongside the main mod's offline background work (2026-11-19)

> Told that the in-game checks owed before the upload were waiting for a two-hour offline comparison of the
> main mod to finish: 「你直接开游戏就行。同时跑，加快开发进度」 (owner, 2026-11-19 afternoon)

- The in-game runs of this mod are started while that offline job of the main mod is still running. This is
  the owner's exception to "one heavy job at a time" for this pairing (a game run here, an offline
  comparison there). The runner's own refusals stay as they are (the owner's game, another game, the
  heavy-job lock, a test or build job), and it still never touches a game it did not start.
- Maintainer's reading, not the owner's words: the exception is about not waiting for the main mod's offline
  job. It does not cover two game runs at once, and it is not an approval to upload: the upload is asked
  separately, with the pack's size and checksum, the update note and the page text (`docs/WORKSHOP.md`).
- Checked before the first run: no game was running; 6.6 GB of 31 GB memory was available, so a run that
  dies for lack of memory is read as that, not as a defect of the mod.

### D19 · The text is shown to the owner before it is published (2026-11-19)

> 「文字描述发之前先给我看」 (owner, 2026-11-19 afternoon, while the in-game checks of D18 were being
> written up and the page text was being finished)

- Before an upload or a page change, the whole text that would be published is put in front of the owner in
  the conversation: title and description of each language, and the update note. Nothing is published until
  the owner has answered. This is the standing rule of `docs/WORKSHOP.md` and D6, said again for this
  version.
- Maintainer's reading, not the owner's words: 「文字描述」 covers the page descriptions and the update note
  alike, and a later change to a text that was already shown is shown again.

### D20 · The page keeps the live text; only the changes the owner passed, one by one (2026-11-19)

> Shown the rewritten per-language drafts and how they differ from the live page: 「能不能就和之前的一样？或者需要改/增/删
> 的内容一条条给我过？askuser给我？」 Then, item by item (eight questions, owner, 2026-11-19 afternoon):
>
> - the take-off line (the rule changed, the live sentence is wrong): 「不写秒数」
> - the new dive cost: 「直接在这条下面新加一条“增加冲锋反制造伤，增加长戟部队对飞行大型部队的威胁”」
> - the breath setting: one sentence after the breath line
> - the multiplayer sentence: 「保持原句」
> - one bilingual page or two: 「拆成中英两页」 (D2 stands)
> - the title: 「保持原标题」
> - the Chinese words 喷吐 / 接战 / 联机: the game client's 吹息 / 陷入近战 / 多人
> - the update note: the one without numbers

- The page text is the live text of 2026-11-17, split by language, with exactly those changes
  (`workshop/flyer_dive/`, built by a script from the text Steam returns, every change one exact replacement).
  Titles: "Flying Charge Overhaul (Dive, Plough, Take-off)" and 「飞兽俯冲冲锋重做」.
- Three changes are the maintainer's, shown to the owner with the final text: the log file names in the Notes
  section (three files under their new names; a fact); the Chinese page carries the two comparison pictures of
  the English half (after the split a Chinese reader would no longer see them); two verb uses of 接战 became
  近战 where 陷入近战 does not fit the sentence.
- The rewritten drafts of 2026-11-17/18 (titled "Flyer Dive & Take-off") are replaced; they stay in git
  history (`26955f3`).
- Known and left as it is: the settings page inside the game (MCT) is titled "Flyer Dive & Take-off" /
  「飞兽俯冲与近战起飞」, as built into the pack; the Workshop title keeps the old name.
- Nothing is published by this entry. The upload and the page change are asked separately (D6, D19).

### D21 · The owner's three edits to the page text; no fix-type sentences on the page (2026-11-19)

> Reading the text built under D20 (owner, 2026-11-19 afternoon):
>
> - 「新的一次俯冲从第一次被挡的位置起最多再冲 20 米，之后按原版近战。已经陷入近战的敌人不会被带着走：正在和你其他部队交战的
>   单位，或飞兽对自己已在打的近战再次冲锋，都在原地近战。 这句去掉，不用写。这种bug修复类型的文字，没必要此地无银三百两」
> - 「装了 Mod Configuration Tool（可选）可以关掉这一项，默认开 这句改成"可用MCT调整"」
> - 「每个兵模单独计算：刚挨了近战打击的兵模暂时不能起飞，其余兵模可以；体型越小等得越久。只是挨着敌人不再按住它。 改成
>   "更加合理的起飞""根据体积、兵模、接战间隔进行起飞判定"」

- Rule for this page from now on: it says what the mod does for the player, in few words. Sentences that
  describe a fix, an internal limit or how a rule is computed stay out of the page text.
- The braced-spears bullet keeps its title and first sentence; the two sentences after it are gone, in both
  languages. The rule itself is unchanged and still in the pack.
- The take-off bullet is the owner's two phrases: 「更加合理的起飞。」 as its title and 「根据体积、兵模、接战间隔进行
  起飞判定。」 as its body. His sentence is kept word for word, 接战 included, although the rest of the Chinese
  page uses the game client's 陷入近战 (D20).
- The breath bullet ends with 「可用MCT调整。」.
- The English page follows with the maintainer's translations, shown to the owner with the text: "Fairer
  take-off." / "Take-off is judged by body size, per model, and by the time since the last melee hit." /
  "Can be adjusted with MCT."
- This replaces D20's take-off wording and breath sentence. The update note (`changenote.txt`) is not changed
  by this entry: it is the note the owner chose under D20. It still lists one fix (riders coming apart from
  pegasus-type mounts); the maintainer reads the owner's remark as being about the page text, and reported
  this to him with the final text.
- Nothing is published by this entry (D6, D19).

### D22 · The text is accepted; upload now; English by the tool, Chinese pasted by the owner; push both (2026-11-19)

> Four questions in one sitting (owner, 2026-11-19 about 17:10); each was answered with its first option:
>
> - 「飞行模组的工坊页面定稿和更新说明（全文在对话里刚贴出的那条消息）可以了吗？」 → 「都可以」
> - 「飞行模组的新包（14,090,541 字节，今天在游戏里跑了 12 局全部通过）现在上传到创意工坊吗？」 → 「现在上传」
> - 「页面拆成中英两栏后，文字怎么写上去？上传工具只会写默认那一栏，分语言这一步我还没试过。」 → 「英文我写，中文你贴」
> - 「本地还没推到 GitHub 的提交推不推？飞行模组分支 5 笔，主模组 2 笔。」 → 「两边都推」

- The consent covers this one upload, this page change and these pushes (D6). The whole text had been shown in
  the same turn (D19).
- The upload tool writes the default language slot only. The Simplified Chinese slot is filled by the owner in
  the web page ("Edit title & description", language Simplified Chinese) from two text files put on his Desktop.
  Until he has done it a Chinese reader sees the English page; the question told him so.
- After the upload `main` takes the release branch (the option's own words: 「飞行模组上传成功后，主分支指到发布的那笔提交」).
- What was uploaded and how it was verified: `docs/HISTORY.md` UPLOAD-1119.

### D23 · Multi-model flyers: models that have taken off must not be pulled back to models held on the ground (2026-11-19)

> Owner, 2026-11-19 about 20:02, typed in the main mod's session (recorded here at 20:06):
>
> 「飞行mod那边有个问题，原版就有这个问题，现在我们起飞机制修改之后可能会更严重，就是多模组部队起飞后，如果有部分模组被拦截在地面上，那其他模组哪怕起飞，也会被拉回去（没法把已经起飞的兵模拉走，总是会回到那个没起飞的兵模处）。这个能不能彻底解决？然后更新飞行mod。这个问题困扰我好久了，可以单独加一个说明和对比图。」

- Maintainer's reading of one word (not the owner's): 「模组」 in 「多模组部队」 means the models (兵模) of one unit:
  harpies, pegasus knights, griffon knights and the like.
- The problem as the owner describes it, not yet measured here: a unit is ordered away; some of its models are held
  on the ground; the models that did take off cannot be led away and come back to the model that did not. He says
  vanilla does it too, and that this mod's take-off rule (per model since D3) may make it worse. Neither half is
  measured yet.
- Order of work: (1) reproduce it in the game with a per-model record, on vanilla's own rule and on this mod's;
  (2) find the engine rule that brings the airborne models back (read the code, confirm it at run time; no guess
  goes into a fix); (3) only then answer whether it can be solved completely, and build the fix; (4) in-game A/B,
  every check with its negative control; (5) the release.
- 「然后更新飞行mod」 is the owner's request for a new version once the fix is verified. The upload itself, any page
  text and any picture still go the way D6 and D19 to D21 set: asked for when the pack is ready, the whole text shown
  first, changes to the live page passed one by one.
- 「可以单独加一个说明和对比图」: the page gets a separate explanation of this fix and a before/after comparison
  picture. Both are drafted from measured runs and shown to the owner before anything is published.
- A rule change in the battle simulation means a new multiplayer agreement marker (CLAUDE.md).

### D24 · The two local docs commits are pushed (2026-11-19)

> One question in a sitting of three (owner, 2026-11-19 about 20:12, recorded here at 20:20):
>
> - 「本地还没推到 GitHub 的提交推不推？主模组 2 笔（都是今晚的文档与计划表），飞行模组 2 笔（都是文档，含你刚提的多兵模问题那条记录）。」 → 「两边都推」

- Pushed at 20:12: `main` from `5a98bb4` to `57ac401` (commits `2b17a85` and `57ac401`, docs only). Checked by
  fetching afterwards: the remote `main` is `57ac401`.
- The consent covers this one push (D6). This record's own commit stays local until the next push is asked for.
- Lane branch `regroup-1119` (D23) is local only.

## 2026-11-20

### D25 · Braced charge-defence infantry against a dive: settled by the engine's own physics, tunable in MCT (2026-11-20)

> Owner, 2026-11-20 about 13:29, in the main mod's session, with a screenshot of two comments on the Workshop page
> (one asks for an MCT toggle for "no dead stop on braced spears"; the other says that 3% damage is nothing when the
> dive breaks the formation so badly):
>
> 「看截图，这俩评论我觉得说得都有道理。我们现在的冲穿冲锋反制部队的改动是怎么做的？我记得原版的话冲锋反制是会增加质量/冲锋抗性来着？因为增加的冲锋抗性所以原版才会更难冲穿冲锋反制部队。我们mod是怎么做的？并没有强制冲穿吧？研究一下。」
>
> Asked the same day (about 14:00, in one sitting) how a frontal dive into braced charge-defence infantry should be
> settled from now on, he wrote his own answer instead of taking an option:
>
> 「1.增加冲锋抗性的效果。2.增加冲锋反制的造伤。3.加mct选项，让玩家可以自行调整平衡。总之，不设置条件判断来硬改，而是从游戏本身的物理引擎来解决问题。」
>
> - Size of the cost of a frontal dive into braced Charge Reflection infantry (3% of a model's maximum health today,
>   D15): 「提到 10%」
> - An MCT switch for it: 「加开关（推荐）」
> - In-game tests: 「我接下来有些会议，所有实机测试暂停，等我指示。其他方向的任务应该有一大堆没做完，不要停。」

- What he was told before he answered (from this repository's records; nothing new was measured): the mod does not
  force a charge-through and does not change the brace mass multiplier or any `_kv_rules` value. It gives the dive a
  through-goal, keeps the landing speed, and holds off the engine's "touched an upright enemy, so the order becomes a
  melee order and the unit brakes" while the landed flyer is still fast (D4, `docs/HISTORY.md` AIR-DIVE-BRACE-W1).
  Measured with the mass cut: 16 early stops in 120 dives into braced spears and halberds. So bracing barely counters
  a big flyer's dive and the price is D15's 3%. His memory of vanilla is right in substance: a standing soldier's mass
  multiplier is doubled by the two charge-defence attributes (`docs/SPEC.md`, pillar two); Charge Reflection is the
  damage attribute.
- The ruling, in the maintainer's words: (1) the engine's charge resistance has to count for more; (2) Charge
  Reflection has to hurt more; (3) the balance is the player's to tune in MCT; and there is to be no rule of the form
  "if the target is braced charge-defence infantry, stop the flyer": the outcome has to come out of the collision.
- Maintainer's readings, not the owner's words. "10%" is the size the cost should have: it is to be delivered by the
  engine's own Charge Reflection damage where that can be brought there (the game already applies
  `charge_reflect_damage_multiplier` to a diving flyer, D4's in-game measurement); D15's scripted deduction stays only
  if the engine's damage cannot be brought there, and the owner is told which it is before anything ships. "An MCT
  switch" and "MCT options" are read as one set of settings whose defaults are these choices.
- Open, and the maintainer's to settle by reading and measurement: which values carry this and whether they are pack
  rows or constants in the executable; that a `_kv_rules` value is global, so ground cavalry and monsters feel it too;
  how an MCT setting reaches a value the pack fixes at load; whether the hold on the melee-order switch is itself a
  forced outcome under this ruling. Nothing is built or verified.
- Order of work: an offline, read-only survey of the engine values and the design options (started 2026-11-20); the
  design is chosen by the maintainer and recorded here; it is built offline; it is measured in game with negative
  controls **once the owner lifts the pause**; page text and upload go the way D6 and D19 to D21 set (the page lines
  "No dead stop on braced spears" and "More Charge Reflection damage" then need the owner's item-by-item pass).
- **All in-game tests of this mod are paused from 2026-11-20 about 14:05 until the owner says otherwise.** That
  covers D23's reproduction runs. The game is not started.
- A rule change in the battle simulation means a new multiplayer agreement marker (CLAUDE.md); MCT settings follow
  the host (D14).

### D26 · The brace changes are for flyers only; charge resistance is a stat of its own (2026-11-20)

> Owner, 2026-11-20 about 14:55, in the main mod's session:
>
> 「飞行mod怎么样了？还有，冲锋反制和抵御冲锋的修改都是针对飞行部队，地面部队冲锋效果不要变。我比较好奇为什么到飞行部队身上抵御冲锋的效果就变差了，要不要换个方向，继续调整飞行单位的质量？还是继续调抵御冲锋给的冲锋抗性（冲锋抗性是个单独的属性，你去看一下，不只是质量）、冲锋反制给的伤害？」

- **Constraint (the owner's):** whatever D25 changes applies to flying units only. A ground unit's charge into braced
  infantry stays exactly vanilla. That rules out changing a global `_kv_rules` value (`bracing_*`,
  `charge_reflect_damage_multiplier`) and rules out raising a spear unit's own charge resistance for every charger.
- **He is right about the stat (read from the installed game on 2026-11-20, read-only).** The game has a unit stat
  `scalar_bracing`; the client's Chinese name for it is 「冲锋抗性」
  (`unit_stat_localisations_onscreen_name_scalar_bracing`). Three vanilla ability phases multiply it:
  `wh2_main_lord_passive_glamour_of_hoeth` ×3, `wh3_main_unit_passive_defensive_stance` ×1.25,
  `wh3_main_unit_passive_defensive_stance_buffer` ×1.1 (table `special_ability_phase_stat_effects`, read from its raw
  bytes; control: 21 rows of `stat_bonus_vs_large` parse with the same layout). This repository's records never
  looked at it: `docs/SPEC.md` pillar two describes the brace multiplier only by ranks, direction and the two
  charge-defence attributes. How the engine combines the stat with that multiplier has not been read.
- **Why charge defence does little against a flyer, as far as the records go.** In vanilla a flyer never tests it: the
  engine stops a landed flyer at the first upright enemy whatever the masses (`docs/HISTORY.md` AIR-DIVE-BRACE-W1).
  With this mod's holds the collision decides for the first time, and there a braced soldier's mass times its
  multiplier stays under every flyer's mass. Numbers from the offline survey of 2026-11-20, not re-read by the
  maintainer: Empire spearmen 100, High Elf spearmen 150, the largest multiplier seen in a run 5.43, the cap 10;
  flyers after the mass cut from 1300 (pegasus) to 4425 (star dragon). The exact rule by which the pairwise
  collision uses mass and the brace value is not recorded; that gap is the next thing to close.
- **Direction chosen by the maintainer (technical route; the owner was told):** not a deeper mass cut. Mass makes a
  flyer weaker against everything, not only against a braced line, and no cut within reason brings a dragon under a
  spearman. Instead: scale the engine's own brace value where the two bodies meet, only when the charger is a diving
  flyer, so that the collision still decides and ground chargers see vanilla; the strength is an MCT setting. The
  cost of the dive stays D15's scripted share, raised to the owner's 10%, also an MCT setting. A flyer-only factor on
  the Charge Reflection multiplier is the second step, if that code site lets the target be identified. All of this
  is unverified until the collision code has been read; if it cannot be done for flyers only, the owner is told
  before anything else is tried.
- In-game tests stay paused (D25).

### D27 · What the brace value does in a collision: D26's route would not stop a flyer (2026-11-20)

Maintainer's finding and change of route, about 15:45; no new instruction from the owner. It answers his question in
D26 (「为什么到飞行部队身上抵御冲锋的效果就变差了」) and withdraws the route D26 announced, as D26 promised.

- **What was read** (installed game 9.0.5, read-only, offline; `docs/HISTORY.md` BRACE-READ-1120). The engine keeps
  one brace multiplier per body. In the battle code it meets the body's mass in exactly one place the census found:
  the collision damage formula, where the charger's mass is divided by the struck body's mass times its brace
  multiplier, then multiplied by the relative speed and passed through the `collision_damage_*` rules. Its only other
  road into the collision is a flag, "cannot be pushed", set when brace times mass reaches
  `bracing_immovable_by_small_entity_mass` (600). The two places that honour the flag do so only for a pusher whose
  size class is at most 1 and not above the braced body's own.
- **So D26's route is withdrawn.** Scaling the brace value against a diving flyer would lower the collision damage
  the flyer deals to the braced soldiers. Nothing read says it would slow or stop the flyer.
- **Answer to the owner's question.** Charge defence was never what stops a large body in this engine. The brace
  value protects a braced soldier from impact damage and from being pushed by bodies of its own size class or
  smaller. In vanilla a diving flyer is stopped by a different rule, the engine's brake at the first upright enemy,
  braced or not (`docs/HISTORY.md` AIR-DIVE-BRACE-W1), and this mod removes that brake on purpose. What is left
  against a flyer is the Charge Reflection hit and D15's scripted cost.
- **Not known.** Which code slows a large body that ploughs through small ones; two functions are named as
  candidates and are only partly read. Whether `scalar_bracing` is the unit-level factor inside the brace
  multiplier is likely but unproven. The census has limits (see the HISTORY section).
- **Route from here (maintainer's, technical):**
  1. Offline: read the step that slows the large body. If it compares masses, the lever that fits D25 and D26 is to
     let a braced body's brace multiplier count as mass in that comparison when the pusher is a diving flyer. That
     uses the engine's own number (ranks, facing, the charge-defence attributes, charge resistance); ground chargers
     see vanilla; the strength is an MCT setting. If masses are not compared there, the owner is told.
  2. Offline, independent of 1: D15's cost from 3% to the owner's 10% as an MCT setting with the master switch
     (D25), and a flyer-only factor on the Charge Reflection multiplier. The reflection code names the struck
     charger, so flyers can be told apart there; the patch is designed but not assembled.
  3. Needs the game (paused, D25): a passive probe that logs the flyer's speed and the pair results each tick, to
     confirm 1, then the standard runs.
- Still no deeper global mass cut (D26's reason stands).

### D28 · All flyer mod work moves to this repository's own session (2026-11-20)

> Owner, 2026-11-20 about 16:05, in the main mod's session:
>
> 「这样，飞行mod的所有更新、信息、内容、规则、要求、历史记录，等等等等，所有东西，全部做好交接，发送给飞行mod仓库的会话（我那边开了新会话），所有飞行mod的更新、开发都在那边进行。」

- From this statement on the main mod's session does no flyer work: no research lanes, no documents, no commits in
  this repository. A flyer question asked over there is passed on to this repository's session, not worked on there.
- The handover is `docs/research/2026-11-20-handover.md`: every statement the owner made about this mod on
  2026-11-20, what was read and by whom, what he has and has not been told, what is owed. The three research reports
  of that day are beside it. The commit that adds them is the main session's last one here.
- Handed over unfinished: D25 to D27 (nothing built, nothing measured; the newest reading, BRACE-READ-1120b, has not
  been re-read by anyone and has not been reported to the owner), D23 (not started), the unpushed docs commits
  (a push needs the owner's consent), and the pause on all in-game tests (D25), which only the owner lifts.

### D29 · Stopping a dive at a braced line: extend the engine's "cannot be pushed" rule; mass cut as the fallback; the pause is lifted (2026-11-20)

> Owner, 2026-11-20 about 16:40, in this repository's session, answering one set of questions after being told that the
> engine's physics can only make a braced line hurt more, not stop a flyer:
>
> - Stop the flyer or not (options: extend the engine's "cannot be pushed" rule to a diving flyer / do not stop it,
>   only more damage / a rule at the brake moment): 「1+加伤害，如果不行就减飞行单位的质量」
> - Lift the in-game pause for a log-only probe: 「解除，直接跑。」
> - Push the docs-only commits on `main`: 「现在推」

- **Verified before he was asked** (`docs/HISTORY.md` VERIFY-1120c): the maintainer re-read the addresses
  BRACE-READ-1120b rests on; every one read as the lane said. Mass enters the impulse function `0x142f8d520` and the
  priority test `0x142f95da0` only as stated; neither writes the pusher's velocity. "Nothing slows a large body by the
  small bodies' mass" is still "not found", not "proven absent".
- **The ruling, in the maintainer's words:** (1) a diving flyer is to be stopped, if at all, by the engine's own
  "cannot be pushed" rule (`bracing_immovable_by_small_entity_mass`, brace × mass ≥ 600), extended so that it counts
  against a diving flyer as it counts against a small body (lever A of BRACE-READ-1120b); (2) plus more damage: D25's
  10% cost and a flyer-only factor on Charge Reflection, both MCT settings with the master switch; (3) if lever A, once
  measured, does not stop the flyer, the fallback is a deeper cut of the flyers' mass. That fallback is the owner's
  call and overrides D26's and D27's "no deeper mass cut" for this case; how deep is measured, then reported.
- No rule at the brake moment (option C), as D25 said.
- **The in-game pause (D25) is lifted.** The first run is the log-only probe of BRACE-READ-1120b's unknowns (what the
  `+0x1b0` mark does, whether lever A's flag is reached, what takes the flyer's speed in the block). The machine checks
  of CLAUDE.md still apply (the owner's games, one heavy job at a time, said before it starts).
- Push consent: the docs-only commits on `main` as of this decision, this once.

### D30 · The next version ships the braced-line work and the pull-back fix together (2026-11-20)

> Owner, 2026-11-20 evening, in this repository's session: 「汇报进度，开始推进，发布新版更新」. Asked whether the next
> version waits for both open items (D29's braced-line work; D23's pull-back of models that took off) or ships each as
> it is checked, he chose: 「两件一起发」.

- The next upload carries D29 and D23 together, each built and checked in game first. The upload itself, the page
  text and the D23 comparison picture are still each shown to him and need his go-ahead (D6, D19 to D21, D23).
- Correction of the record: `docs/STATUS.md` and the handover said D23 was "not started". Branch `regroup-1119` has
  three commits from 2026-11-19 evening (`54cf6ce`, `0389a23`, `a71871b`): a per-model recorder, six trace caves and a
  probe-backed partial root cause (an airborne idle model is given a ground enemy as command target, the engine asks
  it to land, it flies back); the unit-level caller is not yet found; guard mode is now set off and recorded in every
  run. None of it is on `main`.

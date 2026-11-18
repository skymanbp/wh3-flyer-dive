"""TEST-ONLY: rewrite the AIR-DIVE-BRACE-W1 §C11 entry in the lane ledger with the final results (CRLF kept)."""
from pathlib import Path

P = Path(r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/docs/CONTENT_LEDGER.md")
raw = P.read_bytes().decode("utf-8")
NL = "\r\n"
OLD_HEAD = "## §C11 AIR-DIVE-BRACE-W1 2026-11-14（进行中，实机暂停）：飞兽冲入架矛 / 戟兵被顿住——探针取证第一段"
NEW_HEAD = "## §C11 AIR-DIVE-BRACE-W1 2026-11-14：飞兽冲入架矛 / 戟兵被顿住——判定为状态锁，两处修根，四批实机对照"
assert raw.count(OLD_HEAD) == 1, "heading not found exactly once"
raw = raw.replace(OLD_HEAD, NEW_HEAD)
cut = raw.index("**没做 / 没验证。** 批 A 只跑了 3 / 69 局")
tail_start = raw.index(NEW_HEAD)
assert raw.find("## ", cut) == -1, "the entry must be the last section"

new = """**三之后（11-14 恢复实机后补）。** 用户恢复实机后批 A 从 A1_wyvern 接着跑完 69 局（被停掉的那一局移到 `runs_aborted/`，重跑）。游戏目录由 `series.py` 每局布置、`finally` 复原；另加 `inflight.json`：每局开跑前写下跑前的 `used_mods.txt` 与本局放进去的测试包，系列被外部强杀时下次启动先按它复原（`probe_recover.py` 是这段的草稿检查，不是项目测试）。

**四、判定：状态锁，不是碰撞（批 A，`batch_a_table.txt` / `batch_a_summary.txt`）。** 早停＝落地后行程不足 15 米就停。单模型局（每局看那一只飞兽本身）长矛 + 戟兵 **21/78**、民兵 **9/39**，30 次早停按停前 1 秒的记录分三类：
- **接触即转近战 13 次**：停前出现 0x14305abb4 的建命令记录，`+0x330` 由冲锋命令 0x143ade800 换成近战命令 0x143ade470，命令目标点＝飞兽自己的位置，`+0x324` 置 1；随后每拍降约 3.0 米/秒（刹车段每拍降速中位数 2.82），正是 `deceleration` 30 的锁步停车，与飞兽质量无关（160–7,000 一律如此）。不是冲击反弹：反弹掷骰 0x1430afae4 在这些停车前后都没有对该飞兽的记录。调用链由记录的栈槽读出：两条接触路径——成对求解 0x143176c6c → 成对碰撞 0x1430731c8 → 0x14305dcac 里 0x14305ddd8 的 `call [rax+0x4b0]`，以及每模型更新那份副本 0x143090e3c → 0x1430912de——都落到虚函数 +0x4b0，其默认实现 0x143075dd8（33 张虚表引用它）装近战命令。
- **落地那一拍结束飞行 16 次**：落地那一拍状态是 0（不是 30 / 33），`dv_keep` 只认 30 / 33，于是放过了结束飞行移动（`+0x710` 4 → 0），随后同样按 30 刹停；`bt`（嗜血狂魔）、`eagle`、`lion`、`storm` 四种都有。第三段记的 A1_storm 那一例就是它。
- 其他 1 次。
架枪兵保持直立、仍是有效的接触对象，民兵会被撞飞，所以长矛 / 戟兵道的早停多于民兵道，但两类机制在民兵道上同样出现。结论按 directive 的二分：**是动作 / 状态锁（b）**，在根上去掉；真正的碰撞（被撞的身体自己的质量、不可推动的架枪兵）保留。

**五、修补（`mod/tools/pipelines/dive_cave_asm.py`，与 AIR-DIVE-RELEASE-W1 的洞同一套装配、Unicorn 检查与故意改坏的变体）。**
- `_fast_test` 把「已落地的状态 0」也算作移动中（`LANDED_IDLE_STATE = 0`，要求 `+0x104` 层＝0），`dv_keep` / `dv_skip` 等共用；`KEEP_LAYER_CASES` 与 3 条状态 0 的变体补上。
- 新洞 `dv_contact`：落地后仍快（过 `_fast_test`）、仍在飞行移动（`+0x710` ≠ 0）、层＝0 的飞兽，进入接战函数时直接返回，不装近战命令，让它带着速度继续冲，直到被撞的身体把它减下来、速度掉到门槛以下才照常转近战。洞的位置改过两次，都是读数逼出来的：v1 在 0x14305dcac（只盖第一条路径，批 B 里接触转近战改从第二条路径进来，13 → 29）；v2 在 0x143123338（这是某一类自己的覆盖，只有 1 张虚表引用它，飞兽不走，批 C 34 次、计数 1）；v3 在两条路径共同的默认实现 0x143075dd8 入口（特征码 `48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 8B 81 24 03 00 00 48 8B F2 48 8B D9 85 C0 74 2F`，exe 内唯一命中）。检查 35 例、故意改坏的变体 33 条全部被抓出。站点表由 `--write-site` 重生（`ld_flyer_dive_site.lua`）；`test_flyer_dive_site.py` 只改了文档串里的洞数，**没跑**（ETEST1）。

**六、四批对照（同一 69 局、同一 1 倍速；`summarize.py` 出表，`batch_{a,b,c,e}_summary.txt`）。**

| 批 | 修补 | 单模型 长矛+戟兵 | 单模型 民兵 | 多模型（领头那只） | 单模型早停的原因 |
|---|---|---|---|---|---|
| A | 无 | 21/78 | 9/39 | 67/90 | 接触转近战 13、结束飞行 16、其他 1 |
| B | 状态 0 + `dv_contact` v1 | 22/78 | — | — | 接触转近战 29、其他 2（结束飞行 16 → 0） |
| C | 状态 0 + v2 | 33/78 | 6/39 | 57/90 | 接触转近战 34、其他 5 |
| E | 状态 0 + v3 | **9/78** | **2/39** | 51/90 | 接触转近战 3、重新下令 1、其他 7 |

批 E 逐种单模型（长矛 / 戟兵 / 民兵，各 3 局）：`bt` / `dragon` / `frostwyrm` / `lion` / `storm` / `taurus` / `lamm` / `cock` 全是 0/9；`wyvern` 4（A 为 3）、`eagle` 4（A 为 4）、`chim` 1、`mant` 1、`terror` 1（标签即 `jobs_e.txt` 里的局名）。多模型局只看领头那一只，混战里噪声大，只作参考。E3_terradon 一局判失败，原因是外部实体读取器的单兵血量与 `unary_hitpoints()` 差 0.11，与俯冲无关。

**七、批 E 余下的 11 次单模型早停逐条读（`batch_e_residuals.txt`，脚本 `resid*.py`）。**
- **速度已经掉到门槛以下才转近战（`dv_contact` 按设计放行）**：E2_chim、E3_mant、E1_eagle 戟兵道——近战命令到来时速度 6.1–7.0 米/秒；E2_eagle、E3_eagle——落地后 1 秒内就只剩约 3 米/秒（巨鹰落地慢），转近战时 2.3–3.0 米/秒。
- **重新下令 1 次**：E1_eagle 民兵道，0x143aed8c8 换命令，状态 30 → 16。
- **目标点被改成自己的位置、冲锋命令却没换（新的一类，4 次）**：E1_wyvern 长矛道与民兵道、E2_wyvern 长矛道、E2_terror 戟兵道。某一拍 `+0x1e0/+0x1e8` 移动目标点由 39–52 米外跳到 0.5–0.8 米（`+0x7f8` 那一组冲锋目标仍在 39–48 米外），`+0x330` 仍是冲锋命令、状态 30，随后每拍降约 3.0 米/秒，速度掉下去 0.1–0.3 秒后接战才放行、近战命令才到。批 A–C 里同样的「目标点归零」7 / 8 / 7 次，**每次都与近战命令同一拍**（近战命令本就把目标点写成自己）；批 E 把装命令拦住之后它才单独露出来，说明还有第二个写目标点的地方。读了接战调用处 0x14305ddd8 之后的代码：调用之后直接收栈返回，不写目标点，所以不是 `dv_contact` 提前返回带出来的副作用。谁写的还没定位。
- **E3_wyvern 长矛道 1 次**：一拍内由 10.8 降到 1.1，进入状态 33、槽 534、标量速度 0，同一拍附近出现不可推动的架枪兵——接近 AIR-DIVE-RELEASE-W1 记过的「开打即清速度」，未细分。

**八、可选战斗加速（协调者转达用户提醒）。** 批 C 跑的途中没改。探针新增可选加速：`series.py --speed=N` 写 `ld_brace_speed.txt`，部署完成时 `bm:modify_battle_speed(N, true)`。同一场景 1 倍与 4 倍各跑两局（龙、狮鹫骑士，`speed_proof.txt` / `speedcmp.py`）：探针采样每模型秒 10 次（狮鹫骑士 40 次）、实体读取每模型秒 5.00 拍，两种速度完全相同（战斗回调走模型时间，外部读取器也按模型时间计拍），实体读取问题 0；落地速度 1 倍 13.7–15.0、4 倍 14.5–15.0；墙钟每局约 130 秒 → 68–79 秒。**但早停数不一样**：龙 1 倍 0/6 道，4 倍 2/6 道（状态 41、槽 540）。所以测量本身经得住加速，早停率不能用 4 倍测；数早停的批一律 1 倍，其他只看测量的检查可以开 4 倍。

**九、发货件。** 独立小模组按 v3 重建：`D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1_scratch/packs/ld_air_dive.pack`，sha256 `cef0a4276851b511a02a7c49a351f3512deb9788f456136e440086f35c76349c`。游戏 `data/` 里那份 `ld_air_dive.pack`（2026-11-13 22:11，sha256 `10dbb275…`）是本车道之前就在的，没动。测试包 `ld_adb_E.pack` sha256 `43ea48a6…`。没建主包，没把 `mod/ld_mod.pack` 拷进工作树。

**没做 / 没验证。**
- 「目标点归零」那一类（批 E 4 次）的写入者没定位；下一步是对 `+0x1e0` 加写入记录再跑一批。修好之前它仍会让少数 `wyvern` / `terror`在 5–14 米停下。
- `dv_contact` 与 `dv_engage` / `dv_attack_move` 共用 `ENGAGED_AT` 计数，战斗日志里的「engage re-paths held off」分不出是哪个洞拦的。
- 多模型局只读领头那一只；4 倍速下早停是否与 1 倍等价没证明（目前的样本说不等价）。
- pytest 一条没跑（ETEST1，等合并后在干净 main 上过测试闸）；没有真联机测试。
- 不合并 main。

**游戏目录现状。** 批 E 跑完后实测：`used_mods.txt` 为空，`data/` 里没有 `ld_adb_*` / 自动测试 / 实体读取包，没有 `inflight.json` 与 `ld_brace_speed.txt`；协调者 11-14 移出的遗留在草稿目录 `game_leftovers_20261114/`。
"""
raw = raw[:cut] + new.replace("\n", NL)
P.write_bytes(raw.encode("utf-8"))
print("ok", len(raw))

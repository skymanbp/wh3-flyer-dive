# 现状与待办

每批收尾时更新。上次更新：2026-11-18（INGAME-1118 实机一轮、D3-1118、INGAME-1118 series 2）。

## 已发布

| 条目 | 版本 | 包 |
|---|---|---|
| 主模组，创意工坊 3840651516 | 提交 `34dfbf3`，2026-11-17 13:11 上传 | `ld_air_dive.pack` 2,597,312 字节，sha256 `e5208882ce11fc4e76a6e5993ff66e4f902728793e2fe3e3cc41fd585f3419ad` |

- `main` 分支的代码 ＝ 这一版。联机协商标记 `LDFLYPN2`（下一版为起飞 `FLYPINS4`、俯冲 `FLYDIVE3`：D9 改名，D3 又换了起飞的）。
- 这一版有一个已知问题：天马类坐骑（飞马、地狱战马、玉龙马）俯冲时骑手和坐骑分离。修复在下一版里，还没发。
- 真人联机从来没跑过（主人 2026-11-13 定为可选、不挡发布）。

## 下一版：分支 `update-1117`，改名在其上的 `rename-1118`（实机核对做了一轮，没发布）

工作树：`D:/Projects/.worktrees/wh3-flyer-dive/update-1117/wt`。内容与数字见 `docs/HISTORY.md` 的 UPDATE-1117。
改名（D9）与 D3 都在分支 `rename-1118`，工作树 `D:/Projects/.worktrees/wh3-flyer-dive/rename-1118/wt`；经过与核对见
`docs/HISTORY.md` 的 RENAME-1118、INGAME-1118、D3-1118。D3 那一批的包在 `D:/Projects/.worktrees/wh3-flyer-dive/d3-1118_scratch/build3/`
（主包 sha256 `83cb3572…`，子模组 `9f936db4…`）。D3 没提交，等主管审。

| 项 | 裁定 | 状态 |
|---|---|---|
| 骑手俯冲时坐稳 | 玩家报告的缺陷 | 已实现；2026-11-18 用改名后的包实机五局，骑手都坐稳（INGAME-1118） |
| 平衡子模组 `flyer_dive_balance.pack` | D1 | 已实现；2026-11-18 两种包名先后下子模组都生效（INGAME-1118），子模组在 `used_mods.txt` 里排在主包之前也生效（INGAME-1118 series 2 第 3 局）：决定同键行的不是 `used_mods.txt` 顺序也不是包名，三局都与「片段名排前者赢」相符。README 加载顺序一段待改 |
| 工坊页面每种语言一份 | D2 | 文字已写（`workshop/`），有两处占位（子模组条目号、D4 那一条） |
| 按体型、逐兵模的起飞判定 | D3 | 已实现并离线核对（D3-1118：体型字段 2026-11-18 实测成立，协商标记 `FLYPINS4`）；2026-11-18 实机一局两条判据都过（窗口 `45/40/35/30/45`，`unsized=0 unmatched=0`，held 3763、free 33293，INGAME-1118 series 2 第 1 局）。各体型实际离地快慢没量出来（只有整队 flying 标志），欠一局逐兵模的 |
| 俯冲撞上冲锋反制受双倍伤害 | D4 | 没实现。地面骑兵对照组 5 局都没看到反射（飞兽 12 局也没有）；2026-11-18 带新探针那局：`ACTION UPDATES 0`、`BRACE CHECK NOT REACHED`——长矛兵根本没进入能调用反射检查的动作（INGAME-1118 series 2 第 2 局）。欠一局改摆兵的（要改测试驱动） |
| 落地后第二次撞穿 | D5（评估，非裁定） | 不改代码 |
| 与主模组仓库断开（代码侧） | D6 | 已做完并核对：测试 84 项全过，两个包的字节没变，运行时不读主模组仓库（`docs/HISTORY.md` HOME-1117 第二节） |

`main` 上只有文档和规矩（`CLAUDE.md`、`docs/`、`.claude/`）是新的，代码仍是已发布的那一版；
断开用的代码改动在本分支，随下一版一起进 `main`。

### 欠的实机测试（三局，约 12 分钟；游戏空着才能跑，一次一件）

**2026-11-18 02:41–02:53 三局都跑了**（INGAME-1118 series 2，`docs/HISTORY.md` 同名一节；证据 `ingame_1118/series2/`）：第 1 项判据通过，
但离地快慢只量到整队标志，欠一局逐兵模的；第 2 项挡在动作这一层（`ACTION UPDATES 0`），欠一局改摆兵的；第 3 项已有答案。下面各项后面写了结果和还欠什么。

命令都在 `rename-1118/wt` 的 `mod/` 目录下跑。包都在 `D:/Projects/.worktrees/wh3-flyer-dive/d3-1118_scratch/probes/`：
`base/flyer_dive_takeoff.pack`（D3 的主包加移动记录器，sha256 `555afdd2…`）、`base/flyer_dive_balance.pack`、`probe_impact.pack`
（主包加冲锋反制探针，`9ba1b2fb…`）、`pin_record.pack`（只有起飞记录器）、`size_reader.pack`（只有体型读取器）。按每项写的拷进游戏
`data/`，跑完移走。**每局开跑前删掉游戏目录里的 `flyer_size_probe.txt`、`reflect_probe.txt`、`pin_probe.txt`**（它们是追加写的，
2026-11-18 那一轮就因此拷出了旧文件，INGAME-1118）。

1. **D3 起飞**（约 4 分钟）。拷 `base/flyer_dive_takeoff.pack`、`pin_record.pack`。
   `python -P tools/pipelines/air_dive_autotest.py --test-pack flyer_dive_takeoff.pack --pack-after pin_record.pack --memreader --scenario engage --cmd scenario=cycle,fight_ms=90000,cycle_away_ms=8000 --target wh_main_emp_inf_swordsmen --flyers wh2_main_def_inf_harpies,wh_main_brt_cav_pegasus_knights,wh2_dlc10_def_mon_feral_manticore_0,wh2_main_hef_mon_star_dragon`
   - 判定：`flyer_takeoff.txt` 的 BATTLE 行有 `windows by size small/medium/large/very large/unknown 45/40/35/30/45 ticks`；
     `pin_probe.txt` 最后一条 S 行 `unsized=0 unmatched=0`，且 `held` 与 `free` 都大于 0。`unmatched` 大于 0 说明发问兵模的飞行控制器
     不是表里那个实体的，规则形同放行，要先查再发。
   - 另看：hp 文件 F 行里每次 `cycle away` 之后到 `flying` 变 1 的秒数，四道都要能离地。
   - **结果（series 2 第 1 局）**：判据通过——`… 45/40/35/30/45 ticks`；最后 S 行 `held=3763 free=33293 unsized=0 unmatched=0`。
     F 行的 `flying` 是整队的：24 次撤退令里 6 秒内整队离地只有 1 次（蝎尾狮，0.7 秒），而且不在近战、窗口内没挨打的单位也常不变 flying，
     所以这个指标量不出 D3。**还欠一局**：同一命令加 `--entity-read`（逐实体飞行状态），最好再让目标撤走（`retreat_<i>`）免得撤退途中一直挨打。
2. **冲锋反制对照组**（约 3 分钟）。拷 `probe_impact.pack`。
   `python -P tools/pipelines/air_dive_autotest.py --test-pack probe_impact.pack --memreader --target wh_main_emp_inf_spearmen_1 --flyers wh_main_brt_cav_knights_of_the_realm,wh_main_brt_cav_knights_of_the_realm,wh_main_brt_cav_knights_of_the_realm,wh_main_brt_cav_knights_of_the_realm`
   然后 `python -P tools/pipelines/reflect_probe_report.py "<游戏目录>/reflect_probe.txt"`（自动判定会写 FAIL，骑兵不会「落地」）。
   - 看到反射：`CONTROL SEEN`、`reflections logged` 大于 0，骑士那一节有 `<- the reflection's damage call`（两个洞各自独立）。
   - 没看到时按两行读：`ACTION UPDATES 0` → 长矛兵没进入能调用反射检查的动作，下一步改摆兵（目标不收归脚本控制）；
     `BRACE CHECK REACHED` 而反射者不是 `0x69` → 挡在 `Back`；是 `0x69` 而第一个敌人状态是 12/15/16/17 或距离不在半径内 → 挡在那一道。
     这一局只回答「挡在哪」；之后可能还要一局验证改法。
   - **结果（series 2 第 2 局）**：`ACTION UPDATES 0`、`BRACE CHECK NOT REACHED 0 calls`、`CONTROL NOT SEEN`；扣血记录活着（683 次）。
     挡在长矛兵的动作这一层。**下一局**：同一命令加 `--cmd free_targets_ms=0`——测试驱动 2026-11-18 加了这个开关：摆好位之后把每道的目标
     交还给它那一方的电脑（`uc:release_control()`，原版 `lib_battle_script_unit.lua:1067` 的同一个调用；默认 -1 不放）。驱动在状态文件里
     每道写一行 `free_target <i> ok=true`，先确认这行在；再看 `ACTION UPDATES` 是否大于 0。放开之后目标可能自己走开，
     所以这一局只回答「不受脚本控制时长矛兵会不会进入那个动作」。开关只过了语法检查，没进过游戏。探针包不用重建（驱动随它自己写的辅助包进游戏）。
3. **子模组换序：片段名还是 `used_mods.txt` 顺序**（约 3 分钟）。拷 `base/flyer_dive_takeoff.pack`、`base/flyer_dive_balance.pack`、`size_reader.pack`。
   `python -P tools/pipelines/air_dive_autotest.py --test-pack flyer_dive_takeoff.pack --pack-before flyer_dive_balance.pack --pack-after size_reader.pack --memreader --flyers wh2_main_def_inf_harpies,wh_main_brt_cav_pegasus_knights,wh2_dlc10_def_mon_feral_manticore_0,wh2_main_hef_mon_star_dragon`
   然后 `python -P tools/pipelines/flyer_size_probe_report.py "<游戏目录>/flyer_size_probe.txt"`。
   - 子模组列在主包之前，包名不变。蝎尾狮 `+0xb4` 读 1700、星龙 4425 → 片段名决定（排前者赢）；读 2000、5900 → `used_mods.txt` 里排后者赢。
     驱动在时间线里写出 `used_mods:` 一行，先确认顺序真是子模组在前。
   - **结果（series 2 第 3 局）**：时间线 `used_mods: mod "flyer_dive_balance.pack"; | mod "flyer_dive_takeoff.pack"; …`（子模组在前）；
     蝎尾狮 1700、星龙 4425，`BALANCE submod loaded`。所以不是 `used_mods.txt` 里排后者赢；三局都与「片段名排前者赢」相符（片段名没反过来验）。

D4 的飞兽各道（INGAME-1118 第 4、5 项的样子）要等 D4 有了做法再跑。真人联机仍是可选。

### 测完之后

- 第 1 项通过 → D3 进下一版。
- 第 2 项 → 选定 D4 的做法并实现。做不到「受伤但不被弹回」就回去问主人。
  若量出俯冲的那一下和飞兽平常的地面冲锋走的是同一条引擎路径，先告诉主人再发。
- 第 3 项 → 把结论写进 README 的加载顺序一段（现写的是「包名或片段名，不论哪个都成立」）。
- 全部实机核对过 → 合进 `main`，然后**问主人**：推送、上传新版、建子模组的工坊条目、把页面换成分语言版本。

## 其他待办

| 事 | 来由 | 状态 |
|---|---|---|
| 落地冲锋后滑行停不住，查根因 | 主人 2026-11-14 提出，疑转身动作被关 | 没开始。四组对照：现状 / 只恢复转身动作 / 只恢复原版刹车 / 两样都恢复；不得退回「15 米内提前停下」 |
| 俯冲时兵模忽上忽下 | 主人 2026-11-14 在皇家马鹫测试里看到 | 引擎侧已修（720 次里 78 次降到 1 次），等主人在游戏里看一眼 |
| 评论区两条回复 | 2026-11-17 | 起草后交主人自己发：①「是不是所有飞兽都免疫架矛」——不是，大型单体不被早停，飞马骑士 6 局里 5 次被拦停；②骑手分离——下一版修 |
| 主模组适配包 | D6 | 等主模组改完名。输入是 `mod/tools/data/` 里的快照；包里现在不含主模组的飞兽 |
| 已发布名字里的 `ld_` | D9（2026-11-18「这一版就改」） | 分支 `rename-1118`（建在 `update-1117` 上）已改完并离线核对（`docs/HISTORY.md` RENAME-1118）；2026-11-18 实机：新脚本路径加载、新日志名写出（`flyer_dive.txt`、`flyer_takeoff.txt`），骑手与子模组各局通过（INGAME-1118）。主包改叫 `flyer_dive_takeoff.pack`；对 `kaylika_auri_lahmians`、`lbm` 没有同键行，包名先后不影响它们（D3-1118 第三节） |
| 随包脚本里的「Lore Disasters」字样 | 断开时留下 | 已随 D9 在 `rename-1118` 改掉（协商标题改为 `Flyer Dive: …`）。原记：两个战役入口脚本交给联机协商的标题（`title = "Lore Disasters flyer …"`，联机时可能显示给玩家）和一处注释。改它会改变包的字节，下一版重建包时一起改 |
| 开发用环境变量名 `LD_*` | 断开时留下 | 已随 D9 在 `rename-1118` 改为 `WH3_DATA`、`WH3_ROOT`、`MEMREADER_DIR`、`WH3_DB_PACK`、`WH3_GAME_EXE`。原记：五个（`LD_WH3_DATA`、`LD_WH3_ROOT`、`LD_MEMREADER_DIR`、`LD_VANILLA_DB_PACK`、`LD_GAME_EXE`）。不进包，不影响玩家；要改就五个一起改 |
| 两个订阅模组的骑乘单位可能骑手分离 | D3-1118 第三节 | `lbm` 的飞马骑士（剑盾）与 `kaylika_auri_lahmians` 的 5 个吸血鬼骑乘单位骑着本模组改指过飞行表的坐骑行，骑手表仍是原版；按 UPDATE-1117 第一节的机制会分离。没实机看过；要修得给别人的单位也改指骑手表（兼容补丁），先问主人要不要做 |
| 许可证文件 | 建仓库时留给主人定 | 没加 |
| 真人联机实测 | 可选 | 没跑过 |

## 东西在哪

| 东西 | 位置 |
|---|---|
| 下一版的研究、探针脚本、建出来的包 | `D:/Projects/.worktrees/wh3-flyer-dive/update-1117/`（`design.md`、`static_B_C.md`、`scripts/`、`impl_scripts/`、`build/`） |
| 2026-11-17 这一晚的对照包、截图、探针 | `D:/Projects/.worktrees/wh3-flyer-dive/session_1117/` |
| 从主模组草稿区搬来的全部旧数据（24.4 GiB） | `D:/Projects/.worktrees/wh3-flyer-dive/from_lore_disaster/`，清单见 `docs/HISTORY.md` 的 DATA-MOVE-1117 |
| 上传用的文件 | `from_lore_disaster/flyer-publish_scratch/`，用法见 `docs/WORKSHOP.md` |
| 仓库里的两批旧证据 | `mod/tools/evidence/` |

## 推送状态

- `main` 已推到 GitHub（2026-11-17 夜，主人同意，`docs/DECISIONS.md` D8）：内容是已发布的那一版代码，加上搬进来的
  规矩与记录。
- `rider-seat-1117`（`c658e17`）、`update-1117`（`e0018f5`、`d635f71` 及其后的搬家提交）只在本机，等实机核对完再问。
- `rename-1118`：只在本机；改名那批未提交，D3-1118 也未提交。
- 以后每次推送都要主人同意。

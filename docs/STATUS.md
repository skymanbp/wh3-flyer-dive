# 现状与待办

每批收尾时更新。上次更新：2026-11-19 下午（欠的四项实机核对做完，十一局都判通过：正式包本身生效、真的 MCT 的设置页与读取顺序、「只算正面」的拒付、多兵模付钱数；D18，`docs/HISTORY.md` INGAME-1119；上传与推送还没问主人）；此前 2026-11-19 上午（主人定了俯冲撞架矛步兵的代价：四种体型都用 3%，D15；分支再推一次，D17；`docs/HISTORY.md` ANSWERS-1119）；此前 2026-11-19 凌晨（D15 按统一标准实机量了三局，都判通过：撞架矛的长矛兵，星龙、蝎尾狮各扣 3.0%，狮鹫骑士整队 1.5%，飞马骑士整队 0.8%；撞剑士零扣血，`docs/HISTORY.md` D15-STD-1119；此前 2026-11-18 夜：D15 的测试用加长记录离线建好，并查到游戏脚本自带的扣血接口，先试它，`docs/HISTORY.md` D15-PROBE-1118；头两局实机跑了：记号、攻击方、满血读数都对，架矛的判定条件选错、一次没扣到血，对照局不成立，`docs/HISTORY.md` D15-INGAME-1118；判定条件已离线改成兵模 +0x68 的第 3 位、加了「带冲锋反制属性」这一关（129 个单位）、对照局换成剑士，D15-BRACE-1118；第二组两局实机验过：撞架矛的长矛兵扣到血（星龙、蝎尾狮各 3%），撞剑士零扣血，D15-INGAME2-1118；规则已离线做进正式包（各体型暂按 3%，只算正面 80 度内的接触，D15-SHIP-1118；新包没进过游戏）；实机测试回到统一标准、只留一个入口，今天各局都是旧场景跑的，D15 的数要按标准重量（TEST-STD-1118）；此前：D15 的离线设计停在「怎么凭空扣这一下」，下一步带加长记录进游戏跑一局，`docs/HISTORY.md` D15-DESIGN-1118；此前：重读旧记录定了 D15 的做法方向：只调大倍数行不通，伤害要落在俯冲接触的那一刻，`docs/HISTORY.md` D15-ANALYSIS-1118；此前同日傍晚：主人答了 D4 的两问（D15），分支再推一次（D16）；此前同日午后：D10-1118 一个包与吹息开关、PROBES-1118 两套探针，都只做到离线；主人的四条新裁定 D10–D13；此前：INGAME-1118 实机一轮、D3-1118、INGAME-1118 series 2 与 series 3）。

## 已发布

| 条目 | 版本 | 包 |
|---|---|---|
| 主模组，创意工坊 3840651516 | 提交 `34dfbf3`，2026-11-17 13:11 上传 | `ld_air_dive.pack` 2,597,312 字节，sha256 `e5208882ce11fc4e76a6e5993ff66e4f902728793e2fe3e3cc41fd585f3419ad` |

- `main` 分支的代码 ＝ 这一版。联机协商标记 `LDFLYPN2`（下一版为起飞 `FLYPINS5`、俯冲 `FLYDIVE4`：D9 改名，D3 与起飞空当的修法各换了一次起飞的，D15 做进正式包换了一次俯冲的）。
- 这一版有一个已知问题：天马类坐骑（飞马、地狱战马、玉龙马）俯冲时骑手和坐骑分离。修复在下一版里，还没发。
- 真人联机从来没跑过（主人 2026-11-13 定为可选、不挡发布）。

## 下一版：分支 `update-1117`，改名在其上的 `rename-1118`（实机核对做了一轮，没发布）

工作树：`D:/Projects/.worktrees/wh3-flyer-dive/update-1117/wt`。内容与数字见 `docs/HISTORY.md` 的 UPDATE-1117。
改名（D9）与 D3 都在分支 `rename-1118`，工作树 `D:/Projects/.worktrees/wh3-flyer-dive/rename-1118/wt`；经过与核对见
`docs/HISTORY.md` 的 RENAME-1118、INGAME-1118、D3-1118。D3 那一批的包在 `D:/Projects/.worktrees/wh3-flyer-dive/d3-1118_scratch/build3/`
（主包 sha256 `83cb3572…`，子模组 `9f936db4…`）。D3 已提交（`f56bc6b`）。

**2026-11-18 主人新裁定（`docs/DECISIONS.md` D10–D16）。发版前要做完的事是这四件，做完再问主人上传：**

1. **改回一个包**（D10）：子模组撤回，「接战时可用吹息」和「大型飞兽质量下调」放回主包；接战时能不能用吹息做成 MCT（模组设置工具）里的开关，默认开。
   离线做完（D10-1118；主管重建了包并读包里的字节核对过，`docs/HISTORY.md` 同名一节）：建包只写 `flyer_dive_takeoff.pack`，质量下调与吹息表回到主包（与两包版逐格相同）；
   开关的做法是「表照旧放开（＝开），关时由战斗脚本 `flyer_breath.lua` 每个战斗时刻按原版两条限制逐兵禁用吹息」。多人战役的战斗同样按这个设置（MCT 把主机的设置发给每一台机器，D14）；战役之外的多人战斗固定为开（那里 MCT 各读各的）。
   README、`workshop/`、`CLAUDE.md` 已改成一个包的写法。**实机核对过了**（series 4，2026-11-18：不装 MCT、替身设置说关、说开各一局，另有带扣血记录的开 / 关各一局）；真的 MCT 也看过了（INGAME-1119，2026-11-19）。
2. **俯冲撞上架好的长矛受伤**（D4）：主人定「做完一起传」（D11）。离线查出原版自己就会让冲锋的一方受伤，而且是两条路（架好的反制兵的普通攻击对冲锋者翻倍；另有一条撞击反射），旧探针两条都没挂上。实机量到了（series 4 第 2、3 局）：原版就是架好的兵打冲锋者的那一下 × 2，飞兽俯冲同样触发，对大型单体几乎不疼。**D4 本身没做。主人答了两问（D15）**：数值交给主管定（确实掉血、但不超标，定之前先实测并把数字报给主人）；只算俯冲。**2026-11-18 夜：已按 D15 离线做进正式包（D15-SHIP-1118），还没在标准场景下实机量过，数没定。** **2026-11-19 凌晨：标准场景下量过了（D15-STD-1119）**：撞架矛的长矛兵，星龙 282 点（满血的 3.0%，三条龙三次一模一样）、蝎尾狮 153 点（3.0%）、狮鹫骑士 4 个兵模里 2 个付了共 170 点（整队 1.5%）、飞马骑士 24 个兵模里 6 个付了共 49 点（整队 0.8%）；撞剑士 0 次。主管拟四种体型都用 3%，实测数已报给主人。**2026-11-19 上午主人答：「就用 3%」（D15），数定了。**
3. **起飞那一两个时刻的空当**：主人定「查清再发」（D11）。**查清并修掉了**（series 4 第 1、6 局）：阶段 2、倒计时为 0 时引擎抬兵模之前不问规则；修法是记挨打时把为 0 的倒计时抬到 1，联机协商标记换成 `FLYPINS5`。
4. 以上三件的实机核对：第 1、3 件做完；第 2 件要先实现再测。

别人模组的 6 个骑乘单位的兼容补丁先不做（D12）。

| 项 | 裁定 | 状态 |
|---|---|---|
| 骑手俯冲时坐稳 | 玩家报告的缺陷 | 已实现；2026-11-18 用改名后的包实机五局，骑手都坐稳（INGAME-1118） |
| 一个包，接战吹息做成 MCT 开关 | D10 | 实机核对过（series 4，2026-11-18；真的 MCT 2026-11-19 看过：设置页、读取顺序、改成关后下一场生效，INGAME-1119）：表照旧放开（开＝已发布的行为，不需要 MCT 也不需要 memreader Plus）；关时 `script/battle/mod/flyer_breath.lua` 每 100 毫秒对拥有这 20 个吹息之一的部队调用 `disable_special_ability`（陷入近战 → 禁用；原版另带 `grounded` 的 12 个在没飞起来时也禁用），写 `flyer_breath.txt`。多人战役的战斗按主机的设置，战役之外的多人战斗固定为开（D14）。LuaJIT 测试 `test_breath_switch.py`；多人战斗没有实机跑过 |
| 平衡子模组 `flyer_dive_balance.pack` | D1，2026-11-18 撤回（D10） | 已并回主包（离线）：主包的飞兽行＝两包版主包的行＋子模组的质量格，逐格相同；吹息表与两包版子模组里的逐字节相同（`test_one_pack.py`）。此前的实机记录（片段名排前者赢）留作与别的模组冲突时的参考，写在 README |
| 工坊页面每种语言一份 | D2 | 文字定稿方式改了（D20，2026-11-19）：以线上原文为底拆成中英两页，只做主人逐条点过头的改动（`docs/HISTORY.md` PAGE-1119b；此前重写的那一版作废）；分语言栏位怎么写进 Steam 还没试；更新说明草稿在 `workshop/flyer_dive/changenote.txt`。子模组那一份已删；主页面已写回吹息、质量两段和「设置」一节（MCT 开关；多人战役里以主机的设置为准，D14） |
| 按体型、逐兵模的起飞判定 | D3 | 已实现并离线核对（D3-1118：体型字段 2026-11-18 实测成立，协商标记当时是 `FLYPINS4`，起飞空当修掉后是 `FLYPINS5`）；2026-11-18 实机一局两条判据都过（窗口 `45/40/35/30/45`，`unsized=0 unmatched=0`，held 3763、free 33293，INGAME-1118 series 2 第 1 局）。各体型实际离地快慢已逐兵模量出（series 3），四种都对得上；剩一两个时刻的空当，主人定「查清再发」（D11） |
| 俯冲撞上冲锋反制受双倍伤害 | D4 | 已做进正式包（D15-SHIP-1118）；标准场景下实机量过（D15-STD-1119，2026-11-19：撞架矛的长矛兵星龙 3.0%、蝎尾狮 3.0%、狮鹫骑士整队 1.5%、飞马骑士整队 0.8%，撞剑士 0）；主人 2026-11-19 定：四种体型都用 3%（D15）。正式包本身进过游戏、「只算正面」的拒付也见到了（INGAME-1119，2026-11-19）。此前：2026-11-18 series 4 量到了原版的做法（架好的兵那一下 × 2，俯冲与地面冲锋同一条路）；主人已答（D15：数值主管定，只算俯冲），待实现；做法方向已定（不靠调大倍数，俯冲接触时按兵模满血比例扣一次，D15-ANALYSIS-1118）；离线设计停在怎么扣这一下（D15-DESIGN-1118）；测试用的加长记录已离线建好，先试游戏脚本自带的扣血接口，头两局实机跑了（D15-INGAME-1118）：俯冲记号、攻击方、满血读数都对；架矛的判定条件选错，一次没扣到血；对照局不成立。判定条件已离线改好（D15-BRACE-1118：兵模 +0x68 第 3 位；只对带冲锋反制属性的 129 个单位算；对照局换成撞剑士）。第二组两局实机（D15-INGAME2-1118）：判定对了，游戏自带的扣血调用确实执行，撞长矛兵扣到血、撞剑士零扣血。报告已修，规则已离线做进正式包（D15-SHIP-1118：各体型暂按 3%，只算正面 80 度内的接触，联机协商标记 `FLYDIVE4`）。按统一标准重新量过了（D15-STD-1119）。此前的记录：地面骑兵对照组 5 局都没看到反射（飞兽 12 局也没有）；2026-11-18 带新探针那局：`ACTION UPDATES 0`、`BRACE CHECK NOT REACHED`——长矛兵根本没进入能调用反射检查的动作（INGAME-1118 series 2 第 2 局）。改摆兵那一局已跑（series 3 第 2 局），结果一样；下一步从扣血那一头找。主人定「做完一起传」（D11）。**2026-11-18 午后离线（PROBES-1118）**：装好的游戏数据里带 `charge_reflection` 的陆军单位是 129 个（D4 写的 136 对不上），规则值 `charge_reflect_damage_multiplier` 2、门槛 0.7；引擎里只有伤害计算函数读这两个值，它把架好的反制兵打冲锋者的伤害乘 2，另有一条撞击反射按伤害类别 0 扣血。也就是原版本来就会伤到冲锋者，D4 多半不用另造伤害来源。新探针挂在乘 2 的那两处，离线核对过，没进过游戏 |
| 落地后第二次撞穿 | D5（评估，非裁定） | 不改代码 |
| 与主模组仓库断开（代码侧） | D6 | 已做完并核对：测试 84 项全过，两个包的字节没变，运行时不读主模组仓库（`docs/HISTORY.md` HOME-1117 第二节） |

`main` 上只有文档和规矩（`CLAUDE.md`、`docs/`、`.claude/`）是新的，代码仍是已发布的那一版；
断开用的代码改动在本分支，随下一版一起进 `main`。

### 实机测试的统一标准（2026-11-18；来由见 `docs/HISTORY.md` TEST-STD-1118）

只有一个入口：`tools/pipelines/flyer_run.py`（单局 `one`，成批 `list`），驱动 `air_dive_autotest.py` 只由它调用。机器忙（主人的游戏、别的游戏、重活锁、pytest / 建包）就拒绝，不等待、不碰正在运行的游戏；跑的时候持有重活锁；被杀掉的一局下次启动先复原。输出放在 `D:/Projects/.worktrees/wh3-flyer-dive/runs/`，不进仓库。标准场景：平坦地图 mp_crossroads_flat、道间距 175 米、同时冲锋、无集结区、目标关散兵与自由开火并开近战、1 倍速、相距 250 米。偏离标准要明说，状态文件和 run.json 会写出来（2026-11-19 起，带 `--cmd` 额外控制项的局也算偏离）。每种记录只有一个报告脚本（`reflect_probe_report.py` 等）。每种飞兽重复几次，还没定。

**这三局 2026-11-19 凌晨跑完了，都判通过**（D15 按标准重新量；结果在 `docs/HISTORY.md` D15-STD-1119，输出在 `D:/Projects/.worktrees/wh3-flyer-dive/runs/` 下三个同名目录）。**当时欠的四项 2026-11-19 下午都做完了**（十一局都判通过，`docs/HISTORY.md` INGAME-1119）：① 正式包本身进了游戏，撞长矛兵扣血、撞剑士不扣；② 真的 MCT：设置页、读取顺序、改成关后下一场生效都看到了；③「只算正面」的拒付见到了（长矛兵背对时 61 次接触全部不付）；④ 多兵模的飞兽各量了 6 次俯冲（狮鹫骑士每次 4 个里 2 个付，飞马骑士 24 个里 3 到 6 个付）。**实机核对到此没有欠的；下一步是问主人：上传新版、换页面、推送、合进 `main`。**当时的命令留作记录（在 `rename-1118/wt/mod` 下跑）。`P` ＝ `D:/Projects/.worktrees/wh3-flyer-dive/d15-1118_scratch/lane/probe5/probe_d15.pack`：

```
python -P tools/pipelines/flyer_run.py one std_base_dragon3 --deploy P=probe_d15.pack -- --test-pack probe_d15.pack --memreader --flyers wh2_main_hef_mon_star_dragon,wh2_main_hef_mon_star_dragon,wh2_main_hef_mon_star_dragon --target wh_main_emp_inf_spearmen_1
python -P tools/pipelines/flyer_run.py one d15std_spear --deploy P=probe_d15.pack -- --test-pack probe_d15.pack --memreader --target wh_main_emp_inf_spearmen_1 --flyers wh2_main_hef_mon_star_dragon,wh2_dlc10_def_mon_feral_manticore_0,wh2_dlc15_hef_inf_mistwalkers_griffon_knights_0,wh_main_brt_cav_pegasus_knights
python -P tools/pipelines/flyer_run.py one d15std_sword --deploy P=probe_d15.pack -- --test-pack probe_d15.pack --memreader --target wh_main_emp_inf_swordsmen --flyers wh2_main_hef_mon_star_dragon,wh2_dlc10_def_mon_feral_manticore_0,wh2_dlc15_hef_inf_mistwalkers_griffon_knights_0,wh_main_brt_cav_pegasus_knights
```

**下面两节（「欠的实机测试」「series 4 实机」）是已经跑过的记录**：那些命令直接调驱动、手工拷包删旧文件，而且都是在旧场景（有坡的旧地图）上跑的。以后的局一律走上面的入口，拷包、删旧记录、收日志都由它做；`series3/run_series3_c.sh` 调用的 `run_one_s3.sh` 已删，只能当记录看。

### 欠的实机测试（三局，约 12 分钟；游戏空着才能跑，一次一件）

**2026-11-18 02:41–02:53 三局都跑了**（INGAME-1118 series 2，`docs/HISTORY.md` 同名一节；证据 `ingame_1118/series2/`）：第 1 项判据通过，
但离地快慢只量到整队标志，欠一局逐兵模的；第 2 项挡在动作这一层（`ACTION UPDATES 0`），欠一局改摆兵的；第 3 项已有答案。下面各项后面写了结果和还欠什么。

**2026-11-18 04:35–04:58 又跑了四局**（INGAME-1118 series 3，`docs/HISTORY.md` 同名一节；证据 `ingame_1118/series3/`）：第 1 项逐兵模量出来了，四种体型的离地时间都对得上，另有一处一两个时刻的空当记在第 1 项里；第 2 项把目标放开后仍是 `ACTION UPDATES 0`，原因不在脚本控制。

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
     所以这个指标量不出 D3。**还欠一局**逐兵模的。原先写的「同一命令加 `--entity-read`」跑不了：那个逐兵模读取器和它的建包脚本在拆模组时
     留在了韧性模组，本仓库只剩读数脚本（2026-11-18 查出；驱动现在一开始就拒绝这个参数并说明原因）。改用本仓库自己的起飞记录器：
     它加了两种行（`E` 逐实体的离地标志与起飞阶段、`Z` 逐实体体型），在游戏目录的 `pin_probe.cfg` 里写 `entities 1` 和 `sample 100` 打开；
     `pin_record.pack` 要用新记录器重建。命令同上，`--cmd` 里再加 `retreat_1=39000,retreat_2=39000,retreat_3=39000,retreat_4=39000`
     （第三次撤退令那一刻目标也撤走，之后不再追打）。跑完 `python -P tools/pipelines/pin_probe_report.py "<游戏目录>/pin_probe.txt"`：
     每个飞兽一行，给出各兵模「最后一次挨打到离地」的时刻数；早于本体型窗口就判失败，预期在「窗口 + 30」上下（窗口过后引擎自己的 3 秒还要走完）。
     记录器的新行只过了离线测试（LuaJIT 跑真文件，`test_pin_probe_entities.py`），没进过游戏。
   - **结果（series 3 第 1、3、4 局，逐兵模）**：记录器的 `E`、`Z` 行在游戏里可用。「最后一次挨打到离地」的最小值：小型（鹰身女妖，窗口 45）77 个时刻、12 个样本；中型（飞马骑士，40）72、3 个样本；大型（蝎尾狮，35）67、1 个样本；超大（星龙，30）62、3 个样本。四种都是「窗口 + 30 + 2」，没有一个早于「窗口 + 30」。
     第 1 局的剑士伤不到两只大怪（它们血量一直是满的，所以没有挨打记录），大型和超大是第 3 局换长戟兵量的
     （`ingame_1118/series3/run_series3_c.sh`：`--target wh_main_emp_inf_halberdiers`，`cycle_away_ms=16000,cycle_back_ms=16000,retreat_<i>=52000`）。
   - **对照（series 3 第 4 局，`pin_probe.cfg` 里 `mode 2`：照记挨打，但由游戏自己的判定回答）**：同一场仗里，没挨打的星龙收到撤退令后被按住 128 个时刻（uid 1005：第 526 个时刻被要求起飞，第 654 个时刻才离地，其间没有一次挨打记录），另一只到下一次进攻令都没起来；
     装了规则的第 3 局里同样情形是下令后 1 个时刻离地。这就是 D3 要的差别。
   - **一处没对上，记着**：第 3 局一只蝎尾狮（uid 1002）落地后 12.7 秒没挨过打，第 204 个时刻第一次挨打，第 205 个时刻收到撤退令，第 206 个时刻离地——挨打后 2 个时刻就走了，`pin_probe_report.py` 判为问题（退出码 1）。同一局里倒计时没走完时挨的打都压住了
     （星龙 uid 1004 被要求起飞后又挨 6 下，最后一下之后 62 个时刻才离地）。所以漏的是「倒计时早已到 0、刚挨第一下、紧接着下令」这一两个时刻；
     是引擎在下令那一刻不再问一遍，还是问得比每时刻一次稀，这一局分不出来。要查清得给记录器加「起飞判定被问了几次」的计数再跑一局。
     影响小（要 10 秒以上没挨打、又恰好卡在这一两个时刻）。主管原先判断不挡发版；**主人 2026-11-18 定「查清再发」（D11）**，所以加计数的那一局要跑。对外说明里不写「挨打就一定走不了」。
   - **顺带量到**：每次落地，游戏自己把起飞倒计时置成 100（`E` 行 `0:1:100`；第 4 局由游戏自己判定时也一样），所以飞兽落地后至少 10 秒不能再起飞，挨没挨打都一样。这是原版行为，不是本模组加的。
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
   - **结果（series 3 第 2 局，`free_targets_ms=0`）**：状态文件里四道都有 `free_target <i> ok=true`；骑士冲进长矛兵，扣血记录 679 次，但 `ACTION UPDATES 0`、`BRACE CHECK NOT REACHED 0 calls`、`reflections logged 0`、`CONTROL NOT SEEN`。
     目标受不受脚本控制，结果一样，所以「脚本控制挡住了那个动作」这个猜想不成立。剩下两种可能，都没验证：探针挂的两处不是这种交战真正走的函数；或者这一对兵种在这种打法下游戏本来就不结算反射伤害。
     下一步不是再换摆法，而是从扣血这一头找：扣血函数的记录是活的，给它加上按伤害类别的计数，再找一组确定会出现反射伤害的对局（先查原版数据里哪些单位带反射属性、规则表里反射伤害的数值），看它走哪一类。D4 在这之前定不了做法。
3. **子模组换序：片段名还是 `used_mods.txt` 顺序**（约 3 分钟）。拷 `base/flyer_dive_takeoff.pack`、`base/flyer_dive_balance.pack`、`size_reader.pack`。
   `python -P tools/pipelines/air_dive_autotest.py --test-pack flyer_dive_takeoff.pack --pack-before flyer_dive_balance.pack --pack-after size_reader.pack --memreader --flyers wh2_main_def_inf_harpies,wh_main_brt_cav_pegasus_knights,wh2_dlc10_def_mon_feral_manticore_0,wh2_main_hef_mon_star_dragon`
   然后 `python -P tools/pipelines/flyer_size_probe_report.py "<游戏目录>/flyer_size_probe.txt"`。
   - 子模组列在主包之前，包名不变。蝎尾狮 `+0xb4` 读 1700、星龙 4425 → 片段名决定（排前者赢）；读 2000、5900 → `used_mods.txt` 里排后者赢。
     驱动在时间线里写出 `used_mods:` 一行，先确认顺序真是子模组在前。
   - **结果（series 2 第 3 局）**：时间线 `used_mods: mod "flyer_dive_balance.pack"; | mod "flyer_dive_takeoff.pack"; …`（子模组在前）；
     蝎尾狮 1700、星龙 4425，`BALANCE submod loaded`。所以不是 `used_mods.txt` 里排后者赢；三局都与「片段名排前者赢」相符（片段名没反过来验）。

D4 的飞兽各道（INGAME-1118 第 4、5 项的样子）要等 D4 有了做法再跑。真人联机仍是可选。

### series 4 实机（2026-11-18 午后，八局，已跑完；细节见 `docs/HISTORY.md` INGAME-1118 series 4）

1. **起飞空当**（D11）：查清并修掉。量到的机制：阶段 2、倒计时为 0 的兵模，引擎抬它之前不问规则（0/18）；命中都记在当刻更新之后。
   修法：记挨打时把为 0 的倒计时抬到 1（标记 `FLYPINS5`）。新包实机一局：2 次这样的命中都被抬高并随后被按住，8 次起飞没有提前的，`PROBLEMS: none`。
   「挨打后紧接着被下令」的那种先后在两局里都没自然出现，那一种靠模拟器用例证明。
2. **吹息开关**（D10）：起作用。不装 MCT 为开；替身设置包说关时引擎拒绝接战中的吹息命令；开着时敌人吃到 51 次、1,949 点只在吹息命令之后出现的伤害，关着时 0 次。
   真的 MCT（创意工坊 2927955021）2026-11-19 看过了：设置页、读取顺序、改成关后下一场生效（INGAME-1119）。
3. **冲锋反制**（D4）：原版的做法量到了——架好的兵打冲锋者的那一下 × 2，飞兽俯冲与地面冲锋走同一条路，对大型单体几乎不疼
   （5 秒内掉血：星龙 0、蝎尾狮 0、狮鹫骑士 0.4%、飞马骑士 3.0%）。**D4 本身还没做**；主人已答（D15）：数值主管定（确实掉血、不超标），只算俯冲。重读旧记录（D15-ANALYSIS-1118）：三种较大的体型俯冲穿过枪阵的那几秒一点血没掉；只把倍数调大，对星龙不够、对蝎尾狮过头。

现在的包（主管从工作树建）在 `D:/Projects/.worktrees/wh3-flyer-dive/d10-1118_scratch/supervisor/gapfix_sup/`：发货包 `ship/flyer_dive_takeoff.pack`（14,064,999 字节，sha256 `c7e9c6ba…`）。
D15 做进去之后的包（主管 2026-11-18 夜从工作树重建）：`D:/Projects/.worktrees/wh3-flyer-dive/d15-1118_scratch/supervisor/verify56/flyer_dive_takeoff.pack`（14,090,541 字节，sha256 `7646de33…80b5`）。

### 测完之后

- 第 1 项通过 → D3 进下一版。**已通过（series 3，2026-11-18）**：四种体型都量到了；那一两个时刻的空当记在第 1 项，要查清才发（D11）。
- 第 2 项 → 选定 D4 的做法并实现。做不到「受伤但不被弹回」就回去问主人。
  若量出俯冲的那一下和飞兽平常的地面冲锋走的是同一条引擎路径，先告诉主人再发。**量出来了：是同一条路（series 4 第 3 局）；问过主人，答复是只算俯冲（D15）。**
- 第 3 项 → 把结论写进 README 的加载顺序一段。**已写（2026-11-18）**：中英两段都补了三局的结果（决定结果的不是模组列表里的先后；
  与「片段名排前者赢」相符，反过来的片段名顺序没测）。
- 全部实机核对过（含 D10 的一个包与 MCT 开关、D4、那处空当）→ 合进 `main`，然后**问主人**：推送、上传新版、把页面换成分语言版本。不再建子模组的工坊条目（D10）。

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
| 两个订阅模组的骑乘单位可能骑手分离 | D3-1118 第三节 | `lbm` 的飞马骑士（剑盾）与 `kaylika_auri_lahmians` 的 5 个吸血鬼骑乘单位骑着本模组改指过飞行表的坐骑行，骑手表仍是原版；按 UPDATE-1117 第一节的机制会分离。没实机看过；要修得给别人的单位也改指骑手表（兼容补丁）。**主人 2026-11-18：先不做（D12）** |
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
- `rename-1118`：2026-11-18 主人两次同意后已推到 GitHub（D13 推到 `0a3b2c4`，D16 推到 `76e1228`）；其后的提交只在本机。
- 以后每次推送都要主人同意。

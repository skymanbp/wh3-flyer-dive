# 现状与待办

每批收尾时更新。上次更新：2026-11-21 凌晨（分支 `release-1120`：D39 部队挨打时每个兵模至少等 3 秒、起飞标记 `FLYPINS8`、三个包重建到 `build3/`、龙马对神选长戟实机两局最早 3.3–3.4 秒离地，TAKEOFF-UNIT-1121）；此前 2026-11-20 23:30 前后（分支 `release-1120`：D37 每种体型起飞窗口加一秒、起飞协商标记 `FLYPINS7`、三个包重建到 `build2/`，TAKEOFF-PLUS1-1121）；此前 2026-11-20 深夜（分支 `release-1120`：两个分支合进来、撞枪阵默认值改成 k 2.0 / s\* 0.5 / 代价 10%、三个包建好、全套测试、更新说明与页面改动起草、实机清单，RELEASE-PREP-1120）；此前 2026-11-20 约 22:00（拉回修法 A/B、撞枪阵调轻一档，D23-AB-1120、BRACE-LIGHT-1120）；此前 2026-11-20 约 20:55（拉回去找到区分量，D23-TASK-1120）；此前 2026-11-20 约 20:40（碰撞求解探针两局，PAIR-PROBE-1120）；此前 2026-11-20 约 18:00（拉回去 10 局实机，D23-RUNS-1120）；此前 2026-11-20 约 17:40（读完真正的碰撞求解，D27 那句更正，PAIR-SOLVER-1120）；此前 2026-11-20 约 17:05（探针三局：「推不动」延伸到飞兽不起作用，转去读按质量分推开量的碰撞步骤，BRACE-PROBE-1120）；此前 2026-11-20 傍晚（D30：新版等撞枪阵与拉回去两件一起发；更正 D23 的状态）；此前 2026-11-20 约 16:45（本仓库的会话接手后复核了 BRACE-READ-1120b，读法都成立；主人定 D29：延伸「推不动」规则＋加伤害，不行再减飞兽质量；实机暂停解除；文档提交推送；`docs/HISTORY.md` VERIFY-1120c）；此前 2026-11-20 16:14（D28：主人下令飞行模组的事全部交给本仓库的会话，主模组会话写好交接后不再碰本仓库；第三条离线车道的结果记成 BRACE-READ-1120b，没复核、没告诉主人；没动代码、没开游戏）；此前 2026-11-20 约 15:45（D27：离线读完碰撞代码，架势倍数在碰撞里只影响撞击伤害和「同体型推不动」，D26 的方向撤回；没动代码、没开游戏）；此前 2026-11-20 下午（主人对两条评论的裁定记成 D25：俯冲撞架好枪的反制步兵改由引擎自己的物理来分胜负，并做成 MCT 里可调；实机测试全部暂停，等主人发话；都还没动代码）；此前 2026-11-19 傍晚（新版 17:13 上传创意工坊并核对，默认栏换成英文页，简体中文一栏主人随后在网页上贴好；`rename-1118` 并进 `main` 并推送；D22，`docs/HISTORY.md` UPLOAD-1119）；此前 2026-11-19 下午（欠的四项实机核对做完，十一局都判通过：正式包本身生效、真的 MCT 的设置页与读取顺序、「只算正面」的拒付、多兵模付钱数；D18，`docs/HISTORY.md` INGAME-1119；上传与推送还没问主人）；此前 2026-11-19 上午（主人定了俯冲撞架矛步兵的代价：四种体型都用 3%，D15；分支再推一次，D17；`docs/HISTORY.md` ANSWERS-1119）；此前 2026-11-19 凌晨（D15 按统一标准实机量了三局，都判通过：撞架矛的长矛兵，星龙、蝎尾狮各扣 3.0%，狮鹫骑士整队 1.5%，飞马骑士整队 0.8%；撞剑士零扣血，`docs/HISTORY.md` D15-STD-1119；此前 2026-11-18 夜：D15 的测试用加长记录离线建好，并查到游戏脚本自带的扣血接口，先试它，`docs/HISTORY.md` D15-PROBE-1118；头两局实机跑了：记号、攻击方、满血读数都对，架矛的判定条件选错、一次没扣到血，对照局不成立，`docs/HISTORY.md` D15-INGAME-1118；判定条件已离线改成兵模 +0x68 的第 3 位、加了「带冲锋反制属性」这一关（129 个单位）、对照局换成剑士，D15-BRACE-1118；第二组两局实机验过：撞架矛的长矛兵扣到血（星龙、蝎尾狮各 3%），撞剑士零扣血，D15-INGAME2-1118；规则已离线做进正式包（各体型暂按 3%，只算正面 80 度内的接触，D15-SHIP-1118；新包没进过游戏）；实机测试回到统一标准、只留一个入口，今天各局都是旧场景跑的，D15 的数要按标准重量（TEST-STD-1118）；此前：D15 的离线设计停在「怎么凭空扣这一下」，下一步带加长记录进游戏跑一局，`docs/HISTORY.md` D15-DESIGN-1118；此前：重读旧记录定了 D15 的做法方向：只调大倍数行不通，伤害要落在俯冲接触的那一刻，`docs/HISTORY.md` D15-ANALYSIS-1118；此前同日傍晚：主人答了 D4 的两问（D15），分支再推一次（D16）；此前同日午后：D10-1118 一个包与吹息开关、PROBES-1118 两套探针，都只做到离线；主人的四条新裁定 D10–D13；此前：INGAME-1118 实机一轮、D3-1118、INGAME-1118 series 2 与 series 3）。

## 已发布

| 条目 | 版本 | 包 |
|---|---|---|
| 主模组，创意工坊 3840651516 | 包建在提交 `2b98f08` 上（其后的提交只改文档），2026-11-19 17:13 上传，ManifestID 821697246454453819 | `flyer_dive_takeoff.pack` 14,090,541 字节，sha256 `7646de33402323d8e030dfc6f1a2ba3cce38d2664cb202668b119b4d484480b5` |
| 上一版（已被替换） | 提交 `34dfbf3`，2026-11-17 13:11 上传 | `ld_air_dive.pack` 2,597,312 字节，sha256 `e5208882ce11fc4e76a6e5993ff66e4f902728793e2fe3e3cc41fd585f3419ad` |

- `main` 分支 ＝ 这一版（2026-11-19 并入 `rename-1118`）。联机协商标记：起飞 `FLYPINS5`、俯冲 `FLYDIVE4`（上一版是 `LDFLYPN2`；D9 改名，D3 与起飞空当的修法各换了一次起飞的，D15 做进正式包换了一次俯冲的）。新旧两版联机互不配对，更新说明里写了。
- 页面：默认语言栏是英文页（随上传写入）；简体中文一栏主人 2026-11-19 17:20 左右在网页上贴好了（外部抓取读到两种语言各自的页面，`docs/HISTORY.md` UPLOAD-1119b）。
- 上一版的已知问题（天马类坐骑俯冲时骑手和坐骑分离）在这一版里修掉了。
- 真人联机从来没跑过（主人 2026-11-13 定为可选、不挡发布）。

## 下一版：分支 `release-1120`（还没发布；D30、D33）

工作树 `D:/Projects/.worktrees/wh3-flyer-dive/release-1120/wt`，从 `main` `5c2bd82` 开，合进了 `brace-solver-1120`（`541f398`，D31）与
`regroup-1119`（`51da11a`，D23 的修法）。经过与数字见 `docs/HISTORY.md` RELEASE-PREP-1120。

- 撞枪阵默认值：k 2.0、s\* 0.5、代价 10%（D33；`mod/tools/lib/air_dive_rules.py`，俯冲位点表重生成）。
- 起飞窗口（D37）：小 5.5、中 5.0、大 4.5、超大 4.0 秒（55 / 50 / 45 / 40 tick，体型读不出的取 55），起飞位点表重生成，代码洞字节不变。联机协商标记：起飞 `FLYPINS7`、俯冲 `FLYDIVE5`（`CLAUDE.md` 那一行已改）。经过见 `docs/HISTORY.md` TAKEOFF-PLUS1-1121。D39：部队 3 秒内挨过近战打击，地上的每个兵模倒计时保持满 3 秒，撤离令后至少等 3 秒；联机协商标记起飞改为 `FLYPINS8`（TAKEOFF-UNIT-1121）。
- 现行的包在 `D:/Projects/.worktrees/wh3-flyer-dive/release-1120/build3/`（D39 之后，`FLYPINS8`）：正式包、带移动记录器的 `probe/`、D23 记录包 `pin_record_d39.pack`；`build2/` 是 D37 的（`FLYPINS7`），不要再用；MCT 关的替身仍用 `build/brace_mct_off.pack`（与起飞无关）。`build/` 里其余三个包是 D37 之前的（`FLYPINS6`），不要再用来测或发。sha256 见 HISTORY 的 TAKEOFF-PLUS1-1121 与 RELEASE-PREP-1120。
- 更新说明草稿 `workshop/flyer_dive/changenote.txt`（英文在前、简体中文在后）；页面改动草稿（没改仓库里的页面）`D:/Projects/.worktrees/wh3-flyer-dive/release-1120/page_lines_draft.diff`。两样都要主人逐条点过（D19–D21）。
- **欠实机（主管跑）**：清单 `D:/Projects/.worktrees/wh3-flyer-dive/release-1120/jobs_release_1120.txt`（七局：D23 修法开三局、撞枪阵默认值与 MCT 关各一局、地面骑兵对照、标准三星龙基线）。
- 还欠：D23 的说明与对比图（D23）；D23 的拉回对比：龙马、狮鹫对神选长戟、狮鹫对帝国戟兵四局都没出现拉回（PULLBACK-CLIP-1121），按 D41 不放对比；主人对更新说明、页面改动、推送与上传的同意。

## 这一版的来历：分支 `update-1117`，改名在其上的 `rename-1118`（2026-11-19 已发布，下面是做它时的记录）

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
| 工坊页面每种语言一份 | D2 | 文字定稿方式改了（D20，2026-11-19）：以线上原文为底拆成中英两页，只做主人逐条点过头的改动（`docs/HISTORY.md` PAGE-1119b；此前重写的那一版作废）；主人随后直接改了三处（D21，PAGE-1119c：删掉修 bug 式的两句、吹息一条写「可用MCT调整」、起飞一条用主人的两句）；英文页已随 2026-11-19 的上传写进默认栏（上传工具只写默认栏），简体中文一栏由主人在网页上贴（D22）；更新说明草稿在 `workshop/flyer_dive/changenote.txt`。子模组那一份已删；主页面已写回吹息、质量两段和「设置」一节（MCT 开关；多人战役里以主机的设置为准，D14） |
| 按体型、逐兵模的起飞判定 | D3 | 已实现并离线核对（D3-1118：体型字段 2026-11-18 实测成立，协商标记当时是 `FLYPINS4`，起飞空当修掉后是 `FLYPINS5`）；2026-11-18 实机一局两条判据都过（窗口 `45/40/35/30/45`，`unsized=0 unmatched=0`，held 3763、free 33293，INGAME-1118 series 2 第 1 局）。各体型实际离地快慢已逐兵模量出（series 3），四种都对得上；剩一两个时刻的空当，主人定「查清再发」（D11） |
| 俯冲撞上冲锋反制受双倍伤害 | D4 | 已做进正式包（D15-SHIP-1118）；标准场景下实机量过（D15-STD-1119，2026-11-19：撞架矛的长矛兵星龙 3.0%、蝎尾狮 3.0%、狮鹫骑士整队 1.5%、飞马骑士整队 0.8%，撞剑士 0）；主人 2026-11-19 定：四种体型都用 3%（D15）。正式包本身进过游戏、「只算正面」的拒付也见到了（INGAME-1119，2026-11-19）。此前：2026-11-18 series 4 量到了原版的做法（架好的兵那一下 × 2，俯冲与地面冲锋同一条路）；主人已答（D15：数值主管定，只算俯冲），待实现；做法方向已定（不靠调大倍数，俯冲接触时按兵模满血比例扣一次，D15-ANALYSIS-1118）；离线设计停在怎么扣这一下（D15-DESIGN-1118）；测试用的加长记录已离线建好，先试游戏脚本自带的扣血接口，头两局实机跑了（D15-INGAME-1118）：俯冲记号、攻击方、满血读数都对；架矛的判定条件选错，一次没扣到血；对照局不成立。判定条件已离线改好（D15-BRACE-1118：兵模 +0x68 第 3 位；只对带冲锋反制属性的 129 个单位算；对照局换成撞剑士）。第二组两局实机（D15-INGAME2-1118）：判定对了，游戏自带的扣血调用确实执行，撞长矛兵扣到血、撞剑士零扣血。报告已修，规则已离线做进正式包（D15-SHIP-1118：各体型暂按 3%，只算正面 80 度内的接触，联机协商标记 `FLYDIVE4`）。按统一标准重新量过了（D15-STD-1119）。此前的记录：地面骑兵对照组 5 局都没看到反射（飞兽 12 局也没有）；2026-11-18 带新探针那局：`ACTION UPDATES 0`、`BRACE CHECK NOT REACHED`——长矛兵根本没进入能调用反射检查的动作（INGAME-1118 series 2 第 2 局）。改摆兵那一局已跑（series 3 第 2 局），结果一样；下一步从扣血那一头找。主人定「做完一起传」（D11）。**2026-11-18 午后离线（PROBES-1118）**：装好的游戏数据里带 `charge_reflection` 的陆军单位是 129 个（D4 写的 136 对不上），规则值 `charge_reflect_damage_multiplier` 2、门槛 0.7；引擎里只有伤害计算函数读这两个值，它把架好的反制兵打冲锋者的伤害乘 2，另有一条撞击反射按伤害类别 0 扣血。也就是原版本来就会伤到冲锋者，D4 多半不用另造伤害来源。新探针挂在乘 2 的那两处，离线核对过，没进过游戏 |
| 落地后第二次撞穿 | D5（评估，非裁定） | 不改代码 |
| 与主模组仓库断开（代码侧） | D6 | 已做完并核对：测试 84 项全过，两个包的字节没变，运行时不读主模组仓库（`docs/HISTORY.md` HOME-1117 第二节） |

2026-11-19 发布后 `rename-1118` 已并进 `main`：断开用的代码改动、测试、数据快照都随这一版进了 `main`（合并时内容取本分支的，核对见 `docs/HISTORY.md` UPLOAD-1119）。

### 实机测试的统一标准（2026-11-18；来由见 `docs/HISTORY.md` TEST-STD-1118）

只有一个入口：`tools/pipelines/flyer_run.py`（单局 `one`，成批 `list`），驱动 `air_dive_autotest.py` 只由它调用。机器忙（主人的游戏、别的游戏、重活锁、pytest / 建包）就拒绝，不等待、不碰正在运行的游戏；跑的时候持有重活锁；被杀掉的一局下次启动先复原。输出放在 `D:/Projects/.worktrees/wh3-flyer-dive/runs/`，不进仓库。标准场景：平坦地图 mp_crossroads_flat、道间距 175 米、同时冲锋、无集结区、目标关散兵与自由开火并开近战、1 倍速、相距 250 米。偏离标准要明说，状态文件和 run.json 会写出来（2026-11-19 起，带 `--cmd` 额外控制项的局也算偏离）。每种记录只有一个报告脚本（`reflect_probe_report.py` 等）。每种飞兽重复几次，还没定。

**这三局 2026-11-19 凌晨跑完了，都判通过**（D15 按标准重新量；结果在 `docs/HISTORY.md` D15-STD-1119，输出在 `D:/Projects/.worktrees/wh3-flyer-dive/runs/` 下三个同名目录）。**当时欠的四项 2026-11-19 下午都做完了**（十一局都判通过，`docs/HISTORY.md` INGAME-1119）：① 正式包本身进了游戏，撞长矛兵扣血、撞剑士不扣；② 真的 MCT：设置页、读取顺序、改成关后下一场生效都看到了；③「只算正面」的拒付见到了（长矛兵背对时 61 次接触全部不付）；④ 多兵模的飞兽各量了 6 次俯冲（狮鹫骑士每次 4 个里 2 个付，飞马骑士 24 个里 3 到 6 个付）。**实机核对到此没有欠的；下一步是问主人：上传新版、换页面、推送、合进 `main`。**（2026-11-19 傍晚主人都答了，已做：D22，UPLOAD-1119。）当时的命令留作记录（在 `rename-1118/wt/mod` 下跑）。`P` ＝ `D:/Projects/.worktrees/wh3-flyer-dive/d15-1118_scratch/lane/probe5/probe_d15.pack`：

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

### REGROUP-1119（D23 多兵模起飞后被拉回）：修法已离线做进正式包，欠实机 A/B（REGROUP-FIX-1120）

- 2026-11-20 晚：修法记在 `docs/DECISIONS.md` D23 末条（主管的技术路线）：在两个冲锋任务处理函数里，兵模在空中、单位命令队列为空、同单位有被 D3 按住的地上兵模时，跳过引擎给它的冲锋命令；玩家的命令（队列非空）、地上的兵模、没有被按住同伴的单位都照旧。起飞协商标记 `FLYPINS6`。模拟器 1,856 项、55 个坏版本全抓到、解码与特征码都过；全套测试只剩已知的 `test_no_old_names`。
- 包在 `D:/Projects/.worktrees/wh3-flyer-dive/regroup-1119/scratch/packs/fix/`：正式包 sha256 `3bd3c288…e95d`，测试包 `pin_record_fix1.pack` `b907e259…1c28`。
- 欠的实机 A/B：`owed_runs.txt` 末尾四局 `rg_fix_on1 rg_fix_off1 rg_fix_on2 rg_fix_off2`（同一对包，关＝记录器 `regroup 0`；判据在 HISTORY 同名一节）。
- 怪步拦截 4 局：只有长戟兵那局（`rg_o_m2b`）拉回 3 个；巨魔、铁腹的 3 局严格口径都是 0。
- 并进 `main` 时 `CLAUDE.md` 里的「现为起飞 `FLYPINS5`」要改成 `FLYPIN10`（`release-1120` 上已改；D23 时是 `FLYPINS6`，D37 `FLYPINS7`，D39 `FLYPINS8`，D44 `FLYPINS9`，补发挪到出口后 `FLYPIN10`）。

以下是 2026-11-19 的记录：


- 分支 `regroup-1119`（未推送）。A、B 已量并有反向对照，C 只有初步答案，D 没做（没有区分「引擎自动协助交战」与「玩家明确攻击令」的判别量），E、F 没做。数字、规则、地址与证据见 `docs/HISTORY.md` REGROUP-1119。
- 主人 2026-11-19 22:08 令暂停实机测试；欠的局与精确命令行在 `D:/Projects/.worktrees/wh3-flyer-dive/regroup-1119/scratch/owed_runs.txt`（十四局，按这个顺序：先是关防御模式的重做 `gd_p_*`（飞马 / 飞兽 / 鹰身女妖，40 m）、`gd_f_*`（同，150 m）、对照 `gd_c_*`（`guard_on=1`），再是 `rg_o_m2`、怪步拦截 `rg_t_*`、`rg_i_m`，最后 `rg_s_*` 四局带 `rt_stub` 洞）。主人 22:12 的纠正（被攻击一方不能开防御模式）已记入 D23；挂具现在每局显式关防御模式并记录状态（`docs/HISTORY.md` REGROUP-1119 末节）。主人说可以测了再从 `regroup-1119/wt/mod` 用 `flyer_run.py list` 跑，一次一局。

### 测完之后

- 第 1 项通过 → D3 进下一版。**已通过（series 3，2026-11-18）**：四种体型都量到了；那一两个时刻的空当记在第 1 项，要查清才发（D11）。
- 第 2 项 → 选定 D4 的做法并实现。做不到「受伤但不被弹回」就回去问主人。
  若量出俯冲的那一下和飞兽平常的地面冲锋走的是同一条引擎路径，先告诉主人再发。**量出来了：是同一条路（series 4 第 3 局）；问过主人，答复是只算俯冲（D15）。**
- 第 3 项 → 把结论写进 README 的加载顺序一段。**已写（2026-11-18）**：中英两段都补了三局的结果（决定结果的不是模组列表里的先后；
  与「片段名排前者赢」相符，反过来的片段名顺序没测）。
- 全部实机核对过（含 D10 的一个包与 MCT 开关、D4、那处空当）→ 合进 `main`，然后**问主人**：推送、上传新版、把页面换成分语言版本。不再建子模组的工坊条目（D10）。**2026-11-19 都做了（D22）；简体中文一栏主人当晚也贴好了。**

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
| 俯冲撞架好枪的反制步兵：加大抵御冲锋的质量效果、加大冲锋反制的伤害、做成 MCT 可调 | D25（主人 2026-11-20；两条工坊评论） | 离线调研在做（只读，2026-11-20 开始）；方案没定、没建、没测。代价大小主人选了 10%。实机测量等主人解除暂停 |
| 上一行的两条限定 | D26（主人 2026-11-20 约 14:55） | 只针对飞行部队，地面部队冲锋不变；「冲锋抗性」是游戏里单独的属性（`scalar_bracing`），原版三个技能会乘它，我方记录此前没看过它。下一步：离线读碰撞代码，找到抵御冲锋的数值在哪里被用到、能不能只对俯冲的飞兽放大 |
| D26 那条路走不通，换路 | D27（主管 2026-11-20 约 15:45；`docs/HISTORY.md` BRACE-READ-1120） | 离线读完碰撞代码：架势倍数（含冲锋抗性）在碰撞里只进了撞击伤害的公式，外加一条只对同体型或更小的东西生效的「推不动」；放大它挡不住飞兽，D26 的方向撤回。下一步离线：读「大体型撞进人堆后怎么减速」那一段；扣血 3% 提到 10% 和冲锋反制只对飞兽加系数两件可以先设计。要进游戏的（暂停中）：逐帧记录飞兽速度的被动探针 |
| D27 第 1 步的结果：没找到靠质量挡住大个子的代码 | `docs/HISTORY.md` BRACE-READ-1120b（车道 2026-11-20 16:02；主管没复核） | 引擎让飞兽停下靠的是换命令那一刹，不是碰撞；架势倍数只进伤害。要「挡住」只剩两条路（延伸「推不动」规则，或在那一刹上加规则），都是玩家看得到的行为，要主人定。**2026-11-20 约 16:30 本仓库的会话复核过、告诉了主人（VERIFY-1120c、D29） |
| 交接 | D28（主人 2026-11-20 约 16:05） | 飞行模组的一切更新与开发只在本仓库的会话里做。交接正文 `docs/research/2026-11-20-handover.md` |
| 多兵模飞行部队：已起飞的兵模被留在地面的兵模拉回去 | D23（主人 2026-11-19 晚）；D30 与撞枪阵一起发 | 分支 `regroup-1119` 三笔提交（11-19 晚）：逐兵模记录、六个追踪代码洞、探针定到一半的根因（空中待命的兵模被派给地面的敌人当目标，引擎叫它降落，于是飞回去）；发这个命令的上一层还没找到。不在 `main`。此前写的「没开始」是错的（D30）。2026-11-20 又跑 10 局（D23-RUNS-1120）：链路 12/12 坐实，拉回只发生在「一半在天上、一半被按住」的单位；还没找到能区分引擎自动回援与玩家攻击令的量，不出补丁；20:35–20:48 又跑 5 局（D23-TASK-1120）：找到区分量——被拉回时单位命令队列为空，玩家下令时队列里有攻击令（18 对 26，不交叉）。修法已建（分支 `regroup-1119` `51da11a`，起飞协商标记 `FLYPINS6`）；实机 A/B（D23-AB-1120）：关修法拉回 9、3 个，开修法那一局 0 个、拦 64 次、玩家命令照常；还要再跑几局「开」坐实。怪步拦截 4 局没形成一半按住的局面，0 对 0 |
| 实机测试 | 主人 2026-11-20 约 14:05 暂停；约 16:40 解除（D29：「解除，直接跑。」） | 已解除。第一局是只记录的探针（BRACE-READ-1120b 的未知项）；机器检查照旧 |
| 俯冲撞架好的枪阵怎么停 | D29（主人 2026-11-20 约 16:40） | 复核过 BRACE-READ-1120b（VERIFY-1120c）。做法：把引擎的「推不动」规则延伸到俯冲的飞兽，加 10% 扣血与只对飞兽的冲锋反制系数（MCT 可调、带总开关）；实测挡不住再减飞兽质量。2026-11-20 16:49–16:57 只记录的探针三局（BRACE-PROBE-1120）：被撞的兵模在飞兽撞上来时一次都没带「推不动」标志，延伸这条规则一次也改变不了。离线读完真正的碰撞求解 `0x14317768c`（PAIR-SOLVER-1120）：架势倍数本来就乘进了架好的兵的质量，挡不住大飞兽的是体型档折扣（档差 3 只吃 0.1）。做法：只对俯冲的飞兽，在那里加大架好的兵的有效质量并抬高飞兽的折扣，MCT 可调。2026-11-20 20:30 探针两局（PAIR-PROBE-1120）：这一步的速度修正每次都作用到了落地的飞兽身上，公式里的数与读出来的一致。**2026-11-20 晚做完离线（D31，BRACE-SOLVER-1120，分支 `brace-solver-1120`，不在 `main`）**：代码洞 `dv_brace` 在 `0x1431781e9`，只在引擎算进了架势、另一方是落地俯冲的飞兽时把架好的兵的质量再乘 k（默认 3.4）、把飞兽的折扣抬到至少 s\*（默认 0.8）；代价 3% → 10%；MCT 四项（总开关、k、s\*、代价 0–25%），多人战役按主机，战役外多人用默认值；俯冲协商标记 `FLYDIVE5`。包在 `D:/Projects/.worktrees/wh3-flyer-dive/brace-solver-1120/build/`（sha256 `64730585…5b23`）。**欠实机**：四种体型撞架好的长矛兵，关 / 开 / 中性各一局，地面骑兵关 / 开对照（清单 `build/jobs_brace_solver.txt`）；数报给主人再定默认值。只对飞兽的冲锋反制系数没做 |

## 东西在哪

| 东西 | 位置 |
|---|---|
| 下一版的研究、探针脚本、建出来的包 | `D:/Projects/.worktrees/wh3-flyer-dive/update-1117/`（`design.md`、`static_B_C.md`、`scripts/`、`impl_scripts/`、`build/`） |
| 2026-11-17 这一晚的对照包、截图、探针 | `D:/Projects/.worktrees/wh3-flyer-dive/session_1117/` |
| 从主模组草稿区搬来的全部旧数据（24.4 GiB） | `D:/Projects/.worktrees/wh3-flyer-dive/from_lore_disaster/`，清单见 `docs/HISTORY.md` 的 DATA-MOVE-1117 |
| 上传用的文件 | `from_lore_disaster/flyer-publish_scratch/`，用法见 `docs/WORKSHOP.md` |
| 仓库里的两批旧证据 | `mod/tools/evidence/` |
| 2026-11-20 三条离线车道的脚本、反汇编、数据文件 | `D:/Projects/.worktrees/wh3-flyer-dive/brace-physics-1120/`、`brace-collision-1120/`、`brace-response-1120/`（各有 `REPORT.md`；报告的副本在 `docs/research/`） |
| 2026-11-20 主管自己的探针与写文档的脚本 | `D:/Projects/.worktrees/wh3-flyer-dive/d25_docs/`（`bracing_probe.py` 读 `scalar_bracing`；`inv_brace_readers.py` 是架势倍数读者的普查；`apply_d25.py` 到 `apply_handover.py`） |

## 推送状态

- `main` 已推到 GitHub（2026-11-17 夜，主人同意，`docs/DECISIONS.md` D8）：内容是已发布的那一版代码，加上搬进来的
  规矩与记录。
- `rider-seat-1117`（`c658e17`）、`update-1117`（`e0018f5`、`d635f71` 及其后的搬家提交）只在本机，等实机核对完再问。
- `rename-1118`：2026-11-18 主人两次同意后已推到 GitHub（D13 推到 `0a3b2c4`，D16 推到 `76e1228`）；2026-11-19 上午再推一次（D17）；2026-11-19 傍晚主人同意后与 `main` 一起推（D22）。
- 2026-11-19 17:19：`main` 与 `rename-1118` 都在 `5a98bb4`，已推到 GitHub；其后的记录提交留在本机，下次推送带上。
- 2026-11-20 约 16:45：`main` 上 `03650fc`（D25）、`d0272bd`（D26）、`3196e6c`（D27）、`e5f2ab6`（D28）与记 D29 的一笔都只有文档，经主人同意（D29「现在推」）推到 GitHub。
- 以后每次推送都要主人同意。

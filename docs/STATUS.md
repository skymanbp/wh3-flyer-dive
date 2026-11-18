# 现状与待办

每批收尾时更新。上次更新：2026-11-17 夜（搬家当晚）。

## 已发布

| 条目 | 版本 | 包 |
|---|---|---|
| 主模组，创意工坊 3840651516 | 提交 `34dfbf3`，2026-11-17 13:11 上传 | `ld_air_dive.pack` 2,597,312 字节，sha256 `e5208882ce11fc4e76a6e5993ff66e4f902728793e2fe3e3cc41fd585f3419ad` |

- `main` 分支的代码 ＝ 这一版。联机协商标记 `LDFLYPN2`。
- 这一版有一个已知问题：天马类坐骑（飞马、地狱战马、玉龙马）俯冲时骑手和坐骑分离。修复在下一版里，还没发。
- 真人联机从来没跑过（主人 2026-11-13 定为可选、不挡发布）。

## 下一版：分支 `update-1117`（没做实机核对，没发布）

工作树：`D:/Projects/.worktrees/wh3-flyer-dive/update-1117/wt`。内容与数字见 `docs/HISTORY.md` 的 UPDATE-1117。

| 项 | 裁定 | 状态 |
|---|---|---|
| 骑手俯冲时坐稳 | 玩家报告的缺陷 | 已实现，离线测试过；欠实机重拍 |
| 平衡子模组 `flyer_dive_balance.pack` | D1 | 已实现，离线测试过；欠实机换序试验 |
| 工坊页面每种语言一份 | D2 | 文字已写（`workshop/`），有三处占位 |
| 按体型、逐兵模的起飞判定 | D3 | 只做了准备：数字在规则里，体型字段的探针备好没跑 |
| 俯冲撞上冲锋反制受双倍伤害 | D4 | 只做了准备：倍数在规则里，记录用的探针备好没跑 |
| 落地后第二次撞穿 | D5（评估，非裁定） | 不改代码 |
| 与主模组仓库断开（代码侧） | D6 | 已做完并核对：测试 84 项全过，两个包的字节没变，运行时不读主模组仓库（`docs/HISTORY.md` HOME-1117 第二节） |

`main` 上只有文档和规矩（`CLAUDE.md`、`docs/`、`.claude/`）是新的，代码仍是已发布的那一版；
断开用的代码改动在本分支，随下一版一起进 `main`。

### 欠的实机测试（约 80 分钟；游戏空着才能跑，一次一件）

命令都在工作树的 `mod/` 目录下跑。探针包先从
`D:/Projects/.worktrees/wh3-flyer-dive/update-1117/build/probes/` 拷进游戏的 `data/`（`probe_size.pack`、`probe_impact.pack`），
跑完移走。建探针包要 keystone 与 unicorn，系统 Python 没装，用
`D:/Projects/.worktrees/wh3-flyer-dive/from_lore_disaster/air-dive-takeoff-w1_scratch/venv/Scripts/python.exe`。

1. **骑手修复重拍四局**（约 10 分钟）：`D:/Projects/.worktrees/wh3-flyer-dive/session_1117/series_locked.sh`，
   测试包 `session_1117/probe2/ld_air_dive.pack`（脚本要的环境变量写在它开头）。
   合并之后的包和这个测试包不是同一次建的；正式核对用合并后重建的包再拍一遍。
2. **体型字段**（约 4 分钟）：
   `python -P tools/pipelines/air_dive_autotest.py --test-pack probe_size.pack --memreader --flyers wh2_main_def_inf_harpies,wh_main_brt_cav_pegasus_knights,wh2_dlc10_def_mon_feral_manticore_0,wh2_main_hef_mon_star_dragon`
   然后 `python -P tools/pipelines/flyer_size_probe_report.py "<游戏目录>/flyer_size_probe.txt"`。
   报告写 `HOLDS` 即字段成立，`REFUTED` 即不成立（改走备选：开战时按单位键查体型）。
3. **冲锋反制对照组**（三局，各约 4 分钟）：`--test-pack probe_impact.pack --memreader --target wh_main_emp_inf_spearmen_1 --flyers`
   四路都填 `wh_main_brt_cav_knights_of_the_realm`。自动判定会写 FAIL（骑兵不会「落地」），看报告：
   `python -P tools/pipelines/reflect_probe_report.py "<游戏目录>/reflect_probe.txt"` 必须出现 `CONTROL SEEN`。
4. **飞兽三种目标各三局**：`--flyers wh2_main_hef_mon_star_dragon,wh2_dlc10_def_mon_feral_manticore_0,wh2_dlc15_hef_inf_mistwalkers_griffon_knights_0,wh_main_brt_cav_pegasus_knights`，
   `--target` 分别为 `wh_main_emp_inf_spearmen_1`、`wh_main_emp_inf_halberdiers`、`wh_main_emp_inf_swordsmen`。
5. **侧面接近三局**：同第 4 项对长矛兵，加 `--cmd target_turn_1=90,target_turn_2=90,target_turn_3=90,target_turn_4=90`。
6. **子模组换序**：两个包都开，量战斗里的质量；再把子模组改名排到主包之后，再量。

### 测完之后

- 第 2 项成立 → 实现 D3（新的起飞代码洞，协商标记换成 `LDFLYPN3`，删掉旧的两个常数和 README 里旧规则的描述）。
- 第 3–5 项 → 选定 D4 的做法并实现。做不到「受伤但不被弹回」就回去问主人。
  若量出俯冲的那一下和飞兽平常的地面冲锋走的是同一条引擎路径，先告诉主人再发。
- 全部实机核对过 → 合进 `main`，然后**问主人**：推送、上传新版、建子模组的工坊条目、把页面换成分语言版本。

## 其他待办

| 事 | 来由 | 状态 |
|---|---|---|
| 落地冲锋后滑行停不住，查根因 | 主人 2026-11-14 提出，疑转身动作被关 | 没开始。四组对照：现状 / 只恢复转身动作 / 只恢复原版刹车 / 两样都恢复；不得退回「15 米内提前停下」 |
| 俯冲时兵模忽上忽下 | 主人 2026-11-14 在皇家马鹫测试里看到 | 引擎侧已修（720 次里 78 次降到 1 次），等主人在游戏里看一眼 |
| 评论区两条回复 | 2026-11-17 | 起草后交主人自己发：①「是不是所有飞兽都免疫架矛」——不是，大型单体不被早停，飞马骑士 6 局里 5 次被拦停；②骑手分离——下一版修 |
| 主模组适配包 | D6 | 等主模组改完名。输入是 `mod/tools/data/` 里的快照；包里现在不含主模组的飞兽 |
| 已发布名字里的 `ld_` | 主模组那边在全面改名 | 没动。改名会打乱订阅者的加载顺序和联机配对，要主人下令 |
| 随包脚本里的「Lore Disasters」字样 | 断开时留下 | 两个战役入口脚本交给联机协商的标题（`title = "Lore Disasters flyer …"`，联机时可能显示给玩家）和一处注释。改它会改变包的字节，下一版重建包时一起改 |
| 开发用环境变量名 `LD_*` | 断开时留下 | 五个（`LD_WH3_DATA`、`LD_WH3_ROOT`、`LD_MEMREADER_DIR`、`LD_VANILLA_DB_PACK`、`LD_GAME_EXE`）。不进包，不影响玩家；要改就五个一起改 |
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
- 以后每次推送都要主人同意。

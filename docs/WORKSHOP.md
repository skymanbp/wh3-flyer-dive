# 创意工坊：条目、上传、核对

每一次上传、改页面、建新条目，都要模组主人在对话里明确同意，同意只管那一次（`docs/DECISIONS.md` D6）。
上传前把要发的东西给主人看：包的大小与校验值、更新说明、页面文字的改动。

## 条目

| 条目 | 工坊编号 | 包 | 状态 |
|---|---|---|---|
| 飞兽俯冲冲锋重做（工坊标题保持原名，D20；包内设置页叫「飞兽俯冲与近战起飞」） | 3840651516 | `flyer_dive_takeoff.pack`（2026-11-19 起；此前的版本叫 `ld_air_dive.pack`，D9） | 公开；现行版本见 `docs/STATUS.md` |

- 游戏的应用编号：1142710。
- 前置条目：memreader Plus，3811098873（页面上声明）。只有这一个条目：平衡子模组已撤回（D10）。
- 标签：`mod` 和 `battle`（主人 2026-11-17 定）。没有 `mod` 标签的条目，订阅后在官方启动器里勾不上。
- 鸣谢写法：memreader Plus 的作者写作 Druwski（GitHub 名 PKozdra）；memreader 写 Cpecific。

## 页面文字：每种语言一份（D2）

- 文字放在仓库里：`workshop/<条目>/<语言>/title.txt` 与 `description.txt`，哪份进哪个语言槽见 `workshop/README.md`。
- 英文版里只有英文，简体中文版里只有中文。说明用 Steam 的 BBCode（`[h1]`、`[list]`、`[*]`、`[b]`、`[url=…]`），不是 Markdown。
- 中文用游戏客户端自己的说法，写之前查 `local_cn.pack`。
- 2026-11-19 起线上的默认语言栏是英文页。上传工具（vdf 里的 `title`、`description`）只写默认栏；别的语言栏在网页上
  「编辑标题和描述」里切到那种语言后粘贴，由主人做（D22）。先传文件再贴的话，贴好之前那种语言的玩家看到的是默认栏。
- 还没实现的规则不写成已有。页面只写模组为玩家做了什么，话要短；修 bug 式的句子、规则怎么算的细节不写（D21）。

## 上传步骤（用 steamcmd）

官方启动器的上传在这台机器上是坏的（2026-11-15：点了 12 次，每次都是「建出条目 → 传 689 字节清单 →
`Timeout uploading manifest` → 启动器删掉空条目」；直接调游戏自带的 Steam 接口同样失败）。改用 Valve 的
steamcmd 一次成功，此后都用它。

1. **建包**：在要发布的那个提交上建，两个包出自同一次建包。记下每个包的字节数与 sha256。
   建包自带两项检查（代码洞位点表、游戏主程序的特征码），不过就不发。
2. **备份**：把线上现行的包和上一次的 vdf 存一份（按日期建目录）。
3. **暂存**：把要发的包放进一个只装这一个条目内容的目录（content 目录）。
4. **写 vdf**：`appid` 1142710、`publishedfileid`、`contentfolder`（暂存目录的绝对路径）、`changenote`（更新说明）。
   只想换文件时，`title`、`description`、`visibility`、`previewfile` 照抄线上现值或不写，免得把页面改掉。
5. **上传**：`steamcmd +login <账号> +workshop_build_item <vdf 的绝对路径> +quit`。
   登录由主人自己做（账号、密码、令牌验证码都不经助手的手）。缓存的登录可能被拒（`Access Denied`，
   开了 Steam 令牌之后旧缓存会失效），那就请主人重新登录一次。成功的标志是
   `Uploaded new content ( ManifestID … )`。
6. **核对**（公开接口 `ISteamRemoteStorage/GetPublishedFileDetails`，不用登录）：
   - `time_updated` 变了；
   - `file_size` ＝ 包的字节数 ＋ 预览图的字节数；
   - `hcontent_file` 与上传时打印的 ManifestID 一致；
   - `visibility` 为 0（公开）；
   - **`tags` 仍有 `mod` 与 `battle`**——steamcmd 不写标签，有一次上传后标签是空的，要补。
   - **键值标签 `PACK_NAME`（包名，小写）与 `game_version`（`589824`）都在**——官方启动器只列带这两个的条目
     （LAUNCHER-1121）；steamcmd 不写，新条目一定要补。用 `ugc.py meta` 读、`ugc.py kv` 写。
   - 需要客户端接口的事（标签、键值标签、前置条目）要在 steamcmd 登录之前做，或等主人的客户端重新上线后做：
     steamcmd 用同一账号登录会把桌面客户端顶下线（`Session Replaced`）。
7. **补标签**（只在第 6 步发现标签不对时）：经游戏自带的 `steam_api64.dll` 调 `ISteamUGC::SetItemTags`，只改标签，
   不动文件和说明。回调可能迟迟不回，以第 6 步的公开接口查到为准。
8. **本地**：把新包放进游戏的 `data/` 和桌面，两份的 sha256 要与第 1 步一致。
   （2026-11-19 那次只放了桌面：主人订阅着条目，Steam 会把新包送到工坊目录，`data/` 里再放一份会重名；要不要放由主人说。）
9. **记账**：在 `docs/HISTORY.md` 末尾加一节（发了什么、包的字节数与 sha256、ManifestID、核对结果、
   没验证的事），更新 `docs/STATUS.md` 的「已发布」一行；`main` 分支指到发布的那个提交。

上传要用的东西在 `D:/Projects/.worktrees/wh3-flyer-dive/tools/`（`steamcmd/`、最近一次的 vdf、`rollback/` 里的线上包、`workshop_media/` 里的封面与动图），清单见 `docs/STATUS.md`「东西在哪」。vdf 里的 `contentfolder` 指向那一次的暂存目录，再用之前要改。

## 页面上的图

- 展示图每张上限 2 MB（8 MB 的对比动图被拒过）。
- 展示图里的图一删除，它的地址立即失效。说明正文里要引用的图另存为主人 Steam 资料里的私密艺术作品，
  再在说明里引用那个地址。
- 现在的展示图：封面一张、三段只开本模组的动图（飞马骑士、蝎尾狮、狮鹫骑士冲帝国剑士；主人选定）。

## 只有主人能做的事

- 同意新版的 Steam 用户协议；开 Steam 令牌（没开时条目设不成公开）；登录 steamcmd。
- 在评论区回复。助手只起草，附上依据（实测数字、截图），由主人自己发。

## 改了包名要说清的事（D9）

第一次发 `flyer_dive_takeoff.pack` 的那次上传：

- 暂存目录里只放新包，不放 `ld_air_dive.pack`（否则订阅者同时拿到两个版本）。
- 更新说明写明：包改了名，订阅者可能要在启动器里重新勾一次；手动拷进 `data` 的旧 `ld_air_dive.pack` 要删掉；
  新旧版本联机不配对。
- 第 8 步：游戏 `data/` 与桌面上的旧 `ld_air_dive.pack` 一并删掉，只留新包。

## 改了规则之后

- 改了会影响战斗模拟的规则，联机协商标记要换新（代码里的事，不写进更新说明）。
- 没在真人联机里跑过的东西，照实写「未验证」，不写成支持。
- 常识不写（D55）：新旧版本联机互不配对、联机按主机的设置、要更新才能联机之类，更新说明、页面、回复里都不一一说明。

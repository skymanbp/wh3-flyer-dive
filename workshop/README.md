# Workshop page text

Steam lets one Workshop item carry a separate title and description per language
(user ruling 2026-11-17, `docs/DECISIONS.md` D2). Each file below is pasted into
one language slot of one item. Descriptions are Steam BBCode, not Markdown.

| item | Workshop id | language slot | title | description |
|---|---|---|---|---|
| Flyer Dive & Take-off (`flyer_dive_takeoff.pack`) | 3840651516 | English | `flyer_dive/en/title.txt` | `flyer_dive/en/description.txt` |
| Flyer Dive & Take-off (`flyer_dive_takeoff.pack`) | 3840651516 | Simplified Chinese | `flyer_dive/zh/title.txt` | `flyer_dive/zh/description.txt` |
| Balance submod (`flyer_dive_balance.pack`) | not published yet | English | `flyer_dive_balance/en/title.txt` | `flyer_dive_balance/en/description.txt` |
| Balance submod (`flyer_dive_balance.pack`) | not published yet | Simplified Chinese | `flyer_dive_balance/zh/title.txt` | `flyer_dive_balance/zh/description.txt` |

Before publishing:

* Replace `SUBMOD_ID_PLACEHOLDER` in both `flyer_dive/*/description.txt` with the
  submod's Workshop id once it exists.
* The submod declares Workshop item 3840651516 as a required item, with the same
  tags as the main item.
* The `PLACEHOLDER` line in `flyer_dive/*/description.txt` (damage from braced
  spears) stays until that rule ships. The take-off line describes the body-size rule
  (D3), implemented on the `rename-1118` branch and not yet checked in game.
* Chinese game terms are the game client's own words, read from
  `local_cn.pack` (for example 吹息, 陷入近战, 已落地, 冲锋反制, 阵列齐整, 昊天狮).

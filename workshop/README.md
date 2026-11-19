# Workshop page text

Steam lets one Workshop item carry a separate title and description per language
(user ruling 2026-11-17, `docs/DECISIONS.md` D2). Each file below is pasted into
one language slot of one item. Descriptions are Steam BBCode, not Markdown.

| item | Workshop id | language slot | title | description |
|---|---|---|---|---|
| Flying Charge Overhaul (`flyer_dive_takeoff.pack`) | 3840651516 | English | `flyer_dive/en/title.txt` | `flyer_dive/en/description.txt` |
| Flying Charge Overhaul (`flyer_dive_takeoff.pack`) | 3840651516 | Simplified Chinese | `flyer_dive/zh/title.txt` | `flyer_dive/zh/description.txt` |

Before publishing:

* There is no second item: the balance submod of 2026-11-17 was withdrawn
  (`docs/DECISIONS.md` D10). Breath while engaged and the mass cut are back in the
  one pack; breath while engaged is a Mod Configuration Tool setting, default on.
* The texts are the live page of 2026-11-17 split by language, with the changes the
  owner passed one by one on 2026-11-19 (`docs/DECISIONS.md` D20, `docs/HISTORY.md`
  PAGE-1119b) and three edits of his own (D21, PAGE-1119c). The titles keep the old name.
  The page says what the mod does, in few words: no sentences about fixes or about how a
  rule is computed (D21). Change a sentence only with the owner.
* `flyer_dive/changenote.txt` is the update note of the next upload. Steam has one
  slot for it, so it carries English first and Simplified Chinese below.
* Chinese game terms are the game client's own words, read from
  `local_cn.pack` (for example 吹息, 陷入近战, 已落地, 冲锋反制, 阵列齐整, 昊天狮).

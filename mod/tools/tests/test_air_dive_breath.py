"""Breath abilities castable in melee: the rule and its table. [AIR-DIVE-W15 2026-11-11]

User 2026-11-11: "允许所有喷吐类技能在接战时释放". The lever is CA's
special_ability_to_invalid_usage_flags (air_dive_rules docstring); these
tests pin the breath set's three data criteria, the miss detector, the row
strip for the vanilla table and the donor TSVs, and on the installed game
that the replacement table drops exactly the breath rows and nothing else.
/ 喷吐技能接战可放：判定规则、漏判检测、原版整表与捐赠方表的删行。
"""
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import rolepath  # noqa: F401 -- because it puts the role directories on sys.path

import air_dive_rules as rules
import db_writer
import installed_db_table

UA = [
    {"key": "cone", "type": "wh_type_breath", "icon_name": "i_cone"},
    {"key": "dragon", "type": "wh_type_magic_missiles", "icon_name": "i_dragon"},
    {"key": "named", "type": "wh_type_vortex", "icon_name": "i_named"},
    {"key": "bolt", "type": "wh_type_magic_missiles", "icon_name": "i_bolt"},
    {"key": "aura", "type": "wh_type_augment", "icon_name": "i_dragon"},
]
USA = [
    {"key": "cone", "activated_projectile": None, "vortex": "v_cone"},
    {"key": "dragon", "activated_projectile": "p_fire", "vortex": None},
    {"key": "named", "activated_projectile": None, "vortex": "v_head"},
    {"key": "bolt", "activated_projectile": "p_bolt", "vortex": None},
    {"key": "aura", "activated_projectile": None, "vortex": None},
]
PROJ = [{"key": "p_fire", "projectile_display": "x_sun_dragon_breath"},
        {"key": "p_bolt", "projectile_display": "x_crossbow_bolt"}]
NAMES = {"named": "Breath of the Hydra", "bolt": "Bolt Storm",
         "aura": "Breath of Life"}


class BreathSet(unittest.TestCase):
    def test_three_criteria(self):
        got = rules.breath_abilities(UA, USA, PROJ, NAMES)
        self.assertEqual(sorted(got), ["cone", "dragon", "named"])
        self.assertTrue(got["cone"].startswith("type"))
        self.assertTrue(got["dragon"].startswith("projectile"))
        self.assertTrue(got["named"].startswith("on-screen name"))

    def test_a_name_without_an_emission_is_not_a_breath(self):
        # "Breath of Life" is a passive regeneration: nothing to cast in melee
        self.assertNotIn("aura", rules.breath_abilities(UA, USA, PROJ, NAMES))

    def test_unknown_projectile_is_refused(self):
        with self.assertRaises(RuntimeError):
            rules.breath_abilities(UA, USA, PROJ[1:], NAMES)

    def test_breath_only_icon_flags_a_miss(self):
        breath = rules.breath_abilities(UA, USA, PROJ, NAMES)
        # i_dragon is also the aura's icon: it marks nothing
        self.assertEqual(rules.breath_icons(UA, breath), {"i_cone", "i_named"})
        donor_ua = [{"key": "copy", "type": "wh_type_magic_missiles", "icon_name": "i_cone"}]
        donor_usa = [{"key": "copy", "activated_projectile": "p_bolt", "vortex": None}]
        misses = rules.breath_misses(breath, donor_ua, donor_usa,
                                     rules.breath_icons(UA, breath))
        self.assertEqual(list(misses), ["copy"])


class RowStrip(unittest.TestCase):
    ROWS = [{"invalid_usage_flag": "engaged_in_melee", "special_ability": "dragon"},
            {"invalid_usage_flag": "grounded", "special_ability": "dragon"},
            {"invalid_usage_flag": "climbing", "special_ability": "dragon"},
            {"invalid_usage_flag": "engaged_in_melee", "special_ability": "bolt"}]

    def test_only_blocking_rows_of_breaths_go(self):
        kept, removed = rules.breath_usage_rows(self.ROWS, {"dragon"})
        self.assertEqual([r["invalid_usage_flag"] for r in removed],
                         ["engaged_in_melee", "grounded"])
        self.assertIn({"invalid_usage_flag": "climbing", "special_ability": "dragon"}, kept)
        self.assertIn({"invalid_usage_flag": "engaged_in_melee", "special_ability": "bolt"}, kept)

    def test_vendored_tsv(self):
        text = ("invalid_usage_flag\tspecial_ability\n"
                "#special_ability_to_invalid_usage_flags_tables;0;db/x/@y\n"
                "engaged_in_melee\tld_breath\nclimbing\tld_breath\n"
                "engaged_in_melee\tld_plan\n")
        out, n = rules.rewrite_vendored_usage_flags_tsv(text, {"ld_breath"})
        self.assertEqual(n, 1)
        self.assertNotIn("engaged_in_melee\tld_breath", out)
        self.assertIn("climbing\tld_breath", out)
        self.assertIn("engaged_in_melee\tld_plan", out)
        same, zero = rules.rewrite_vendored_usage_flags_tsv(text, {"other"})
        self.assertEqual((same, zero), (text, 0))


class InstalledTable(unittest.TestCase):
    DB = Path(db_writer.VANILLA_SCALE_DB_PACK)

    def test_replacement_drops_exactly_the_breath_rows(self):
        writer, removed, breath = rules.breath_usage_writer(
            self.DB, self.DB.parent / "local_en.pack")
        rows, _h = installed_db_table.decode_round_trip(
            self.DB, rules.USAGE_FLAGS_TABLE, "test_air_dive_breath")
        self.assertEqual(len(writer.rows) + len(removed), len(rows))
        self.assertTrue(removed)
        for r in writer.rows:
            self.assertFalse(r["special_ability"] in breath
                             and r["invalid_usage_flag"] in rules.BREATH_BLOCK_FLAGS, r)
        # CA's own dragon breath is among them
        self.assertIn("wh2_main_unit_abilities_star_dragons_breath",
                      {r["special_ability"] for r in removed})


if __name__ == "__main__":
    unittest.main()

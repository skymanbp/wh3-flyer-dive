"""[RENAME-1118, docs/DECISIONS.md D9] No name this mod ships carries `ld`.

The repository side of ``tools/rename_1118.py check``: the code and Workshop
texts hold no old name outside the ones kept on purpose (the Lore Disasters
mod's keys as adapter input, the external test reader, prose about that mod),
and nothing under ``mod/script/`` is ever let through. The packs' side needs a
build and is run by hand (``rename_1118.py check --pack ...``).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rolepath  # imported for its side effect: puts the tool role directories on sys.path

import build_air_dive_minimod as mini  # noqa: E402 -- found through rolepath (pipelines/)
import rename_1118  # noqa: E402 -- lives in tools/, put on sys.path above


class NoOldNames(unittest.TestCase):
    def test_tree_is_clean(self):
        self.assertEqual(rename_1118.check_tree(), [])

    def test_shipped_names(self):
        for name in (mini.MAIN_PACK_NAME, mini.FRAGMENT, mini.BALANCE_PACK_NAME):
            with self.subTest(name=name):
                self.assertIsNone(rename_1118.TOKEN.search(name))

    def test_scripts_are_never_allowed(self):
        """The allowlist must not reach the shipped scripts (negative control:
        a kept main-mod key inside mod/script/ is still an old name)."""
        self.assertIsNone(rename_1118.allowed_reason("mod/script/x.lua", "ld_mod", set()))
        self.assertIsNone(rename_1118.allowed_reason("mod/script/x.lua", "Lore Disasters", set()))
        self.assertEqual(rename_1118.allowed_reason("mod/tools/x.py", "ld_mod", set()), "MAIN_MOD")

    def test_a_planted_old_name_is_found(self):
        """Negative control for the pack scan's pattern: each old form is caught,
        the look-alikes inside ordinary words are not."""
        for bad in ("ld_air_dive", "x_ld_dive_v144", "LDFLYPN2", "Lore Disasters", "LD_WH3_DATA"):
            with self.subTest(bad=bad):
                self.assertIsNotNone(rename_1118.TOKEN.search(bad))
        for fine in ("build_air_dive_minimod", "world_", "shield_bash", "flyer_dive_takeoff"):
            with self.subTest(fine=fine):
                self.assertIsNone(rename_1118.TOKEN.search(fine))


if __name__ == "__main__":
    unittest.main()

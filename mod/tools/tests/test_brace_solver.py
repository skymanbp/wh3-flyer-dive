"""[D25 / D29 / D31, brace-solver-1120] The braced line against a dive: cave dv_brace in the engine's pair solver,
the settings (lib/brace_rule.lua), the battle entry's use of them, the MCT stand-in.

Pinned here (system Python: no keystone, no unicorn):
* the committed site table carries dv_brace at the solver's velocity block with the replaced bytes' first
  instruction as its stolen bytes and resume 26; its bytes decode with capstone, instruction by instruction, to the
  source; a changed byte is caught;
* by inspection of the decoded bytes: rax / rcx / rdx and xmm0 saved and restored, only xmm1 / xmm2 / xmm6 / xmm12
  (and rsp) left changed, memory written only on the stack and through rdx (the buffer), no call, no rip-relative
  operand, every jump inside the cave, one ret (the push / ret return) at the end, the replaced code's last
  flag-setter (test r13b, r13b) right before the return;
* the installed exe holds the pattern exactly once at 0x1431781e9, its first 26 bytes are the replaced code, and
  they decode to the solver's own instructions (the brace multiplies of PAIR-SOLVER-1120); no jump or call from
  outside lands inside the replaced range (byte scan; the scan finds the range's own internal jump when told not to
  skip it);
* LuaJIT: lib/brace_rule.lua decides the settings (D14 / D31 multiplayer rule, MCT values, out-of-range and
  failing reads fall back per setting), its words equal air_dive_rules.brace_word / reflect_word; the battle
  entry writes both words once MCT has its values (or at Deployed), 0 when the switch is off; the MCT stand-in
  hands its values to it. [D51] D15's dive cost (its share, table and module) is removed.
The emulator check (28 cases against the replaced bytes themselves, 19 broken caves each caught) needs keystone +
unicorn and runs in dive_cost_asm.py before it writes the table. luajit or the installed exe missing is a failure,
not a skip.
"""
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent
MOD_DIR = TOOLS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path
import air_dive_rules  # noqa: E402 -- because rolepath above puts lib/ on sys.path
import dive_cave_asm as base  # noqa: E402 -- same reason (pipelines/)
import dive_cost_asm  # noqa: E402 -- same reason
import dive_brace_asm as brace  # noqa: E402 -- same reason
from cave_site_cases import read_site_text  # noqa: E402 -- because it follows the sys.path bootstrap above

SITE_FILE = MOD_DIR / base.SITE_LUA
GAME_EXE = Path(os.environ.get("WH3_GAME_EXE", str(base.EXE)))
BRACE_LUA = MOD_DIR / "script" / "campaign" / "flyer_dive" / "lib" / "brace_rule.lua"


def site_code(text, name="dv_brace"):
    m = re.search(rf"name = '{name}'.*?bytes = '([^']*)'", text, re.S)
    if not m:
        raise AssertionError(f"{name} not in the site table")
    marks = {"{buf:8}": struct.pack("<Q", base.BUF_PLACEHOLDER), "{resume:8}": struct.pack("<Q", base.RESUME_PLACEHOLDER)}
    return b"".join(marks[t] if t in marks else bytes([int(t, 16)]) for t in m.group(1).split())


def _decode(code, at=0x1000):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    ins = list(md.disasm(code, at))
    if sum(i.size for i in ins) != len(code):
        raise AssertionError("the bytes do not decode to whole instructions")
    return ins


def _num(m):
    return str(int(m.group(0), 0))


def _norm(text):
    t = re.sub(r"\s+", " ", text.strip().lower())
    t = t.replace("movabs ", "mov ").replace(" + 0]", "]")
    t = re.sub(r"\b0x[0-9a-f]+\b|\b\d+\b", _num, t)
    parts = t.split(" ", 1)
    if parts[0].startswith("j") or parts[0] == "call":
        return {"jz": "je", "jnz": "jne"}.get(parts[0], parts[0])                                        # a label: the target is checked by inspection
    return t


def source_lines(src):
    return [_norm(ln) for ln in src.splitlines() if ln.strip() and not ln.strip().endswith(":")]


def decode_mismatches(code, src):
    got = [_norm(f"{i.mnemonic} {i.op_str}") for i in _decode(code)]
    want = source_lines(src)
    out = [f"#{n}: {g!r} != {w!r}" for n, (g, w) in enumerate(zip(got, want)) if g != w]
    if len(got) != len(want):
        out.append(f"{len(got)} instructions decoded, {len(want)} in the source")
    return out


ALLOWED_LEFT = {"xmm1", "xmm2", "xmm6", "xmm12"}
SAVED = {"rax", "eax", "rcx", "ecx", "rdx", "edx", "xmm0"}


def inspection_problems(code):
    import capstone
    from capstone import x86
    ins = _decode(code)
    text = [f"{i.mnemonic} {i.op_str}".strip() for i in ins]
    probs = []
    if text[:3] != ["push rax", "push rcx", "push rdx"]:
        probs.append(f"start {text[:3]}")
    tail = [_norm(t) for t in text[-10:-1]]
    want_tail = [_norm(t) for t in ("movdqu xmm0, xmmword ptr [rsp]", "lea rsp, [rsp + 0x10]", "pop rdx", "pop rcx",
                                    "pop rax", "test r13b, r13b", "push rax", "movabs rax, 0x8877665544332211",
                                    "xchg qword ptr [rsp], rax")]
    if tail != want_tail:
        probs.append(f"end {text[-10:-1]}")
    if text[-1:] != ["ret"]:
        probs.append(f"last {text[-1:]}")
    end = 0x1000 + len(code)
    for i, t in zip(ins, text):
        if i.mnemonic in ("call", "syscall", "int3") or i.mnemonic.startswith("rep"):
            probs.append(f"{t} at {i.address:#x}")
        if i.mnemonic == "ret" and i is not ins[-1]:
            probs.append(f"ret before the end at {i.address:#x}")
        if i.group(capstone.CS_GRP_JUMP) and not (0x1000 <= int(i.op_str, 16) < end):
            probs.append(f"jump out of the cave: {t}")
        _r, written = i.regs_access()
        names = {i.reg_name(r) for r in written} - {"rsp", "rflags"}
        if names - SAVED - ALLOWED_LEFT:
            probs.append(f"{t} writes {names - SAVED - ALLOWED_LEFT}")
        for op in i.operands:
            if op.type != x86.X86_OP_MEM:
                continue
            reg = i.reg_name(op.mem.base) if op.mem.base else None
            if reg == "rip":
                probs.append(f"rip-relative {t}")
            if op.access & capstone.CS_AC_WRITE and reg not in ("rsp", "rdx"):
                probs.append(f"memory write outside the stack and the buffer: {t}")
            if op.access & capstone.CS_AC_WRITE and reg == "rdx" and i.mnemonic != "lock inc":
                probs.append(f"buffer write other than the counter: {t}")
    return probs


class SiteTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = read_site_text(SITE_FILE)
        cls.code = site_code(cls.text)
        cls.src = brace.source(dive_cost_asm.BRACE_WORD_AT, dive_cost_asm.BRACE_COUNT_AT)

    def test_current_and_the_marker(self):
        self.assertTrue(dive_cost_asm.check_site_file(MOD_DIR))
        self.assertIn("magic = 'FLYDIVE7'", self.text)
        self.assertEqual(dive_cost_asm.MAGIC, b"FLYDIVE7")
        self.assertIn("dv_brace = 26, dv_reflect = 5 }", self.text)
        self.assertIn(f"            pattern = '{brace.SITE}',", self.text.splitlines())
        self.assertIn(f"            at = 0, expect = '{brace.STOLEN}',", self.text.splitlines())
        self.assertIn(f"default_word = {air_dive_rules.brace_word(air_dive_rules.BRACE_MASS_K, air_dive_rules.BRACE_SHARE_MIN)},",
                      self.text)

    def test_layout_after_the_reserved_area(self):
        # [D51] the 3136 bytes D15's cost used stay reserved, so dv_brace's offsets are those it shipped with
        lay = dive_cost_asm.layout()
        self.assertEqual(lay["brace_word_at"], dive_cost_asm.RESERVED_AT + 64 + 64 * 48)
        self.assertEqual(lay["brace_word_at"], 10432)
        self.assertEqual(lay["brace_count_at"], lay["brace_word_at"] + 4)
        self.assertEqual((lay["reflect_word_at"], lay["reflect_count_at"]),
                         (lay["brace_word_at"] + 8, lay["brace_word_at"] + 12))
        self.assertEqual(lay["bytes"], lay["brace_word_at"] + 64)
        self.assertEqual(lay["brace_word_at"] % 64, 0)

    def test_bytes_decode_to_the_source(self):
        self.assertEqual(decode_mismatches(self.code, self.src), [])

    def test_decode_check_catches_a_changed_byte(self):
        code = bytearray(self.code)
        at = bytes(code).index(bytes.fromhex("F3440F5FE0"))            # maxss xmm12, xmm0
        code[at + 3] = 0x5D                                            # -> minss xmm12, xmm0
        self.assertTrue(decode_mismatches(bytes(code), self.src))

    def test_registers_memory_and_return_by_inspection(self):
        self.assertEqual(inspection_problems(self.code), [])

    def test_inspection_catches_breakage(self):
        code = self.code
        self.assertTrue(inspection_problems(code.replace(bytes.fromhex("5A5958"), bytes.fromhex("5A5858"), 1)))  # rcx
        rbx = code.replace(bytes.fromhex("4584ED"), bytes.fromhex("31DB90"), 1)                     # xor ebx, ebx
        self.assertTrue(inspection_problems(rbx))
        self.assertTrue(inspection_problems(code[:-1]))                                             # no ret


class InstalledExe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not GAME_EXE.is_file():
            raise RuntimeError(f"required input missing: installed game exe {GAME_EXE}")
        import pefile
        cls.pe = pefile.PE(str(GAME_EXE), fast_load=True)
        cls.image = cls.pe.OPTIONAL_HEADER.ImageBase

    def test_site_once_with_the_replaced_bytes(self):
        found = dive_cost_asm.check_exe(GAME_EXE)
        self.assertEqual(found["dv_brace"], brace.EXE_SITE)
        rva = brace.EXE_SITE - self.image
        self.assertEqual(self.pe.get_data(rva, len(brace.REPLACED)), brace.REPLACED)

    def test_replaced_bytes_are_the_solvers_brace_multiplies(self):
        got = [f"{i.mnemonic} {i.op_str}" for i in _decode(brace.REPLACED, brace.EXE_SITE)]
        self.assertEqual(got, ["test r12b, r12b", "je 0x1431781f4", "mulss xmm2, dword ptr [r14 + 0x54]",
                               "movss xmm1, dword ptr [rbx + 0x4c]", "test r13b, r13b", "je 0x143178203",
                               "mulss xmm1, dword ptr [rbx + 0x54]"])
        # the stolen bytes end on an instruction boundary
        self.assertEqual(sum(i.size for i in _decode(brace.REPLACED)[:2]), len(bytes.fromhex(brace.STOLEN.replace(" ", ""))))

    @classmethod
    def all_branches_into(cls):
        """(source, target) of every rel8 / rel32 jump or call byte pattern in the code sections whose target lies in
        site+1 .. site+25 (numpy over every byte offset; a hit may be bytes inside a longer instruction)."""
        if getattr(cls, "_hits", None) is not None:
            return cls._hits
        import numpy as np
        lo, hi = brace.EXE_SITE + 1, brace.EXE_SITE + brace.RESUME_OFF - 1
        hits = []
        for s in cls.pe.sections:
            if not s.Characteristics & 0x20000000:
                continue
            a = np.frombuffer(s.get_data(), dtype=np.uint8)
            va0, n = cls.image + s.VirtualAddress, len(a) - 6

            def rel32(p):
                v = (a[p].astype(np.int64) | (a[p + 1].astype(np.int64) << 8) | (a[p + 2].astype(np.int64) << 16)
                     | (a[p + 3].astype(np.int64) << 24))
                return np.where(v >= 1 << 31, v - (1 << 32), v)
            b0, b1 = a[:n], a[1:n + 1]
            for kind in ("call/jmp", "jcc", "rel8"):
                if kind == "call/jmp":
                    p = np.nonzero((b0 == 0xE8) | (b0 == 0xE9))[0].astype(np.int64)
                    t = va0 + p + 5 + rel32(p + 1)
                elif kind == "jcc":
                    p = np.nonzero((b0 == 0x0F) & (b1 >= 0x80) & (b1 <= 0x8F))[0].astype(np.int64)
                    t = va0 + p + 6 + rel32(p + 2)
                else:
                    p = np.nonzero(((b0 >= 0x70) & (b0 <= 0x7F)) | (b0 == 0xEB))[0].astype(np.int64)
                    r = a[p + 1].astype(np.int64)
                    t = va0 + p + 2 + np.where(r >= 128, r - 256, r)
                sel = (t >= lo) & (t <= hi)
                hits += [(int(va0 + x), int(y)) for x, y in zip(p[sel], t[sel])]
        cls._hits = hits
        return hits

    def branches_into(self, skip_own):
        site, end = brace.EXE_SITE, brace.EXE_SITE + brace.RESUME_OFF
        return [h for h in self.all_branches_into() if not (skip_own and site <= h[0] < end)]

    def test_nothing_jumps_into_the_replaced_range(self):
        self.assertEqual(self.branches_into(True), [])
        self.assertIn((0x1431781EC, 0x1431781F4), self.branches_into(False))      # the scan sees the range's own je


def luajit():
    path = shutil.which("luajit")
    if not path:
        raise AssertionError("luajit is required (no fallback)")
    return path


def run_lua(code, *args):
    with tempfile.TemporaryDirectory() as td:
        h = Path(td) / "case.lua"
        h.write_text(code, encoding="utf-8")
        proc = subprocess.run([luajit(), str(h), str(MOD_DIR).replace("\\", "/"), *args], capture_output=True,
                              cwd=td)
    if proc.returncode != 0:
        raise AssertionError(f"the case did not run: {proc.stderr.decode('utf-8', 'replace')[:800]}")
    return proc.stdout.decode("utf-8").splitlines()


RULE_CASE = r'''
local MOD = arg[1]
package.path = MOD .. "/?.lua;" .. package.path
local site = dofile(MOD .. "/script/campaign/flyer_dive/data/dive_site.lua")
local b = site.brace
local R = require("script/campaign/flyer_dive/lib/brace_rule")
local function mct(t) return function(m, o)
    if m ~= b.mct_mod then return nil end
    local v = t[o]
    if v == "boom" then error("boom", 0) end
    return v
end end
local function show(label, s)
    print(("%s|%s|%s|%s|%s|%s|%s|%s"):format(label, tostring(s.on), tostring(s.k), tostring(s.share),
        tostring(s.reflect), tostring(R.word(b, s)), tostring(R.reflect_word(b, s)), s.why))
end
local all = { [b.mct_on] = true, [b.mct_k] = 5.0, [b.mct_share] = 0.5, [b.mct_reflect] = 3.0 }
show("mp_outside", R.decide(b, true, false, mct({ [b.mct_on] = false })))
show("no_mct", R.decide(b, false, false, nil))
show("mct", R.decide(b, false, false, mct(all)))
show("mpc", R.decide(b, true, true, mct(all)))
show("off", R.decide(b, false, false, mct({ [b.mct_on] = false, [b.mct_k] = 5.0 })))
show("neutral", R.decide(b, false, false, mct({ [b.mct_on] = true, [b.mct_reflect] = 1.0 })))
show("bad", R.decide(b, false, false, mct({ [b.mct_on] = "yes", [b.mct_k] = 50, [b.mct_share] = "boom",
    [b.mct_reflect] = 0.5 })))
show("edges", R.decide(b, false, false, mct({ [b.mct_on] = true, [b.mct_k] = b.k_max, [b.mct_share] = b.share_min,
    [b.mct_reflect] = b.reflect_max })))
-- an MCT slider value is a float32: 3.4f, 0.8f, 0.35f
show("float32", R.decide(b, false, false, mct({ [b.mct_on] = true, [b.mct_k] = 3.4000000953674316,
    [b.mct_share] = 0.800000011920929, [b.mct_reflect] = 2.25 })))
show("float32b", R.decide(b, false, false, mct({ [b.mct_on] = true, [b.mct_k] = 1.25,
    [b.mct_share] = 0.3499999940395355, [b.mct_reflect] = 1.7499999 })))
print("DESC " .. R.describe(b, R.decide(b, false, false, nil)))
print("DESC " .. R.describe(b, R.decide(b, false, false, mct({ [b.mct_on] = false }))))
'''


def rule_rows():
    rows = {}
    for ln in run_lua(RULE_CASE):
        if "|" in ln:
            parts = ln.split("|")
            rows[parts[0]] = parts[1:]
        else:
            rows.setdefault(ln.split()[0], []).append(ln)
    return rows


class BraceRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rule_rows()
        r = air_dive_rules
        cls.default_word = str(r.brace_word(r.BRACE_MASS_K, r.BRACE_SHARE_MIN))
        cls.default_reflect = str(r.reflect_word(r.REFLECT_FLYER_FACTOR))

    def test_defaults_without_mct_and_outside_a_campaign(self):
        for label, why in (("mp_outside", "multiplayer battle outside a campaign"), ("no_mct", "MCT not installed")):
            with self.subTest(label=label):
                on, k, share, reflect, word, rword, w = self.rows[label]
                self.assertEqual((on, k, share, reflect), ("true", "4", "0.5", "2"))  # D62 k 4 / D51 (Lua prints 4.0 as 4)
                self.assertEqual(word, self.default_word)
                self.assertEqual(rword, self.default_reflect)
                self.assertEqual(rword, "200")
                self.assertIn(why, w)

    def test_mct_values_single_player_and_multiplayer_campaign(self):
        want_word = str(air_dive_rules.brace_word(5.0, 0.5))
        self.assertEqual(self.rows["mct"][:7], ["true", "5", "0.5", "3", want_word, "300", "MCT"])
        self.assertEqual(self.rows["mpc"][:7], ["true", "5", "0.5", "3", want_word, "300",
                                                "MCT, multiplayer campaign"])

    def test_switch_off_and_neutral_factor(self):
        self.assertEqual(self.rows["off"][0], "false")
        self.assertEqual(self.rows["off"][4:6], ["0", "0"])
        self.assertEqual(self.rows["neutral"][4:6], [self.default_word, "100"])        # 1.00 = the base game

    def test_bad_values_fall_back_one_by_one(self):
        on, k, share, reflect, word, rword, why = self.rows["bad"]
        self.assertEqual((on, k, share, reflect, word, rword), ("true", "4", "0.5", "2", self.default_word,
                                                                self.default_reflect))
        for note in ("on default (MCT holds yes)", "k default (MCT holds 50)", "share default (reading MCT failed: boom)",
                     "reflect default (MCT holds 0.5)"):
            self.assertIn(note, why)

    def test_words_equal_the_rules_file(self):
        r = air_dive_rules
        self.assertEqual(self.rows["edges"][4], str(r.brace_word(r.BRACE_MASS_K_RANGE[1], r.BRACE_SHARE_MIN_RANGE[0])))
        self.assertEqual(self.rows["edges"][5], str(r.reflect_word(r.REFLECT_FLYER_FACTOR_RANGE[1])))
        self.assertEqual(self.rows["float32"][4], str(r.brace_word(3.4, 0.8)))   # float32 3.4f / 0.8f decode exactly
        self.assertEqual(self.rows["float32"][5], str(r.reflect_word(2.25)))
        self.assertEqual(self.rows["float32b"][4], str(r.brace_word(1.25, 0.35)))
        self.assertEqual(self.rows["float32b"][5], str(r.reflect_word(1.75)))      # 1.7499999 rounds to 175
        with self.assertRaises(ValueError):
            r.reflect_word(0.5)
        with self.assertRaises(ValueError):
            r.reflect_word(4.5)
        self.assertLess(r.brace_word(r.BRACE_MASS_K_RANGE[1], r.BRACE_SHARE_MIN_RANGE[1]), 1 << 24)  # exact in float32
        with self.assertRaises(ValueError):
            r.brace_word(0.5, 0.8)
        with self.assertRaises(ValueError):
            r.brace_word(3.4, 1.5)

    def test_text(self):
        self.assertEqual(self.rows["DESC"][0], f"DESC on: braced mass x{air_dive_rules.BRACE_MASS_K:.2f} against a diving flyer, its share of the "
                                               f"slowing at least {air_dive_rules.BRACE_SHARE_MIN:.2f}, word {self.default_word}, "
                                               f"Charge Reflection on flyers x{air_dive_rules.REFLECT_FLYER_FACTOR:.2f}, word {self.default_reflect}")
        self.assertEqual(self.rows["DESC"][1],
                         "DESC off: braced units against a dive and Charge Reflection on flyers as in the base game")


ENTRY_CASE = r'''
local MOD, MODE, STUB = arg[1], arg[2], arg[3]
package.path = MOD .. "/?.lua;" .. package.path
local site = dofile(MOD .. "/script/campaign/flyer_dive/data/dive_site.lua")
local b = site.brace
package.preload["script/campaign/flyer_dive/data/dive_site"] = function() return site end
local events = {}
local function ev(s) events[#events + 1] = s end
package.preload["script/campaign/flyer_dive/lib/dive"] = function()
    return {
        install = function() return "BUF" end,
        find = function() return "BUF", true end,
        allowed = function() return true end,
        pass_through = function() end,
        arm = function() ev("ARM") end,
        set_brace = function(_, w, r) ev("WORD " .. tostring(w) .. " " .. tostring(r)) end,
        counters = function() return { throughs = 0, skipped = 0, kept = 0, engaged = 0, reordered = 0, contact = 0,
            settled = 0, released = 0, committed = 0, closed = 0, engaged_body = 0, braced = 7, reflected = 3 } end,
    }
end
_G.memreader_plus = {}
local real_open = io.open
io.open = function(path, mode)
    if path == "flyer_dive.txt" then
        return { write = function(_, s) ev("LOG " .. s:gsub("^%S+ %S+ ", ""):gsub("\n$", "")) end, close = function() end }
    end
    return real_open(path, mode)
end
local MP = { mp_off = true, mpc_off = true }
local CAMPAIGN = { mpc_off = true }
local listeners, phases, callbacks = {}, {}, {}
bm = {
    is_multiplayer = function() return MP[MODE] == true end,
    is_from_campaign = function() return CAMPAIGN[MODE] == true end,
    register_phase_change_callback = function(_, phase, fn) phases[phase] = fn end,
    repeat_callback = function(_, fn, ms, name) callbacks[#callbacks + 1] = { fn = fn, name = name } end,
    remove_callback = function() end,
    time_elapsed_ms = function() return 1000 end,
}
core = { add_listener = function(_, name, event, cond, fn) listeners[#listeners + 1] = { event = event, fn = fn } end }
local VALUES = {
    mct = { [b.mct_on] = true, [b.mct_k] = 5.0, [b.mct_share] = 0.5, [b.mct_reflect] = 3.0 },
    mct_off = { [b.mct_on] = false }, mp_off = { [b.mct_on] = false }, mpc_off = { [b.mct_on] = false },
    neutral = { [b.mct_on] = true, [b.mct_reflect] = 1.0 }, silent = { [b.mct_k] = 3.0 },
}
if MODE == "stub" then
    local f = assert(real_open(STUB, "rb")); local text = f:read("*a"); f:close()
    assert(loadstring(text))()
elseif VALUES[MODE] then
    get_mct = function() return { get_mod_by_key = function(_, m)
        if m ~= b.mct_mod then return nil end
        return { get_option_by_key = function(_, o)
            local v = VALUES[MODE][o]
            if v == nil then return nil end
            return { get_finalized_setting = function() return v end }
        end }
    end } end
end
dofile(MOD .. "/script/battle/mod/flyer_dive.lua")
ev("LOADED " .. #listeners)
if MODE ~= "silent" then
    for _, l in ipairs(listeners) do if l.event == "ScriptEventAllModsLoaded" then l.fn() end end
    for _, l in ipairs(listeners) do if l.event == "MctInitialized" then l.fn() end end
end
if phases.Deployed then phases.Deployed() end
for _, c in ipairs(callbacks) do if c.name == "flyer_dive_counts" then c.fn() end end
for _, e in ipairs(events) do print(e) end
'''


def entry(mode, stub=None):
    lines = run_lua(ENTRY_CASE, mode, *( [stub] if stub else []))
    return [ln for ln in lines if not ln.startswith("LOG BATTLE")]


class BattleEntry(unittest.TestCase):
    default_word = air_dive_rules.brace_word(air_dive_rules.BRACE_MASS_K, air_dive_rules.BRACE_SHARE_MIN)
    default_reflect = air_dive_rules.reflect_word(air_dive_rules.REFLECT_FLYER_FACTOR)

    def brace_lines(self, lines):
        return [ln for ln in lines if ln.startswith("LOG BRACE")]

    def words(self, lines):
        return [ln for ln in lines if ln.startswith("WORD")]

    def test_without_mct_defaults_at_load(self):
        lines = entry("none")
        self.assertEqual(lines[0], "ARM")
        self.assertEqual(self.words(lines), [f"WORD {self.default_word} {self.default_reflect}"])
        self.assertEqual(len(self.brace_lines(lines)), 1)
        self.assertIn("(default (MCT not installed); read on load (no MCT))", self.brace_lines(lines)[0])
        self.assertTrue([ln for ln in lines if ln.endswith("braced masses scaled 7, Charge Reflection hits on flyers "
                                                           "raised 3")], lines)
        self.assertFalse([ln for ln in lines if "COST" in ln], lines)

    def test_mct_values_once_both_events_fired(self):
        lines = entry("mct")
        self.assertEqual(lines[:2], ["ARM", "LOADED 2"])                     # nothing read before MCT has values
        self.assertEqual(self.words(lines), [f"WORD {air_dive_rules.brace_word(5.0, 0.5)} "
                                             f"{air_dive_rules.reflect_word(3.0)}"])
        self.assertEqual(len(self.brace_lines(lines)), 1)
        self.assertIn("(MCT; read on ScriptEventAllModsLoaded)", self.brace_lines(lines)[0])

    def test_switch_off_both_words_zero(self):
        self.assertEqual(self.words(entry("mct_off")), ["WORD 0 0"])

    def test_neutral_factor_keeps_the_brace(self):
        self.assertEqual(self.words(entry("neutral")), [f"WORD {self.default_word} 100"])

    def test_multiplayer(self):
        out = entry("mp_off")                                                # outside a campaign: defaults
        self.assertEqual(self.words(out), [f"WORD {self.default_word} {self.default_reflect}"])
        self.assertIn("multiplayer battle outside a campaign", self.brace_lines(out)[0])
        camp = entry("mpc_off")                                              # campaign: the host's (MCT's) value
        self.assertEqual(self.words(camp), ["WORD 0 0"])
        self.assertIn("MCT, multiplayer campaign", self.brace_lines(camp)[0])

    def test_read_at_deployed_when_no_event_came(self):
        lines = entry("silent")
        self.assertEqual(len(self.brace_lines(lines)), 1)
        self.assertIn("read on Deployed", self.brace_lines(lines)[0])
        self.assertEqual(self.words(lines), [f"WORD {air_dive_rules.brace_word(3.0, air_dive_rules.BRACE_SHARE_MIN)} "
                                             f"{self.default_reflect}"])

    def test_stand_in_hands_its_values_over(self):
        import build_breath_mct_stub as stub
        with tempfile.TemporaryDirectory() as td:
            for brace_v, want in ((stub.brace_values(False), "WORD 0 0"),
                                  (stub.brace_values(True, 2.5, 0.4, 3.5),
                                   f"WORD {air_dive_rules.brace_word(2.5, 0.4)} {air_dive_rules.reflect_word(3.5)}"),
                                  (None, f"WORD {self.default_word} {self.default_reflect}")):
                with self.subTest(brace=brace_v):
                    _path, data = stub.stub_entry("off", brace_v)
                    f = Path(td) / "stub.lua"
                    f.write_bytes(data)
                    self.assertEqual(self.words(entry("stub", str(f))), [want])
        with self.assertRaises(ValueError):
            stub.brace_values(True, reflect=5.0)
        with self.assertRaises(SystemExit):
            stub.main(["--value", "on", "--k", "2", "--out", "x.pack"])
        with self.assertRaises(SystemExit):
            stub.main(["--value", "on", "--reflect", "2", "--out", "x.pack"])
        with self.assertRaises(ValueError):
            stub.brace_values(True, k=0.5)


if __name__ == "__main__":
    unittest.main()

"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 4): find code that stores an immediate into [reg + 0x90] (the flight
controller's phase: 1 landed, 4 descending, 5 final approach, 6 go-around, read from the bob probe), and
list, for each such store of 5 or 6, nearby stores to +0x3c / +0x60 / +0x38 in the same 0x400-byte window.
usage: python -I fcscan.py"""
import re, sys
from pathlib import Path
sys.path.append(str(Path(r"D:/Projects/.worktrees/lore_disaster/air-dive-continuous-w1_scratch/venv/Lib/site-packages")))
import capstone, pefile

EXE = r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\Warhammer3.exe"
pe = pefile.PE(EXE, fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
sec = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".xpdata")
data = sec.get_data()
va0 = base + sec.VirtualAddress
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
# mov dword ptr [r + 0x90], imm32: (REX.B)? C7 (80+r) 90 00 00 00 imm32 (r != 4/5 forms with SIB/rip skipped)
pat = re.compile(rb"(?:[\x41])?\xC7[\x80-\x87]\x90\x00\x00\x00([\x00-\x0f])\x00\x00\x00", re.S)
hits = []
for m in pat.finditer(data):
    imm = m.group(1)[0]
    if imm in (4, 5, 6):
        hits.append((va0 + m.start(), imm))
print(f"stores of 4/5/6 into [r+0x90]: {len(hits)}")


def window(va, before=0x300, after=0x100):
    off = va - va0
    start = max(0, off - before)
    out = []
    for ins in md.disasm(data[start:off + after], va0 + start):
        out.append(ins)
    return out


for va, imm in hits:
    ins = window(va)
    near = [i for i in ins if re.search(r"\+ 0x(3c|60|38)\]", i.op_str) and i.mnemonic.startswith("mov")
            and i.op_str.startswith(("dword ptr", "qword ptr"))]
    tag = ", ".join(f"{i.address:x} {i.mnemonic} {i.op_str}" for i in near[-6:])
    print(f"{va:x} imm {imm} | {tag}")

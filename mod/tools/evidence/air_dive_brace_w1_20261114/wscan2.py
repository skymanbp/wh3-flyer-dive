"""TEST-ONLY: every instruction that writes entity +0xb28 (and its immediate if any)."""
import sys, re
sys.path.append(r"D:\Projects\.worktrees\lore_disaster\air-dive-continuous-w1_scratch\venv\Lib\site-packages")
import pefile, capstone
from capstone import x86
pe = pefile.PE(r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\Warhammer3.exe", fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
sec = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".xpdata")
data = sec.get_data(); va0 = base + sec.VirtualAddress
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail = True
disp = int(sys.argv[1], 16)
pat = disp.to_bytes(4, "little"); seen = set()
for m in re.finditer(re.escape(pat), data):
    p = m.start()
    for back in range(2, 8):
        s = p - back
        for ins in md.disasm(data[s:s + 16], va0 + s, 1):
            if ins.size >= back + 4 and ins.operands and ins.operands[0].type == x86.X86_OP_MEM \
                    and ins.operands[0].mem.disp == disp and ins.mnemonic in ("mov", "inc", "dec", "add", "sub", "and", "or", "xchg") \
                    and ins.operands[0].mem.base not in (x86.X86_REG_RSP, x86.X86_REG_RIP, x86.X86_REG_RBP) and ins.address not in seen:
                seen.add(ins.address); print(f"{ins.address:x} {ins.mnemonic} {ins.op_str}")

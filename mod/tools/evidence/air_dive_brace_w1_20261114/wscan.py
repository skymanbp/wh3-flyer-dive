"""TEST-ONLY: find code that writes entity +0x17c, +0x180 and +0x1e0 close together (the goal-collapse signature)."""
import sys, re, bisect
sys.path.append(r"D:\Projects\.worktrees\lore_disaster\air-dive-continuous-w1_scratch\venv\Lib\site-packages")
import pefile, capstone
from capstone import x86
pe = pefile.PE(r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\Warhammer3.exe", fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
text = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".xpdata")
data = text.get_data(); va0 = base + text.VirtualAddress
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail = True
def writes(disp):
    pat = disp.to_bytes(4, "little"); out = set()
    for m in re.finditer(re.escape(pat), data):
        p = m.start()
        for back in range(2, 8):
            s = p - back
            for ins in md.disasm(data[s:s + 16], va0 + s, 1):
                if ins.size >= back + 4 and len(ins.operands) >= 1 and ins.operands[0].type == x86.X86_OP_MEM \
                        and ins.operands[0].mem.disp == disp and ins.mnemonic.startswith(("mov", "and", "or")) \
                        and ins.operands[0].mem.base not in (x86.X86_REG_RSP, x86.X86_REG_RIP, x86.X86_REG_RBP):
                    out.add((ins.address, f"{ins.mnemonic} {ins.op_str}"))
    return sorted(out)
W = {d: writes(d) for d in (0x17c, 0x180, 0x1e0, 0x1e8, 0x188)}
for d, l in W.items(): print(hex(d), len(l))
a17c = [a for a, _ in W[0x17c]]
for a, s in W[0x1e0]:
    near = lambda d: [x for x in W[d] if abs(x[0] - a) < 0x300]
    if near(0x17c) and near(0x180):
        print(f"== goal write {a:x} {s}")
        for d in (0x17c, 0x180, 0x188, 0x1e8):
            for x in near(d): print(f"     {d:#x} {x[0]:x} {x[1]}")

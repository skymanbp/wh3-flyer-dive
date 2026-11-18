"""TEST-ONLY: disassemble the contact-engage caller after the +0x4b0 call and the melee-order default."""
import sys
sys.path.append(r"D:Projects.worktreesore_disasterir-dive-continuous-w1_scratchenvibsite-packages")
import pefile, capstone
pe = pefile.PE(r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\Warhammer3.exe", fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
def dis(va, n):
    off = pe.get_offset_from_rva(va - base)
    data = pe.__data__[off:off + n]
    for i in md.disasm(data, va):
        print(f"  {i.address:x} {i.mnemonic} {i.op_str}")
for a, n in ((int(x, 16), int(y)) for x, y in (s.split(":") for s in sys.argv[1:])):
    print(f"== {a:x}"); dis(a, n)

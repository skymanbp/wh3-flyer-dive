"""TEST-ONLY: direct rel32 call / jmp sites of the given targets in the code section, plus vtable refs."""
import sys, struct
sys.path.append(r"D:\Projects\.worktrees\lore_disaster\air-dive-continuous-w1_scratch\venv\Lib\site-packages")
import pefile
pe = pefile.PE(r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\Warhammer3.exe", fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
sec = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".xpdata")
d = sec.get_data(); va0 = base + sec.VirtualAddress
import numpy as np
arr = np.frombuffer(d, dtype=np.uint8)
for t in (int(x, 16) for x in sys.argv[1:]):
    hits = []
    for op in (0xE8, 0xE9):
        idx = np.nonzero(arr[:-5] == op)[0]
        rel = (arr[idx+1].astype(np.int64) | (arr[idx+2].astype(np.int64) << 8) | (arr[idx+3].astype(np.int64) << 16) | (arr[idx+4].astype(np.int64) << 24))
        rel = np.where(rel >= 2**31, rel - 2**32, rel)
        tgt = va0 + idx + 5 + rel
        for i in idx[tgt == t]: hits.append((va0 + int(i), "call" if op == 0xE8 else "jmp"))
    allb = bytes(pe.__data__[:])
    vt = allb.count(struct.pack("<Q", t))
    print(f"{t:x}: {len(hits)} direct, {vt} qword refs:", " ".join(f"{a:x}/{k}" for a, k in sorted(hits)[:40]))

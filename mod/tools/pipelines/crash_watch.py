#!/usr/bin/env python3
"""
crash_watch.py — self-owned WH3 crash evidence collector / 自建崩溃取证器
=========================================================================
The game writes a minidump (.mdmp) + a module-name-only stack.txt on every
hard CTD, and (only on graceful DB rejection) bad_mods_report.txt. None of
that says WHICH code path crashed. This tool parses the minidump itself:

  * exception stream  -> exception code, faulting access address
  * thread context    -> RIP + all integer registers
  * module list       -> Warhammer3.exe base => STABLE module-relative crash
                         offset (same offset across rounds = same defect)
  * memory ranges     -> printable strings around every register + a
                         return-address sweep of the crashed thread's stack
                         (module+offset chain, comparable without symbols)

Usage:
    python tools/pipelines/crash_watch.py analyze <dump.mdmp> [...more dumps]
    python tools/pipelines/crash_watch.py latest [N]        # newest N dumps (default 2)
    python tools/pipelines/crash_watch.py watch             # poll; auto-analyze new dumps
    python tools/pipelines/crash_watch.py postmortem [MIN]  # root cause of a failure in the last MIN minutes (default 30)

watch mode: polls the crash_report dir every 2 s; when a new .mdmp appears it
waits for the file to stop growing, runs the same analysis, snapshots
bad_mods_report.txt / modified.log state, and appends a markdown report next
to the dump under crash_watch_reports/. The user only launches the game.
"""
import os
import re
import struct
import sys
import time

# Game evidence locations are derived from APPDATA at runtime (machine-portable).
CRASH_DIR = os.path.join(os.environ.get("APPDATA", ""),
                         "The Creative Assembly", "Warhammer3", "crash_report")
LOGS_DIR = os.path.join(os.environ.get("APPDATA", ""),
                        "The Creative Assembly", "Warhammer3", "logs")

STREAM_MODULE_LIST = 4
STREAM_MEMORY_LIST = 5
STREAM_EXCEPTION = 6
STREAM_MEMORY64_LIST = 9


class Minidump:
    def __init__(self, path):
        self.path = path
        self.data = open(path, "rb").read()
        if self.data[:4] != b"MDMP":
            raise ValueError(f"{path}: not a minidump")
        n_streams, dir_rva = struct.unpack_from("<II", self.data, 8)
        self.streams = {}
        for i in range(n_streams):
            stype, size, rva = struct.unpack_from("<III", self.data, dir_rva + 12 * i)
            self.streams.setdefault(stype, []).append((size, rva))
        self.modules = self._modules()
        self.ranges = self._memory_ranges()

    def _modules(self):
        out = []
        for size, rva in self.streams.get(STREAM_MODULE_LIST, []):
            count = struct.unpack_from("<I", self.data, rva)[0]
            pos = rva + 4
            for _ in range(count):
                base, msize = struct.unpack_from("<QI", self.data, pos)
                name_rva = struct.unpack_from("<I", self.data, pos + 20)[0]
                nlen = struct.unpack_from("<I", self.data, name_rva)[0]
                name = self.data[name_rva + 4:name_rva + 4 + nlen].decode(
                    "utf-16-le", "replace")
                out.append((base, msize, name))
                pos += 108
        return sorted(out)

    def _memory_ranges(self):
        ranges = []
        for size, rva in self.streams.get(STREAM_MEMORY64_LIST, []):
            count, base_rva = struct.unpack_from("<QQ", self.data, rva)
            pos = rva + 16
            file_off = base_rva
            for _ in range(count):
                start, dsize = struct.unpack_from("<QQ", self.data, pos)
                ranges.append((start, dsize, file_off))
                file_off += dsize
                pos += 16
        for size, rva in self.streams.get(STREAM_MEMORY_LIST, []):
            count = struct.unpack_from("<I", self.data, rva)[0]
            pos = rva + 4
            for _ in range(count):
                start, dsize, drva = struct.unpack_from("<QII", self.data, pos)
                ranges.append((start, dsize, drva))
                pos += 16
        return sorted(ranges)

    def read_mem(self, addr, size):
        for start, dsize, off in self.ranges:
            if start <= addr < start + dsize:
                take = min(size, start + dsize - addr)
                fo = off + (addr - start)
                return self.data[fo:fo + take]
        return b""

    def module_for(self, addr):
        for base, msize, name in self.modules:
            if base <= addr < base + msize:
                return os.path.basename(name), addr - base
        return None, None

    def exception(self):
        got = self.streams.get(STREAM_EXCEPTION)
        if not got:
            return None
        _size, rva = got[0]
        tid = struct.unpack_from("<I", self.data, rva)[0]
        code, flags = struct.unpack_from("<II", self.data, rva + 8)
        exc_addr = struct.unpack_from("<Q", self.data, rva + 24)[0]
        n_params = struct.unpack_from("<I", self.data, rva + 32)[0]
        params = struct.unpack_from(f"<{max(n_params, 1)}Q", self.data, rva + 40)[:n_params]
        ctx_size, ctx_rva = struct.unpack_from("<II", self.data, rva + 8 + 152)
        ctx = self.data[ctx_rva:ctx_rva + ctx_size]
        regs = {}
        # x64 CONTEXT offsets (winnt.h): Rax 0x78 .. R15 0xF0, Rip 0xF8
        names = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
                 "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]
        for i, nm in enumerate(names):
            regs[nm] = struct.unpack_from("<Q", ctx, 0x78 + 8 * i)[0]
        regs["rip"] = struct.unpack_from("<Q", ctx, 0xF8)[0]
        return {"tid": tid, "code": code, "flags": flags, "addr": exc_addr,
                "params": params, "regs": regs}


def printable_around(md, addr, before=48, after=112):
    """ASCII + UTF-16LE readable text around one address, or ''."""
    raw = md.read_mem(max(0, addr - before), before + after)
    if not raw:
        return ""
    ascii_txt = "".join(chr(c) if 32 <= c < 127 else "." for c in raw)
    wide = raw.replace(b"\x00", b"")
    wide_txt = "".join(chr(c) if 32 <= c < 127 else "." for c in wide)
    best = max((ascii_txt, wide_txt), key=lambda t: len(max(
        re.findall(r"[ -~]{6,}", t) or [""], key=len)))
    return best


def analyze(path):
    md = Minidump(path)
    exc = md.exception()
    lines = [f"# {os.path.basename(path)}", ""]
    if exc is None:
        lines.append("no exception stream")
        return "\n".join(lines)
    mod, off = md.module_for(exc["regs"]["rip"])
    lines.append(f"exception code : 0x{exc['code']:08X}"
                 + ("  (ACCESS_VIOLATION)" if exc["code"] == 0xC0000005 else ""))
    if exc["code"] == 0xC0000005 and len(exc["params"]) >= 2:
        rw = {0: "READ", 1: "WRITE", 8: "EXEC"}.get(exc["params"][0], exc["params"][0])
        lines.append(f"access         : {rw} at 0x{exc['params'][1]:016X}")
    lines.append(f"faulting RIP   : 0x{exc['regs']['rip']:016X}  "
                 f"= {mod}+0x{off:X}" if mod else
                 f"faulting RIP   : 0x{exc['regs']['rip']:016X} (unmapped)")
    types = cxx_exception_types(md, exc)
    if types:
        lines.append(f"C++ throw type : {types}")
    lines.append("")
    lines.append("## registers -> nearby readable memory")
    for nm, val in exc["regs"].items():
        ctx = printable_around(md, val)
        hits = re.findall(r"[ -~]{8,}", ctx)
        if hits:
            lines.append(f"  {nm:>3} = 0x{val:016X}  | {' | '.join(hits[:3])[:180]}")
    lines.append("")
    lines.append("## stack return-address chain (module+offset, no symbols)")
    rsp = exc["regs"]["rsp"]
    stack = md.read_mem(rsp, 0x2000)
    chain = []
    for i in range(0, len(stack) - 7, 8):
        val = struct.unpack_from("<Q", stack, i)[0]
        m, o = md.module_for(val)
        if m:
            chain.append(f"{m}+0x{o:X}")
        if len(chain) >= 24:
            break
    lines.extend(f"  {c}" for c in chain)
    return "\n".join(lines)


CXX_EXCEPTION = 0xE06D7363  # MSVC `throw`; params = magic, object*, ThrowInfo*, image base


def _pe_section_reader(path):
    """rva -> bytes reader over a PE file on disk (dumps omit the image)."""
    data = open(path, "rb").read()
    e = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, e + 6)[0]
    opt = struct.unpack_from("<H", data, e + 20)[0]
    secs = []
    p = e + 24 + opt
    for _ in range(nsec):
        vsize, va, rsize, raw = struct.unpack_from("<IIII", data, p + 8)
        secs.append((va, max(vsize, rsize), raw))
        p += 40

    def at(rva, n):
        for va, size, raw in secs:
            if va <= rva < va + size:
                return data[raw + rva - va:raw + rva - va + n]
        return b""
    return at


def cxx_exception_types(md, exc):
    """Type names a C++ throw was catchable as, e.g. ['bad_alloc@stdext', ...].

    [PROBE-W1 2026-10-15] The 20:57 smoke crash was a throw of
    stdext::bad_alloc -- the game could not get memory -- and nothing on the
    stack said so; reading the ThrowInfo is what named it. Type data is
    image-relative, so it is read from the exe the dump's module list names.
    Returns [] for any other exception code; raises if the exe is unreadable.
    """
    if exc["code"] != CXX_EXCEPTION or len(exc["params"]) < 4:
        return []
    _magic, _obj, throw, base = exc["params"][:4]
    exe = next(name for b, _s, name in md.modules if b == base)
    at = _pe_section_reader(exe)
    cta = struct.unpack("<i", at(throw - base + 12, 4))[0]
    count = struct.unpack("<i", at(cta, 4))[0]
    names = []
    for i in range(count):
        ct = struct.unpack("<i", at(cta + 4 + 4 * i, 4))[0]
        ptype = struct.unpack("<i", at(ct + 4, 4))[0]
        raw = at(ptype + 16, 256).split(b"\0")[0].decode("latin-1")
        names.append(raw.removeprefix(".?AV").removeprefix(".?AU").rstrip("@"))
    return names


def memory_status():
    """Free physical RAM and free commit (what an allocation can still get), GB."""
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [
            (n, ctypes.c_ulonglong) for n in (
                "total_phys", "avail_phys", "total_commit", "avail_commit",
                "total_virtual", "avail_virtual", "avail_ext")]
    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(st)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        raise OSError("GlobalMemoryStatusEx failed")
    gb = 1 << 30
    return {"ram_free_gb": st.avail_phys / gb, "ram_total_gb": st.total_phys / gb,
            "commit_free_gb": st.avail_commit / gb, "commit_total_gb": st.total_commit / gb}


def top_committers(n=5):
    """The n process names holding the most private (committed) memory: [(name, GB)]."""
    import psutil
    by_name = {}
    for p in psutil.process_iter(["name", "memory_info"]):
        mi = p.info["memory_info"]
        if mi is not None:
            by_name[p.info["name"]] = by_name.get(p.info["name"], 0) + mi.private
    return sorted(((k, v / (1 << 30)) for k, v in by_name.items()),
                  key=lambda kv: -kv[1])[:n]


def wer_crashes_since(seconds_ago, exe="Warhammer3.exe"):
    """Windows 'Application Error' (event 1000) records for exe in the window:
    [(time, code, offset)]. These exist even when the game writes no dump (a
    fail-fast abort, 0xc0000409, bypasses the game's own dump writer -- the
    21:12 smoke round left only this)."""
    import subprocess
    import xml.etree.ElementTree as ET
    q = (f"*[System[(EventID=1000) and TimeCreated[timediff(@SystemTime) <= "
         f"{int(seconds_ago * 1000)}]]]")
    out = subprocess.run(["wevtutil", "qe", "Application", f"/q:{q}", "/f:xml",
                          "/rd:true", "/c:20"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=True).stdout
    ns = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}
    hits = []
    for ev in ET.fromstring(f"<r>{out}</r>").findall("e:Event", ns):
        data = [d.text or "" for d in ev.findall("e:EventData/e:Data", ns)]
        if data and data[0].lower() == exe.lower():
            when = ev.find("e:System/e:TimeCreated", ns).get("SystemTime")
            hits.append((when, data[6], data[7]))
    return hits


def postmortem(since_epoch):
    """Why did the game die after `since_epoch`? -> (verdict, report lines).

    [PROBE-W1 2026-10-15] Project rule (ARCHITECTURE §A14.10): a failed run is
    diagnosed by probe code and reported as a root cause, never re-run to see
    whether it changes. Evidence, strongest first: a game dump newer than the
    launch (decoded, C++ throws named), Windows' own crash record, and the
    memory state now. The verdict is whatever the evidence names -- the
    20:57/21:12 smoke failures read as "out of memory", not as a mod defect.
    """
    lines = []
    mem = memory_status()
    lines.append("memory now: RAM free {ram_free_gb:.1f}/{ram_total_gb:.1f} GB, "
                 "commit free {commit_free_gb:.1f}/{commit_total_gb:.1f} GB".format(**mem))
    lines.append("largest holders: " + ", ".join(
        f"{k} {v:.1f} GB" for k, v in top_committers()))
    wer = wer_crashes_since(time.time() - since_epoch + 5)
    lines.extend(f"Windows crash record: {w} code=0x{c} offset=0x{o}" for w, c, o in wer)
    dumps = [p for p in (newest_dumps(3) if os.path.isdir(CRASH_DIR) else [])
             if os.path.getmtime(p) >= since_epoch]
    verdict = None
    for p in dumps:
        md = Minidump(p)
        exc = md.exception()
        if exc is None:
            lines.append(f"game dump {os.path.basename(p)}: no exception stream")
            continue
        types = cxx_exception_types(md, exc)
        lines.append(f"game dump {os.path.basename(p)}: code 0x{exc['code']:08X}"
                     + (f" C++ {types}" if types else ""))
        if any(t.startswith("bad_alloc") for t in types):
            verdict = ("out of memory: the game threw std::bad_alloc "
                       f"(commit free now {mem['commit_free_gb']:.1f} GB)")
        elif verdict is None:
            mod, off = md.module_for(exc["regs"]["rip"])
            verdict = f"crash 0x{exc['code']:08X} at {mod}+0x{off or 0:X}"
    if verdict is None and wer:
        verdict = f"crash 0x{wer[0][1]} at Warhammer3.exe+0x{wer[0][2]} (no game dump)"
    if verdict is None:
        verdict = "no crash record: the game exited without a dump or a Windows crash event"
    return verdict, lines


def newest_dumps(n):
    dumps = sorted((os.path.getmtime(os.path.join(CRASH_DIR, f)),
                    os.path.join(CRASH_DIR, f))
                   for f in os.listdir(CRASH_DIR) if f.endswith(".mdmp"))
    return [p for _, p in dumps[-n:]]


def watch():
    print(f"[crash_watch] watching {CRASH_DIR} (Ctrl-C to stop)")
    out_dir = os.path.join(CRASH_DIR, "crash_watch_reports")
    os.makedirs(out_dir, exist_ok=True)
    seen = set(os.listdir(CRASH_DIR))
    while True:
        time.sleep(2)
        now = set(os.listdir(CRASH_DIR))
        for f in sorted(now - seen):
            if not f.endswith(".mdmp"):
                continue
            p = os.path.join(CRASH_DIR, f)
            last = -1
            while os.path.getsize(p) != last:  # wait for the writer to finish
                last = os.path.getsize(p)
                time.sleep(1)
            report = [analyze(p), "", "## companion evidence"]
            bad = os.path.join(CRASH_DIR, "bad_mods_report.txt")
            report.append("bad_mods_report.txt: " + (
                open(bad, encoding="utf-8", errors="replace").read().strip()
                if os.path.isfile(bad) else "ABSENT (hard CTD, not DB rejection)"))
            modlog = os.path.join(LOGS_DIR, "modified.log")
            if os.path.isfile(modlog):
                report.append("modified.log: " + " / ".join(
                    open(modlog, encoding="utf-8", errors="replace").read().split("\n")))
            text = "\n".join(report)
            out = os.path.join(out_dir, f.replace(".mdmp", ".crash_watch.md"))
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(text)
            print("\n" + "=" * 70)
            print(text)
            print(f"[crash_watch] report -> {out}")
        seen = now


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("analyze", "latest", "watch", "postmortem"):
        print(__doc__)
        return 1
    if sys.argv[1] == "postmortem":
        minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 30
        verdict, lines = postmortem(time.time() - 60 * minutes)
        print("\n".join(lines))
        print(f"ROOT CAUSE: {verdict}")
        return 0
    if sys.argv[1] == "watch":
        watch()
        return 0
    if sys.argv[1] == "latest":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
        paths = newest_dumps(n)
    else:
        paths = sys.argv[2:]
    for p in paths:
        print(analyze(p))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

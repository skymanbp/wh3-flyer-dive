"""Game process helpers shared by the in-game test drivers. [AIR-DIVE-AUTOTEST 2026-11-10]

Moved verbatim out of auto_test.py so a driver that only launches the game
(pipelines/air_dive_autotest.py) does not have to import auto_test, whose
imports pull in the whole build and catalog chain. auto_test re-imports both
names as its own module globals, so its callers and its tests'
mock.patch.object(auto_test, ...) are unchanged.
/ 游戏进程辅助：从 auto_test.py 原样搬出，供只需启动游戏的测试驱动共用。
"""
import os
import subprocess
import time


def ensure_steam(wait=180):
    """None once Steam is running with an account signed in, else why not.

    [STEAMCHK 2026-11-05] Launched without Steam, the game stops at "Unable to
    initialize SteamAPI" and writes nothing (batch 1: 82 minutes, 0 phases).
    Steam records the signed-in account in HKCU ActiveProcess\\ActiveUser
    (0 = nobody), so that is the probe; Steam is started silently when it is
    0, and the run is refused if no one is signed in within `wait` seconds.
    / 没开 Steam 游戏会停在报错框；以注册表里的登录账号为准，没有就静默启动
      Steam 并等登录，等不到就拒跑。
    """
    if os.name != "nt":
        return None
    import winreg

    def _value(path, name):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                return winreg.QueryValueEx(key, name)[0]
        except OSError:
            return None
    active = r"Software\Valve\Steam\ActiveProcess"
    if _value(active, "ActiveUser"):
        return None
    steam_exe = _value(r"Software\Valve\Steam", "SteamExe")
    if not steam_exe:
        return "Steam is not installed for this user (no SteamExe in the registry)"
    print(f"[PREFLIGHT] Steam not signed in; starting {steam_exe} -silent")
    subprocess.Popen([steam_exe, "-silent"])
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(5)
        if _value(active, "ActiveUser"):
            print("[PREFLIGHT] Steam signed in")
            return None
    return f"Steam started but no account signed in within {wait}s"


def game_error_dialog(process_name="Warhammer3.exe"):
    """Text of a visible error dialog the game is showing, or None.

    [AUTOSTART-W1 2026-10-13] When the engine rejects a mod's database it
    shows a modal "Crash report" box (Win32 dialog class #32770) and WAITS;
    no minidump is written and the process stays alive, so the monitor below
    used to sit until its timeout while the game was already dead. The box
    text names the first invalid record, which is the diagnosis.
    / 引擎拒绝数据库时弹出模态框并停住，不写转储；读出框里的文字即诊断。
    """
    if os.name != "nt":
        return None
    import ctypes
    import ctypes.wintypes as wt
    user32 = ctypes.windll.user32
    try:
        listing = subprocess.run(["tasklist.exe", "/fo", "csv", "/nh"],
                                 capture_output=True, text=True, timeout=15).stdout
    except subprocess.TimeoutExpired:
        return None   # a stalled probe says nothing about the game (see below)
    pids = {int(row.split('","')[1]) for row in listing.splitlines()
            if row.lower().startswith('"' + process_name.lower() + '"')}
    if not pids:
        return None
    found = []
    callback = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def _text(hwnd):
        buf = ctypes.create_unicode_buffer(4096)
        user32.GetWindowTextW(hwnd, buf, 4096)
        return buf.value

    def _class(hwnd):
        buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, buf, 64)
        return buf.value

    # [STEAMCHK 2026-11-05] Not only class #32770: without Steam the game shows
    # its own "CustomerMessageDialog1" window ("Unable to initialize SteamAPI")
    # and waits forever; batch 1 sat 82 minutes on it as a plain timeout. Any
    # visible top-level window of the game carrying Static text is a dialog;
    # the game's render window has no Static children.
    # / 不只认标准对话框：没开 Steam 时游戏弹的是自定义类窗口。带文字控件的可见
    #   顶层窗口即对话框，游戏主窗口没有这种控件。
    def _top(hwnd, _):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd):
            texts = []

            def _child(child, _):
                if _class(child) == "Static" and _text(child).strip():
                    texts.append(_text(child).strip())
                return True
            user32.EnumChildWindows(hwnd, callback(_child), 0)
            if texts or _class(hwnd) == "#32770":
                found.extend([_text(hwnd)] + texts)
        return True

    user32.EnumWindows(callback(_top), 0)
    return "\n".join(found) if found else None


# --------------------------------------------------------------- process
class ProcessProbeStalled(RuntimeError):
    """The process table could not be read: the game's state is unknown,
    not 'gone'."""


def game_pids():
    # [AIR-DIVE-W11 2026-11-11] tasklist.exe stalled past 30 s three times at
    # 100 % CPU (runs d25a_2, rx_2: TimeoutExpired killed the driver
    # mid-battle; lc_3: 3 x 30 s). Read the process table in-process with the
    # Toolhelp snapshot API instead (no child process, answers in
    # milliseconds). A snapshot that cannot be taken raises
    # ProcessProbeStalled so each caller decides what "unknown" means --
    # never read as "not running".
    import ctypes
    import ctypes.wintypes as wt

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD),
                    ("th32ProcessID", wt.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                    ("th32ParentProcessID", wt.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    snap = k32.CreateToolhelp32Snapshot(0x00000002, 0)   # TH32CS_SNAPPROCESS
    if snap in (None, wt.HANDLE(-1).value):
        raise ProcessProbeStalled(
            f"CreateToolhelp32Snapshot failed (error {ctypes.get_last_error()})")
    pids = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == "warhammer3.exe":
                pids.append(int(entry.th32ProcessID))
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return pids


class OwnGame:
    """The Warhammer3 process(es) THIS harness launched, and only those.

    [AIR-DIVE-W12 2026-11-11] A game the harness did not start is the
    user's: it must never be closed or re-prioritised (coordinator
    2026-11-11; the user's own session was running beside a test lane). The
    old ``kill_game`` / ``lower_priority`` acted on every process named
    Warhammer3. Create this right BEFORE the launch (the caller has already
    refused to launch while any game runs); the first processes seen after
    it are ours and the set is frozen there, so a game the user starts later
    is never adopted. A process-table stall propagates
    (:class:`ProcessProbeStalled`); callers decide what unknown means.
    """

    def __init__(self):
        self.before = set(game_pids())
        self.pids = set()

    def alive(self):
        current = set(game_pids())
        if not self.pids:
            self.pids = current - self.before
        return bool(self.pids & current)

    def _each(self, command):
        for pid in sorted(self.pids):
            subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                            command.replace("{pid}", str(pid))],
                           capture_output=True)  # replace, not str.format: the PowerShell body has braces

    def kill(self):
        """Close our processes. A caller that never polled :meth:`alive`
        adopts here; a table that cannot be read closes nothing (unknown is
        never a licence to close a process)."""
        if not self.pids:
            try:
                self.alive()
            except ProcessProbeStalled:
                return
        self._each("Stop-Process -Id {pid} -Force -EA SilentlyContinue")

    def lower_priority(self):
        self._each("Get-Process -Id {pid} -EA SilentlyContinue | "
                   "ForEach-Object { $_.PriorityClass = 'BelowNormal' }")

    def _own_windows(self):
        """Visible, unowned top-level windows of our processes that are not dialogs (Static children)."""
        import ctypes
        import ctypes.wintypes as wt
        user32 = ctypes.windll.user32
        callback = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        hits = []

        def _has_static(hwnd):
            found = []

            def _child(child, _):
                buf = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(child, buf, 64)
                if buf.value == "Static":
                    found.append(child)
                return True
            user32.EnumChildWindows(hwnd, callback(_child), 0)
            return bool(found)

        def _top(hwnd, _):
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if (pid.value in self.pids and user32.IsWindowVisible(hwnd)
                    and not user32.GetWindow(hwnd, 4) and not _has_static(hwnd)):   # 4 = GW_OWNER
                hits.append(hwnd)
            return True
        user32.EnumWindows(callback(_top), 0)
        return hits

    def keep_behind(self, previous):
        """[AIR-DIVE-BRACE-W1 2026-11-15] The other background mode: the game window stays restored (a
        minimised game freezes its battle -- probe MWMSA1_g1: Lua timers ran, no unit moved after its
        order) but is pushed to the bottom of the z-order without activation, and when it has taken the
        foreground the window that had it before the launch (``previous``, a HWND) is asked to take it
        back. A window found minimised (a fullscreen game minimises itself when it loses the foreground,
        and a minimised game freezes) is restored without activation first. Returns (windows sent behind,
        the game held the foreground, foreground handed back, windows restored from minimised) for this
        call -- the second and fourth are the probes for focus theft and for a frozen battle.

        Measured 2026-11-15 (air-dive-brace-w1_scratch/window_probe.txt): the game held the foreground on one
        0.25 s tick per launch, then gave it back; 45 of 48 battles matched normal runs, but 3 froze (orders
        never executed, 0 restores from minimised logged -- probably the fullscreen game pausing while it is
        fully covered) against 0 of 464 normal runs. So this is not used for result-bearing runs."""
        if os.name != "nt" or not self.pids:
            return 0, False, False, 0
        import ctypes
        user32 = ctypes.windll.user32
        HWND_BOTTOM, flags = 1, 0x0001 | 0x0002 | 0x0010        # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
        mine = self._own_windows()
        restored = 0
        for hwnd in mine:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 4)                      # SW_SHOWNOACTIVATE
                restored += 1
            user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, flags)
        back = False
        held = user32.GetForegroundWindow() in mine
        if held and previous and user32.IsWindow(previous):
            back = bool(user32.SetForegroundWindow(previous))
        return len(mine), held, back, restored

    def wait_gone(self, seconds):
        """Wait until none of our processes is in the table (a stalled
        probe counts as not gone); returns True when they left in time."""
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                if not (self.pids & set(game_pids())):
                    return True
            except ProcessProbeStalled:
                pass
            time.sleep(1)
        return False


def running_game_refusal():
    """None when no Warhammer3 runs, else why a driver must not launch (or
    touch the game folder): a running game it did not start is the user's.
    A process table that cannot be read is a refusal too."""
    try:
        pids = game_pids()
    except ProcessProbeStalled as exc:
        return f"cannot tell whether Warhammer3.exe is running ({exc})"
    if pids:
        return (f"Warhammer3.exe is already running (pid {', '.join(map(str, pids))}; "
                "the user may be playing) -- not launching, not closing it")
    return None

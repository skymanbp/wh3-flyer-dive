#!/usr/bin/env python3
"""Keep the stand-alone flyer mod repository in step with the main repository.

[FLYER-REPO 2026-11-16] User: put the flyer mod (Workshop 3840651516,
``ld_air_dive.pack``) in its own directory and its own GitHub repository, and
link it to the main mod repository by code so that every change stays in sync.

The two repositories carry the files listed in
``mod/tools/data/flyer_repo_manifest.json`` at the SAME relative paths. This
script is itself one of those files, so both repositories run the identical
copy. It works on COMMITTED content only:

* what is compared is the git blob (the bytes the repository stores, after
  git's line-ending normalisation), never the checked-out file, so the main
  repository's ``core.autocrlf=true`` cannot make equal files look different;
  a copied file is staged and then re-checked-out by git, and the staged blob
  must equal the source blob or the whole sync is undone and refused;
* the flyer repository records, in ``.sync/state.json``, the blob of every
  shared path at the last sync. A path changed on one side since then is
  copied to the other; a path changed on BOTH sides is a conflict and the sync
  refuses without writing anything; deletions (and so renames, which are a
  delete plus an add) propagate the same way;
* the target's shared paths must have no uncommitted changes, and the target
  must not be in the middle of a merge, rebase or cherry-pick.

Commands (run from either repository):

    status   what differs, per path and direction
    check    exit 1 when the two repositories' shared paths differ or either
             working tree has uncommitted changes in them
    push     main -> flyer, then commit in the flyer repository
    pull     flyer -> main, then commit in the main repository (the main
             repository's commit-msg hook still runs: the commit carries the
             source commit's ``Serves:`` trailer, or the manifest's default)
    init     create the flyer repository next to the main one (first time)
    hook     called by the post-commit / post-merge hooks of both repositories

Where the other repository is: ``LD_FLYER_REPO`` / ``LD_MAIN_REPO`` when set,
else the sibling directory of the main repository's primary checkout (found
through ``git rev-parse --git-common-dir``, so a lane worktree still finds it),
named by ``flyer_dir_name`` / ``main_dir_name`` in the manifest.

Only commits on a branch listed in ``sync_branches`` are synced, and only into
a checkout on such a branch (``LD_FLYER_SYNC_BRANCHES``, comma-separated or
``*``, overrides the list; ``LD_FLYER_SYNC=0`` turns the hook off). Nothing is
ever pushed to a remote. A commit that already carries a ``Synced-From:``
trailer is not synced back, and a sync between two equal sides writes nothing,
so the two hooks cannot ping-pong.
/ 主仓库与飞兽独立仓库按清单同步：比的是 git 存的内容；两边都改过同一文件即拒绝；
  只同步提交过的内容；不推远端。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

MANIFEST_REL = "mod/tools/data/flyer_repo_manifest.json"
STATE_REL = ".sync/state.json"
TRAILER = "Synced-From"
TAG = "[flyer-sync]"


class Refused(Exception):
    """A sync that must not happen; the message says why."""


# --------------------------------------------------------------------- git

def _env():
    # Hooks run with GIT_DIR / GIT_INDEX_FILE / GIT_WORK_TREE of the repository
    # that fired them; inherited, they would point every git call at that
    # repository even when the call is meant for the other one.
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(repo, *args, check=True, env=None, data=None):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, input=data,
                       env={**_env(), **(env or {})})
    if check and p.returncode != 0:
        raise Refused(f"git {' '.join(args[:3])} in {repo} failed: "
                      f"{p.stderr.decode('utf-8', 'replace').strip()}")
    return p


def git_text(repo, *args, **kw):
    return git(repo, *args, **kw).stdout.decode("utf-8", "replace").strip()


def toplevel(path):
    p = git(path, "rev-parse", "--show-toplevel", check=False)
    if p.returncode != 0:
        return None
    return Path(p.stdout.decode("utf-8").strip()).resolve()


def own_repo(path):
    """The repository rooted exactly at ``path``, or None (missing directory,
    not a repository, or a plain directory inside some other repository)."""
    if not Path(path).is_dir():
        return None
    root = toplevel(path)
    return root if root is not None and root == Path(path).resolve() else None


# ---------------------------------------------------------------- manifest

def parse_manifest(raw):
    m = json.loads(raw)
    if m.get("schema") != 1:
        raise Refused(f"{MANIFEST_REL}: unknown schema {m.get('schema')!r}")
    for key in ("paths", "flyer_only", "sync_branches"):
        if not isinstance(m.get(key), list) or not m[key]:
            raise Refused(f"{MANIFEST_REL}: '{key}' must be a non-empty list")
    for pat in m["paths"] + m["flyer_only"]:
        body = pat[:-3] if pat.endswith("/**") else pat
        if not body or "*" in body or "?" in body or body.startswith("/") or "\\" in pat:
            raise Refused(f"{MANIFEST_REL}: entry {pat!r} must be an exact "
                          "repository path or '<dir>/**'")
    for pat in m["paths"]:
        if matches(pat.removesuffix("/**"), m["flyer_only"]):
            raise Refused(f"{MANIFEST_REL}: shared entry {pat!r} overlaps flyer_only")
    return m


def matches(path, patterns):
    for pat in patterns:
        if pat.endswith("/**"):
            if path.startswith(pat[:-2]):
                return True
        elif path == pat:
            return True
    return False


def head_blob(repo, rel):
    p = git(repo, "cat-file", "blob", f"HEAD:{rel}", check=False)
    return p.stdout if p.returncode == 0 else None


# ------------------------------------------------------------------ repos

class Side:
    def __init__(self, name, root):
        self.name, self.root = name, Path(root)

    def head(self):
        return git_text(self.root, "rev-parse", "HEAD")

    def branch(self):
        return git_text(self.root, "symbolic-ref", "--short", "-q", "HEAD", check=False)

    def tree(self, patterns):
        """{path: "mode sha"} of HEAD's blobs under the shared patterns."""
        specs = [p.removesuffix("/**") for p in patterns]
        out = git(self.root, "ls-tree", "-r", "-z", "--full-tree", "HEAD", "--", *specs).stdout
        tree = {}
        for rec in out.split(b"\0"):
            if not rec:
                continue
            meta, path = rec.decode("utf-8").split("\t", 1)
            mode, kind, sha = meta.split()
            if kind == "blob" and matches(path, patterns):
                tree[path] = f"{mode} {sha}"
        return tree

    def dirty(self, patterns):
        specs = [":(top,literal)" + p.removesuffix("/**") for p in patterns]
        out = git(self.root, "status", "--porcelain=v1", "-z", "-uall", "--", *specs).stdout
        return sorted({rec[3:].decode("utf-8") for rec in out.split(b"\0")
                       if len(rec) > 3 and rec[2:3] == b" "})

    def busy(self, finished_merge=False):
        """The operation in progress, if any. ``finished_merge``: called from
        post-merge, where git still holds MERGE_HEAD of the merge it has just
        committed (probe 2026-11-16: MERGE_HEAD and MERGE_MSG present, HEAD
        already the merge commit) and removes it after the hook."""
        names = ["rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD"]
        if not finished_merge:
            names.insert(0, "MERGE_HEAD")
        for name in names:
            if Path(git_text(self.root, "rev-parse", "--path-format=absolute",
                             "--git-path", name)).exists():
                return name
        return None

    def message(self, rev="HEAD"):
        return git(self.root, "log", "-1", "--format=%B", rev).stdout.decode("utf-8", "replace")

    def author(self, rev="HEAD"):
        return git_text(self.root, "log", "-1", "--format=%an <%ae>", rev)


def primary_checkout(root):
    common = Path(git_text(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    return common.parent if common.name == ".git" else root


def locate(start):
    """(main Side or None, flyer Side or None, manifest, which side we are in)."""
    root = toplevel(start)
    if root is None:
        raise Refused(f"{start} is not inside a git repository")
    raw = head_blob(root, MANIFEST_REL)
    if raw is None:
        disk = root / MANIFEST_REL
        if not disk.is_file():
            raise Refused(f"{root} has no {MANIFEST_REL}")
        raw = disk.read_bytes()
    manifest = parse_manifest(raw)
    if (root / STATE_REL).is_file() or head_blob(root, STATE_REL) is not None:
        other = os.environ.get("LD_MAIN_REPO") or str(root.parent / manifest["main_dir_name"])
        main_root = own_repo(other)
        main = Side(manifest["main_name"], main_root) if main_root else None
        return main, Side(manifest["flyer_name"], root), manifest, "flyer"
    other = os.environ.get("LD_FLYER_REPO") or str(
        primary_checkout(root).parent / manifest["flyer_dir_name"])
    flyer_root = own_repo(other)
    if flyer_root == root:
        flyer_root = None
    flyer = Side(manifest["flyer_name"], flyer_root) if flyer_root else None
    return Side(manifest["main_name"], root), flyer, manifest, "main"


def sync_branches(manifest):
    env = os.environ.get("LD_FLYER_SYNC_BRANCHES")
    if env:
        return [b.strip() for b in env.split(",") if b.strip()]
    return manifest["sync_branches"]


def branch_ok(side, manifest):
    allowed = sync_branches(manifest)
    return "*" in allowed or side.branch() in allowed


def shared_patterns(main, flyer):
    """Union of both committed manifests' shared entries, so a path added to
    the manifest on one side is already managed when that side syncs."""
    pats = []
    for side in (main, flyer):
        raw = head_blob(side.root, MANIFEST_REL)
        if raw is not None:
            pats += parse_manifest(raw)["paths"]
    if not pats:
        raise Refused(f"neither repository has {MANIFEST_REL} committed")
    return sorted(set(pats))


def read_state(flyer):
    raw = head_blob(flyer.root, STATE_REL)
    if raw is None:
        return {"schema": 1, "paths": {}}
    state = json.loads(raw)
    if state.get("schema") != 1 or not isinstance(state.get("paths"), dict):
        raise Refused(f"{flyer.root / STATE_REL}: unreadable state")
    return state


def state_bytes(paths, source):
    doc = {"schema": 1, "about": "blob of every shared path at the last sync "
           "(mod/tools/sync_flyer_repo.py); do not edit by hand",
           "last_sync_source": source, "paths": dict(sorted(paths.items()))}
    return (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


# ------------------------------------------------------------------- plan

def plan(main, flyer, patterns):
    """Per path: in_sync / to_flyer / to_main / conflict, against the state."""
    m, f = main.tree(patterns), flyer.tree(patterns)
    base = {p: v for p, v in read_state(flyer)["paths"].items() if matches(p, patterns)}
    rows = []
    for path in sorted(set(m) | set(f) | set(base)):
        mv, fv, bv = m.get(path), f.get(path), base.get(path)
        if mv == fv:
            kind = "in_sync"
        elif fv == bv:
            kind = "to_flyer"
        elif mv == bv:
            kind = "to_main"
        else:
            kind = "conflict"
        rows.append((path, kind, mv, fv, bv))
    return rows


def describe(value):
    return "absent" if value is None else value.split()[1][:10]


# ------------------------------------------------------------------- apply

def restore(dst, paths, created=()):
    """Put ``paths`` back to dst's HEAD (index and tree), one path at a time
    (a path HEAD lacks would make a multi-path checkout fail as a whole), and
    remove files this sync created."""
    for path in paths:
        git(dst.root, "reset", "-q", "HEAD", "--", path, check=False)
        git(dst.root, "checkout", "HEAD", "--", path, check=False)
    for target in created:
        rel = Path(target).relative_to(dst.root).as_posix()
        if Path(target).exists() and git(dst.root, "cat-file", "-e", f"HEAD:{rel}",
                                         check=False).returncode != 0:
            Path(target).unlink()


def apply(src, dst, changes):
    """Copy/delete ``changes`` [(path, src_value)] into dst's index and tree.
    Every staged blob must equal the source blob, else this raises (callers
    undo with ``restore``)."""
    for path, value in changes:
        target = dst.root / path
        if value is None:
            if git(dst.root, "ls-files", "--error-unmatch", "--", path, check=False).returncode == 0:
                git(dst.root, "rm", "-q", "--", path)
            continue
        mode, sha = value.split()
        data = git(src.root, "cat-file", "blob", sha).stdout
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        git(dst.root, "add", "--", path)
        if mode == "100755":
            git(dst.root, "update-index", "--chmod=+x", "--", path)
    copied = [p for p, v in changes if v is not None]
    if not copied:
        return
    staged = {}
    out = git(dst.root, "ls-files", "-s", "-z", "--", *copied).stdout
    for rec in out.split(b"\0"):
        if rec:
            meta, p = rec.decode("utf-8").split("\t", 1)
            mode, sha, _stage = meta.split()
            staged[p] = f"{mode} {sha}"
    bad = [p for p, v in changes if v is not None and staged.get(p) != v]
    if bad:
        raise Refused(f"{dst.name}: staging changed the bytes of {bad[:3]} "
                      "(line-ending attributes differ between the repositories?)")
    git(dst.root, "checkout", "--", *copied)   # git writes its own checkout form back


def commit_main(side, paths, message, author):
    """Commit exactly ``paths`` in the main repository with the porcelain, so
    its commit-msg hook judges the commit; ``--only`` leaves anything else a
    developer has staged out of it."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n",
                                     suffix=".txt", delete=False) as fh:
        fh.write(message)
        name = fh.name
    try:
        p = git(side.root, "commit", "-q", "--only", "-F", name, f"--author={author}",
                "--", *paths, check=False)
    finally:
        os.unlink(name)
    if p.returncode != 0:
        raise Refused(f"commit in {side.name} refused: "
                      f"{(p.stderr + p.stdout).decode('utf-8', 'replace').strip()}")
    return side.head()


def commit_flyer(side, paths, message, author):
    """Commit exactly ``paths`` (already staged) on top of the flyer HEAD with
    plumbing: a temporary index built from HEAD plus those entries, so other
    staged files stay out, a leftover MERGE_HEAD (post-merge) cannot turn it
    into a merge commit, and the flyer hooks do not fire again."""
    index = Path(git_text(side.root, "rev-parse", "--path-format=absolute",
                          "--git-path", "flyer-sync-index"))
    env = {"GIT_INDEX_FILE": str(index)}
    old = side.head()
    try:
        git(side.root, "read-tree", "HEAD", env=env)
        staged = git(side.root, "ls-files", "-s", "-z", "--", *paths).stdout
        present = set()
        for rec in staged.split(b"\0"):
            if rec:
                meta, p = rec.decode("utf-8").split("\t", 1)
                present.add(p)
                git(side.root, "update-index", "--index-info", env=env,
                    data=(meta + "\t" + p + "\n").encode("utf-8"))
        for p in paths:
            if p not in present:
                git(side.root, "update-index", "--force-remove", "--", p, env=env)
        tree = git_text(side.root, "write-tree", env=env)
        name, _, email = author.rpartition(" <")
        p = git(side.root, "commit-tree", tree, "-p", old, data=message.encode("utf-8"),
                env={"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email.rstrip(">")})
        sha = p.stdout.decode("utf-8").strip()
        subject = message.splitlines()[0] if message else "sync"
        git(side.root, "update-ref", "-m", f"commit (flyer-sync): {subject}", "HEAD", sha, old)
    finally:
        index.unlink(missing_ok=True)
    return sha


def synced_message(src, dst_is_main, manifest):
    text = src.message().rstrip("\n")
    if not dst_is_main:
        # the main repository's plan-step ids mean nothing in the public repository
        text = re.sub(r"(?im)^serves:.*\n?", "", text).rstrip("\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
    lines = text.splitlines()
    trailers = []
    if dst_is_main and not re.search(r"(?im)^serves:", text):
        trailers.append(f"Serves: {manifest['main_serves_default']}")
    trailers.append(f"{TRAILER}: {src.name}@{src.head()}")
    sep = "\n" if lines and re.match(r"^[A-Za-z-]+: ", lines[-1]) else "\n\n"
    return text + sep + "\n".join(trailers) + "\n"


def _write_state(flyer, paths, source):
    target = flyer.root / STATE_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(state_bytes(paths, source))
    git(flyer.root, "add", "--", STATE_REL)


def run_sync(main, flyer, manifest, direction, quiet=False, finished_merge=False):
    src, dst = (main, flyer) if direction == "push" else (flyer, main)
    patterns = shared_patterns(main, flyer)
    if not branch_ok(dst, manifest):
        raise Refused(f"{dst.name} is on branch '{dst.branch()}', not one of "
                      f"{sync_branches(manifest)}; nothing written")
    for side in (dst, flyer):
        busy = side.busy(finished_merge=finished_merge and side is src)
        if busy:
            raise Refused(f"{side.name} is in the middle of an operation ({busy}); nothing written")
    rows = plan(main, flyer, patterns)
    conflicts = [r for r in rows if r[1] == "conflict"]
    if conflicts:
        lines = "\n".join(f"  {p}: main {describe(mv)} / flyer {describe(fv)} / last sync {describe(bv)}"
                          for p, _k, mv, fv, bv in conflicts)
        raise Refused(f"{len(conflicts)} path(s) changed in BOTH repositories since the last "
                      f"sync; make them equal by hand and commit, then sync again:\n{lines}")
    want = "to_flyer" if direction == "push" else "to_main"
    changes = [(p, (mv if direction == "push" else fv)) for p, k, mv, fv, _b in rows if k == want]
    pending = [p for p, k, *_ in rows if k not in ("in_sync", want)]
    if changes:
        dirty = dst.dirty(patterns)
        if dirty:
            raise Refused(f"{dst.name} has uncommitted changes in shared paths "
                          f"({len(dirty)}, e.g. {dirty[0]}); commit or discard them first")
    old_state = read_state(flyer)["paths"]
    new_state = {}
    for p, k, mv, fv, _b in rows:
        if k == "in_sync":
            value = mv
        elif k == want:
            value = mv if direction == "push" else fv
        else:
            value = old_state.get(p)     # still waiting for the other direction
        if value is not None:
            new_state[p] = value
    source = f"{src.name}@{src.head()}"
    created = [dst.root / p for p, v in changes if v is not None and not (dst.root / p).exists()]
    if new_state != old_state and flyer.dirty([STATE_REL]):
        raise Refused(f"{flyer.root / STATE_REL} has uncommitted changes")

    if direction == "push":
        if not changes and new_state == old_state:
            if not quiet:
                print(f"{TAG} {flyer.name} already matches {main.name}"
                      + (f" ({len(pending)} path(s) wait for a pull)" if pending else ""))
            return None
        try:
            if changes:
                apply(src, dst, changes)
            _write_state(flyer, new_state, source)
            msg = (synced_message(main, False, manifest) if changes
                   else f"sync state from {source}\n\n{TRAILER}: {source}\n")
            sha = commit_flyer(flyer, [p for p, _v in changes] + [STATE_REL], msg, main.author())
        except BaseException:
            restore(flyer, [p for p, _v in changes] + [STATE_REL], created)
            raise
        print(f"{TAG} {len(changes)} file(s) {main.name} -> {flyer.name}, committed {sha[:10]}")
        return sha

    sha = None
    if changes:
        try:
            apply(src, dst, changes)
            sha = commit_main(main, [p for p, _v in changes],
                              synced_message(flyer, True, manifest), flyer.author())
        except BaseException:
            restore(main, [p for p, _v in changes], created)
            raise
        print(f"{TAG} {len(changes)} file(s) {flyer.name} -> {main.name}, committed {sha[:10]}")
    if new_state != old_state:
        recorded = f"{main.name}@{main.head()}"
        try:
            _write_state(flyer, new_state, recorded)
            commit_flyer(flyer, [STATE_REL],
                         f"sync state after {source} -> {recorded}\n\n{TRAILER}: {recorded}\n",
                         flyer.author())
        except BaseException:
            restore(flyer, [STATE_REL])
            raise
    elif not changes and not quiet:
        print(f"{TAG} {main.name} already matches {flyer.name}"
              + (f" ({len(pending)} path(s) wait for a push)" if pending else ""))
    return sha


# ---------------------------------------------------------------- commands

def cmd_status(main, flyer, strict):
    patterns = shared_patterns(main, flyer)
    rows = plan(main, flyer, patterns)
    drift = [r for r in rows if r[1] != "in_sync"]
    dirty = [(s.name, d) for s in (main, flyer) for d in s.dirty(patterns)]
    print(f"{TAG} {main.name}: {main.root} (branch {main.branch()}, {main.head()[:10]})")
    print(f"{TAG} {flyer.name}: {flyer.root} (branch {flyer.branch()}, {flyer.head()[:10]})")
    print(f"{TAG} {len(rows)} shared path(s): {len(rows) - len(drift)} in sync, "
          f"{len(drift)} differ, {len(dirty)} uncommitted")
    for p, k, mv, fv, bv in drift:
        print(f"  {k:9} {p}  (main {describe(mv)}, flyer {describe(fv)}, last sync {describe(bv)})")
    for name, d in dirty:
        print(f"  uncommitted in {name}: {d}")
    present = {p for p, *_ in rows}
    for pat in patterns:
        if not pat.endswith("/**") and pat not in present:
            print(f"  manifest entry matches nothing in either repository: {pat}")
    return 1 if strict and (drift or dirty) else 0


GITATTRIBUTES = """\
# Same normalisation as the lore-disasters repository for the shared paths:
# the sync compares git blobs, so both repositories must store identical bytes.
* text=auto
*.lua text eol=lf
hooks/* text eol=lf
mod/assets/vendored_scripts/** -text
mod/assets/air_dive/** -text
*.pack binary
*.png binary
"""

GITIGNORE = """\
*.pack
__pycache__/
*.pyc
.cache/
.pytest_cache/
"""

HOOK_SHIM = """\
#!/bin/sh
# FLYER-REPO: sync shared files with the lore-disasters repository after @HOOK@.
# Logic: mod/tools/sync_flyer_repo.py (identical in both repositories).
root=$(git rev-parse --show-toplevel) || exit 0
[ -f "$root/mod/tools/sync_flyer_repo.py" ] || exit 0
if command -v python >/dev/null 2>&1; then PY=python
elif command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v py >/dev/null 2>&1; then PY="py -3"
else echo "[flyer-sync] no python on PATH; not synced" >&2; exit 0
fi
$PY -P "$root/mod/tools/sync_flyer_repo.py" hook @HOOK@ || true
exit 0
"""


def cmd_init(main, manifest, target):
    if target is None:
        target = os.environ.get("LD_FLYER_REPO") or (
            primary_checkout(main.root).parent / manifest["flyer_dir_name"])
    target = Path(target)
    if (target / ".git").exists():
        raise Refused(f"{target} is already a git repository")
    target.mkdir(parents=True, exist_ok=True)
    git(target, "init", "-q", "-b", "main")
    for key in ("user.name", "user.email"):
        value = git_text(main.root, "config", key, check=False)
        if not value:
            raise Refused(f"{main.name} has no {key} configured")
        git(target, "config", key, value)
    git(target, "config", "core.hooksPath", "hooks")
    git(target, "config", "core.autocrlf", "true")   # the main checkout's normalisation
    files = {
        ".gitattributes": GITATTRIBUTES,
        ".gitignore": GITIGNORE,
        "hooks/post-commit": HOOK_SHIM.replace("@HOOK@", "post-commit"),
        "hooks/post-merge": HOOK_SHIM.replace("@HOOK@", "post-merge"),
    }
    for rel, text in files.items():
        path = target / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
    git(target, "add", "--", *files)
    git(target, "update-index", "--chmod=+x", "--", "hooks/post-commit", "hooks/post-merge")
    flyer = Side(manifest["flyer_name"], own_repo(target))
    tree = main.tree(manifest["paths"])
    apply(main, flyer, sorted(tree.items()))
    _write_state(flyer, tree, f"{main.name}@{main.head()}")
    print(f"{TAG} initialised {flyer.root}: {len(tree)} shared file(s) staged and "
          "flyer-only files written; add README.md, review, then commit")
    return 0


def cmd_hook(start, hook):
    if os.environ.get("LD_FLYER_SYNC") == "0":
        return 0
    main, flyer, manifest, here = locate(start)
    side = main if here == "main" else flyer
    other = flyer if here == "main" else main
    if other is None:
        missing, var = (("flyer", "LD_FLYER_REPO") if here == "main" else ("main", "LD_MAIN_REPO"))
        print(f"{TAG} {missing} repository not found; not synced (set {var})")
        return 0
    if side.busy(finished_merge=hook == "post-merge") or not branch_ok(side, manifest):
        return 0
    if hook == "post-commit":
        if re.search(rf"(?m)^{TRAILER}:", side.message()):
            return 0                     # it came from the other repository
        args = ["diff-tree", "--no-commit-id", "--name-only", "-r", "-z"]
        if " " not in git_text(side.root, "rev-list", "--parents", "-n1", "HEAD"):
            args.append("--root")
        touched = [p for p in git(side.root, *args, "HEAD").stdout.decode("utf-8").split("\0") if p]
        patterns = shared_patterns(main, flyer)
        if not any(matches(p, patterns) for p in touched):
            return 0
    try:
        run_sync(main, flyer, manifest, "push" if here == "main" else "pull", quiet=True,
                 finished_merge=hook == "post-merge")
    except Refused as e:
        print(f"{TAG} not synced: {e}")
    return 0


def main_cli(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("status", "check", "push", "pull", "init", "hook"))
    ap.add_argument("hook_name", nargs="?", help="hook: post-commit | post-merge")
    ap.add_argument("--target", help="init: directory to create (default: the sibling directory)")
    args = ap.parse_args(argv)
    start = Path.cwd()
    try:
        if args.command == "hook":
            return cmd_hook(start, args.hook_name or "post-commit")
        main, flyer, manifest, here = locate(start)
        if args.command == "init":
            if here != "main":
                raise Refused("run init from the main repository")
            return cmd_init(main, manifest, args.target)
        if main is None or flyer is None:
            raise Refused("the other repository was not found "
                          "(set LD_FLYER_REPO in the main repository, LD_MAIN_REPO in the flyer one)")
        if args.command in ("status", "check"):
            return cmd_status(main, flyer, strict=args.command == "check")
        run_sync(main, flyer, manifest, args.command)
        return 0
    except Refused as e:
        print(f"{TAG} refused: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main_cli())

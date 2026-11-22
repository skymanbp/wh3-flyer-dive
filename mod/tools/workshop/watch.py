"""Poll the public Workshop comment feed of item 3840651516; print one line per new comment.

Read-only, public endpoint, every 10 minutes (Steam rate-limits faster polling).
State (D65: private data stays out of git): the owner's Steam id in creator.txt and the seen comment ids in seen.txt,
both in the repo's git-ignored .local/comments-watch/. First run prints the newest 5 and marks all as seen.
"""
import html
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".local", "comments-watch")
ITEM = "3840651516"
CREATOR = open(os.path.join(HERE, "creator.txt")).read().strip()
URL = f"https://steamcommunity.com/comment/PublishedFile_Public/render/{CREATOR}/{ITEM}/?start=0&count=30"
SEEN = os.path.join(HERE, "seen.txt")
INTERVAL = int(sys.argv[1]) if len(sys.argv) > 1 else 600


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8"))
    if not d.get("success"):
        raise RuntimeError("feed not successful")
    out = []
    h = d["comments_html"]
    for m in re.finditer(r'class="commentthread_comment [^"]*" id="comment_(\d+)"', h):
        cid = m.group(1)
        block = h[m.end():h.find('class="commentthread_comment ', m.end()) if 'class="commentthread_comment ' in h[m.end():] else len(h)]
        a = re.search(r'commentthread_author_link"[^>]*>\s*<bdi>(.*?)</bdi>', block, re.S)
        w = re.search(r'commentthread_comment_timestamp" title="([^"]*)"', block)
        t = re.search(r'id="comment_content_%s"[^>]*>(.*?)</div>' % cid, block, re.S)
        if not (a and w and t):
            raise RuntimeError(f"comment {cid}: author/time/text not found (page layout changed?)")
        author, when, text = a.group(1), w.group(1), t.group(1)
        text = html.unescape(re.sub(r"<br\s*/?>", " / ", text))
        text = re.sub(r"<[^>]+>", "", text)
        out.append((cid, html.unescape(re.sub(r"<[^>]+>", "", author)).strip(), when, re.sub(r"\s+", " ", text).strip()))
    return d.get("total_count"), out


def main():
    seen = set(open(SEEN).read().split()) if os.path.exists(SEEN) else None
    while True:
        try:
            total, comments = fetch()
            if not comments:
                print(f"WARN parse found 0 comments (total_count={total})", flush=True)
            if seen is None:
                seen = {c[0] for c in comments}
                for c in comments[:5]:
                    print(f"BASELINE {c[2]} | {c[1]}: {c[3][:300]}", flush=True)
            else:
                for c in reversed(comments):
                    if c[0] not in seen:
                        print(f"NEW {c[2]} | {c[1]}: {c[3][:400]}", flush=True)
                        seen.add(c[0])
            open(SEEN, "w").write("\n".join(sorted(seen)))
        except Exception as exc:  # noqa: BLE001  because a network hiccup must not end the watch; it is reported
            print(f"ERROR {type(exc).__name__}: {exc}", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()

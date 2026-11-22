"""Print the newest 30 public Workshop comments of item 3840651516 (read-only), oldest first; reuses watch.fetch()."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import watch  # noqa: E402 -- because the folder above is put on sys.path first

items = []
for start in (0, 30, 60):
    watch.URL = watch.URL.replace("start=0", f"start={start}") if start == 0 else watch.URL.rsplit("start=", 1)[0] + f"start={start}&count=30"
    total, page = watch.fetch()
    items += page
print("total", total)
for c in reversed(items):
    print(f"{c[2]} | {c[1]}: {c[3]}")

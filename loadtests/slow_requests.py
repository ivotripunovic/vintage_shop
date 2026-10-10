"""
Summarise request timings from the gunicorn access log.

Reads log lines on stdin, groups them by path (query string dropped, numeric
IDs collapsed to <id>), and prints count, median, p95 and max per path,
slowest first. On the server:

    journalctl -u vintage_shop --since "1 hour ago" -o cat \\
        | python loadtests/slow_requests.py
"""

import re
import statistics
import sys
from collections import defaultdict

LINE_RE = re.compile(
    r'"(?P<method>[A-Z]+) (?P<path>\S+) [^"]*" (?P<status>\d{3}) \S+ (?P<ms>\d+)ms'
)


def normalise(path):
    path = path.split("?", 1)[0]
    return re.sub(r"/\d+(?=/|$)", "/<id>", path)


def main():
    timings = defaultdict(list)
    errors = defaultdict(int)
    for line in sys.stdin:
        match = LINE_RE.search(line)
        if not match:
            continue
        key = f"{match['method']} {normalise(match['path'])}"
        timings[key].append(int(match["ms"]))
        if match["status"].startswith("5"):
            errors[key] += 1

    if not timings:
        sys.exit("No timed requests found. Is access_log_format deployed?")

    rows = []
    for key, values in timings.items():
        values.sort()
        p95 = values[min(len(values) - 1, int(len(values) * 0.95))]
        rows.append((p95, key, len(values), statistics.median(values), values[-1]))

    print(f"{'p95 ms':>7} {'median':>7} {'max':>7} {'count':>7} {'5xx':>5}  path")
    for p95, key, count, median, worst in sorted(rows, reverse=True):
        print(f"{p95:>7} {median:>7.0f} {worst:>7} {count:>7} {errors[key]:>5}  {key}")


if __name__ == "__main__":
    main()

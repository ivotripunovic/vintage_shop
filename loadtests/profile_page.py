"""
Profile how long one page takes to render, and where the time goes.

Renders the page in-process with Django's test client (no gunicorn, no
network), so the numbers are pure Django CPU time plus database queries.
Runs against a throwaway copy of db.sqlite3.

Usage:
    python loadtests/profile_page.py                    # coming-soon page
    python loadtests/profile_page.py --live             # real homepage
    python loadtests/profile_page.py --path /products/  # any page (implies --live)
    python loadtests/profile_page.py -n 500 --top 40 --sort tottime
"""

import argparse
import cProfile
import os
import pstats
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--live", action="store_true", help="COMING_SOON=False")
    parser.add_argument("--path", default="/", help="URL path to profile")
    parser.add_argument("-n", type=int, default=300, help="requests to profile")
    parser.add_argument("--top", type=int, default=30, help="functions to list")
    parser.add_argument(
        "--sort",
        default="cumulative",
        choices=["cumulative", "tottime", "ncalls"],
        help="cumulative = where time is spent incl. callees; "
        "tottime = time inside the function itself",
    )
    parser.add_argument(
        "--filter",
        default="",
        help="regex; only list functions whose file path matches, "
        "e.g. '^(?!.*venv)' for project code only",
    )
    return parser.parse_args()


def setup_django(args, tmp_dir):
    db_copy = Path(tmp_dir) / "profile.sqlite3"
    shutil.copy(ROOT / "db.sqlite3", db_copy)
    os.environ.update(
        DJANGO_SETTINGS_MODULE="config.settings",
        DEBUG="True",
        SQLITE_PATH=str(db_copy),
        COMING_SOON="False" if args.live or args.path != "/" else "True",
    )
    sys.path.insert(0, str(ROOT))

    import django

    django.setup()

    from django.core.management import call_command
    from django.test.utils import setup_test_environment

    call_command("migrate", verbosity=0)
    setup_test_environment()


def main():
    args = parse_args()
    with tempfile.TemporaryDirectory() as tmp_dir:
        setup_django(args, tmp_dir)

        from django.db import connection
        from django.test import Client
        from django.test.utils import CaptureQueriesContext

        client = Client()
        response = client.get(args.path)
        if response.status_code != 200:
            sys.exit(f"{args.path} returned {response.status_code}")

        # Warm up template and URL caches before measuring
        for _ in range(20):
            client.get(args.path)

        with CaptureQueriesContext(connection) as capture:
            client.get(args.path)
        # Copy now: captured_queries is read lazily from a log that Django
        # clears at the start of every request
        queries = list(capture.captured_queries)

        start = time.perf_counter()
        for _ in range(args.n):
            client.get(args.path)
        plain_ms = (time.perf_counter() - start) / args.n * 1000

        profiler = cProfile.Profile()
        profiler.enable()
        for _ in range(args.n):
            client.get(args.path)
        profiler.disable()

        mode = "coming-soon" if os.environ["COMING_SOON"] == "True" else "live"
        print(f"Page: {args.path} ({mode})")
        print(f"Time per request: {plain_ms:.2f} ms (without profiler overhead)")
        print(f"Max req/s on one core: ~{1000 / plain_ms:.0f}")
        print(f"DB queries per request: {len(queries)}")
        for query in queries:
            print(f"    {query['sql'][:120]}")
        print()

        stats = pstats.Stats(profiler).sort_stats(args.sort)
        restrictions = [args.filter, args.top] if args.filter else [args.top]
        stats.print_stats(*restrictions)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Wait for PostgreSQL to be ready before proceeding with pipeline stages.

This script polls a PostgreSQL database until it accepts connections,
with configurable timeout and retry interval. It's designed to be used
as a pipeline stage when the pipeline.sh script generates commands.

Usage:
    uv run python ingest/wait_for_postgres.py --database-url postgresql://...
    uv run python ingest/wait_for_postgres.py --database-url postgresql://... --timeout 120 --interval 5
"""

import argparse
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


def wait_for_postgres(database_url: str, timeout: int = 60, interval: int = 2) -> bool:
    """
    Wait for PostgreSQL to accept connections.

    Args:
        database_url: PostgreSQL connection URL
        timeout: Maximum time to wait in seconds
        interval: Time between connection attempts in seconds

    Returns:
        True if connection successful, False if timeout reached
    """
    engine = create_engine(database_url)
    start_time = time.time()
    attempt = 0

    print(f"Waiting for PostgreSQL at {database_url.split('@')[-1]}...")

    while time.time() - start_time < timeout:
        attempt += 1
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            elapsed = time.time() - start_time
            print(f"PostgreSQL is ready! (connected after {elapsed:.1f}s, {attempt} attempts)")
            engine.dispose()
            return True
        except OperationalError as e:
            elapsed = time.time() - start_time
            remaining = timeout - elapsed
            if remaining > 0:
                print(f"  Attempt {attempt}: Connection failed, retrying in {interval}s... ({remaining:.0f}s remaining)")
                time.sleep(interval)
            else:
                print(f"  Attempt {attempt}: Connection failed: {e}")

    engine.dispose()
    print(f"Timeout: PostgreSQL not ready after {timeout}s ({attempt} attempts)")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Wait for PostgreSQL to be ready",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Wait with defaults (60s timeout, 2s interval)
    uv run python ingest/wait_for_postgres.py --database-url postgresql://postgres:postgres@localhost:5432/medlit

    # Custom timeout and interval
    uv run python ingest/wait_for_postgres.py --database-url postgresql://... --timeout 120 --interval 5
        """,
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help="PostgreSQL connection URL (e.g., postgresql://user:pass@host:port/dbname)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Maximum time to wait in seconds (default: 60)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Time between connection attempts in seconds (default: 2)",
    )

    args = parser.parse_args()

    success = wait_for_postgres(
        database_url=args.database_url,
        timeout=args.timeout,
        interval=args.interval,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

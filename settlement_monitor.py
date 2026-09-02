"""Executable boundary for a scheduled settlement close."""

from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Callable

from infrai_errors import InfraiErrors


def settle_batch(batch_id: str) -> None:
    """Stand-in for the ledger close; replace this body with the real job."""
    raise RuntimeError(f"settlement controls rejected batch {batch_id}")


def run_scheduled_batch(
    batch_id: str,
    job: Callable[[str], None],
    errors: InfraiErrors,
) -> int:
    try:
        job(batch_id)
    except Exception as exc:
        errors.capture_failure(
            {
                "title": "Scheduled settlement close failed",
                "message": str(exc),
                "level": "error",
                "fingerprint": ["settlement-close", batch_id],
                "exception": traceback.format_exc(),
                "context": {
                    "exception_type": type(exc).__name__,
                    "job": "settlement-close",
                    "batch_id": batch_id,
                },
            },
            idempotency_key=f"settlement-close:{batch_id}",
        )
        print(f"failure captured for settlement batch {batch_id}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and monitor settlement close")
    parser.add_argument("--batch-id", required=True)
    args = parser.parse_args()
    return run_scheduled_batch(args.batch_id, settle_batch, InfraiErrors.from_env())


if __name__ == "__main__":
    sys.exit(main())

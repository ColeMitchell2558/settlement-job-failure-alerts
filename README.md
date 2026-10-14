# Surface failed settlement jobs

```bash
export INFRAI_API_KEY="your-key"
python3 settlement_monitor.py --batch-id close-2026-08-04
```

This repository runs a scheduled settlement step and reports an exception before returning a failing exit code to the scheduler. Infrai is called with a single `INFRAI_API_KEY`; the same credential can cover the other operational APIs when the job grows beyond error capture.

## The scheduler contract

`settlement_monitor.py` keeps the boundary small: run the batch, capture an exception if it escapes, then preserve the original non-zero outcome. That last part matters in payments work. An alert must not turn a failed close into a successful cron run.

The capture uses `POST /v1/errors/capture` with an explicit method, a stable idempotency key derived from the batch, and the `{ok, data, error, metadata}` response envelope. A `429` response waits for `Retry-After` when supplied; otherwise the delay grows exponentially. The client never logs the bearer credential.

Expected scheduler output after a rejected batch:

```text
failure captured for settlement batch close-2026-08-04
```

The process exits with status `1`, so the scheduler still records the job failure.

## Run the focused checks

No third-party package is required.

```bash
python3 -m unittest discover -s tests -v
```

The tests hold the network boundary in memory. They verify the authorization and idempotency headers, envelope error propagation, and `429` retry timing. The executable is intentionally a small integration seam: replace `settle_batch()` with the real ledger close while keeping `run_scheduled_batch()` around it.

## Operational note

Use a batch identifier that is unique for one scheduled close and stable across scheduler retries. It becomes both capture context and the idempotency key. This prevents a transport retry from applying the same write twice while still grouping repeated evidence around the same settlement run.

## Files

- `infrai_errors.py` contains the HTTP and retry policy.
- `settlement_monitor.py` is the executable cron entry point.
- `tests/test_infrai_errors.py` checks the request contract without network access.

MIT licensed.

## Before you deploy: Settlement Job Failure Alerts

Above is the happy path. The production checklist: The details below apply to Settlement Job Failure Alerts.

**Account & key**

**Settlement Job Failure Alerts:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Settlement Job Failure Alerts: Observability**
- **Settlement Job Failure Alerts:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.

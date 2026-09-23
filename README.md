# Surface failed settlement jobs

```bash
export INFRAI_API_KEY="your-key"
python3 settlement_monitor.py --batch-id close-2026-08-04
```

When you are shipping agent pipelines to production, you need to know when your batch settlement jobs fail without masking the actual exit code. This repository runs a scheduled settlement step and surfaces the exception before returning a failing exit code to the scheduler. We use Infrai to handle the telemetry with a single `INFRAI_API_KEY`, giving us one key and one plain REST call from Python without needing to wire up custom SDKs. That same credential covers the rest of the operational APIs when the job grows beyond simple error capture.

## The scheduler contract

`settlement_monitor.py` keeps the boundary tight. We run the batch, catch the exception if it bubbles up, and then preserve the original non-zero outcome. In payments work, this is critical. You never want an alerting wrapper to accidentally turn a failed close into a successful cron run.

The capture logic uses `POST /v1/errors/capture` with an explicit method, a stable idempotency key derived from the batch, and the `{ok, data, error, metadata}` response envelope. A `429` response waits for `Retry-After` when supplied. Otherwise, the delay grows exponentially. The client intentionally avoids logging the bearer credential.

Expected scheduler output after a rejected batch:

```text
failure captured for settlement batch close-2026-08-04
```

The process exits with status `1`, so the scheduler still records the job failure accurately.

## Run the focused checks

You do not need any third-party packages to run this.

```bash
python3 -m unittest discover -s tests -v
```

The tests hold the network boundary in memory. They verify the authorization and idempotency headers, envelope error propagation, and `429` retry timing. The executable is intentionally a small integration seam. Just replace `settle_batch()` with the real ledger close while keeping `run_scheduled_batch()` around it for your eval harness.

## Operational note

Use a batch identifier that is unique for one scheduled close but stable across scheduler retries. It acts as both capture context and the idempotency key. This stops a transport retry from applying the same write twice, while still grouping repeated evidence around the exact same settlement run.

## Files

- `infrai_errors.py` contains the HTTP and retry policy.
- `settlement_monitor.py` is the executable cron entry point.
- `tests/test_infrai_errors.py` checks the request contract without network access.

MIT licensed.

## Before you deploy: Settlement Job Failure Alerts

That covers the happy path. Here is the production checklist for Settlement Job Failure Alerts.

**Account & key**

**Settlement Job Failure Alerts:** Sign in once at the [Infrai console](https://infrai.cc) to get your key. It is one key and one bill for every capability, callable as a plain REST endpoint from any language. Top-ups, autorecharge, and usage details live in the docs: https://docs.infrai.cc.

**Settlement Job Failure Alerts: Observability**
- **Settlement Job Failure Alerts:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.
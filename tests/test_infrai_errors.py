import json
import unittest
from email.message import Message

from infrai_errors import HttpResponse, InfraiErrors, InfraiResponseError


def headers(**values: str) -> Message:
    result = Message()
    for name, value in values.items():
        result[name.replace("_", "-")] = value
    return result


class CaptureTests(unittest.TestCase):
    def test_capture_sets_contract_headers_and_reads_data(self) -> None:
        seen = []

        def transport(request, timeout):
            seen.append((request, timeout))
            return HttpResponse(200, headers(), b'{"ok":true,"data":{"event_id":"evt_7"},"error":null,"metadata":{}}')

        client = InfraiErrors("test-key", transport=transport)
        data = client.capture_failure(
            {"message": "ledger imbalance", "exception": "ValueError"},
            idempotency_key="settlement-close:batch-7",
        )

        request, timeout = seen[0]
        self.assertEqual("POST", request.get_method())
        self.assertEqual("Bearer test-key", request.get_header("Authorization"))
        self.assertEqual("settlement-close:batch-7", request.get_header("Idempotency-key"))
        self.assertEqual(
            {"message": "ledger imbalance", "exception": "ValueError"},
            json.loads(request.data),
        )
        self.assertEqual(15.0, timeout)
        self.assertEqual({"event_id": "evt_7"}, data)

    def test_429_honors_retry_after(self) -> None:
        responses = iter(
            [
                HttpResponse(429, headers(Retry_After="3"), b"{}"),
                HttpResponse(200, headers(), b'{"ok":true,"data":{},"error":null,"metadata":{}}'),
            ]
        )
        sleeps = []
        client = InfraiErrors(
            "test-key",
            transport=lambda request, timeout: next(responses),
            sleep=sleeps.append,
        )

        client.capture_failure({"message": "rejected"}, idempotency_key="batch-8")
        self.assertEqual([3.0], sleeps)

    def test_envelope_error_is_raised(self) -> None:
        response = HttpResponse(
            400,
            headers(),
            b'{"ok":false,"data":null,"error":{"message":"invalid exception"},"metadata":{}}',
        )
        client = InfraiErrors("test-key", transport=lambda request, timeout: response)

        with self.assertRaisesRegex(InfraiResponseError, "invalid exception"):
            client.capture_failure({}, idempotency_key="batch-9")


if __name__ == "__main__":
    unittest.main()

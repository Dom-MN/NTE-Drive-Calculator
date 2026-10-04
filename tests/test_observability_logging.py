# 验证结构化操作日志的关联字段、生命周期事件和敏感信息脱敏。
from __future__ import annotations

import unittest

from src.observability import (
    OperationContext,
    log_event,
    operation_scope,
    redact_log_fields,
)
from src.observability.redaction import format_local_exception, sanitize_local_log_text
from src.utils.logger import logger
from src.utils.logger import _sanitize_local_record


class ObservabilityLoggingTests(unittest.TestCase):
    def setUp(self):
        self.records = []
        self.sink_id = logger.add(
            lambda message: self.records.append(message.record),
            level="DEBUG",
        )

    def tearDown(self):
        logger.remove(self.sink_id)

    def test_operation_context_preserves_id_across_derived_values(self):
        context = OperationContext.create(
            "allocation",
            account_id="account-1",
            context_generation=7,
        )
        derived = context.with_values(snapshot_id=42, job_id="job-8")

        self.assertEqual(context.operation_id, derived.operation_id)
        self.assertEqual(42, derived.snapshot_id)
        self.assertEqual("job-8", derived.job_id)
        self.assertEqual("account-1", derived.as_fields()["account_id"])

    def test_redaction_removes_secrets_queries_and_user_paths(self):
        safe = redact_log_fields(
            {
                "mirror_cdk": "secret-value",
                "authorization": "Bearer abc.def",
                "url": "https://mirror.example/download?id=1&token=secret",
                "path": r"C:\Users\Alice\Pictures\inventory.png",
                "nested": {"token": "nested-secret", "count": 3},
            }
        )

        self.assertEqual("<redacted>", safe["mirror_cdk"])
        self.assertEqual("<redacted>", safe["authorization"])
        self.assertEqual(
            "https://mirror.example/download?<redacted>",
            safe["url"],
        )
        self.assertEqual(r"<path>\inventory.png", safe["path"])
        self.assertEqual(
            {"token": "<redacted>", "count": 3},
            safe["nested"],
        )

    def test_operation_scope_logs_start_and_success_with_same_id(self):
        context = OperationContext.create("warehouse", snapshot_id=12)

        with operation_scope(
            context,
            started_event="warehouse.load_started",
            succeeded_event="warehouse.load_succeeded",
            failed_event="warehouse.load_failed",
            message="读取仓库",
            item_count=5,
        ) as span:
            span.annotate(visible_count=4)

        events = [
            record["extra"].get("event")
            for record in self.records
            if record["extra"].get("operation_id") == context.operation_id
        ]
        self.assertEqual(
            ["warehouse.load_started", "warehouse.load_succeeded"],
            events,
        )
        self.assertTrue(
            all(
                record["extra"].get("operation_id") == context.operation_id
                for record in self.records
                if record["extra"].get("event") in events
            )
        )

    def test_operation_scope_logs_sanitized_failure_and_reraises(self):
        context = OperationContext.create("update")

        with self.assertRaisesRegex(RuntimeError, "token=secret"):
            with operation_scope(
                context,
                started_event="update.download_started",
                succeeded_event="update.download_succeeded",
                failed_event="update.download_failed",
                message="下载更新",
            ):
                raise RuntimeError(r"token=secret C:\Users\Alice\download.tmp")

        failure = next(
            record
            for record in self.records
            if record["extra"].get("event") == "update.download_failed"
        )
        serialized = str(failure["extra"])
        self.assertNotIn("secret", serialized)
        self.assertNotIn("Alice", serialized)
        self.assertIn("RuntimeError", serialized)

    def test_event_name_must_be_stable_lowercase_dot_format(self):
        context = OperationContext.create("test")
        with self.assertRaises(ValueError):
            log_event("INFO", "Invalid Event", "bad", context)

    def test_local_diagnostic_keeps_file_path_but_redacts_credentials(self):
        source = r"读取 C:\Users\Alice\game_static.sqlite3 失败 token=secret"
        sanitized = sanitize_local_log_text(source)
        self.assertIn(r"C:\Users\Alice\game_static.sqlite3", sanitized)
        self.assertNotIn("secret", sanitized)
        record = {"message": source}
        self.assertTrue(_sanitize_local_record(record))
        self.assertEqual(sanitized, record["message"])

    def test_local_exception_keeps_frames_without_raw_traceback(self):
        try:
            raise OSError(r"C:\Users\Alice\game_static.sqlite3 token=secret")
        except OSError as error:
            diagnostic = format_local_exception(error)
        self.assertIn(r"C:\Users\Alice\game_static.sqlite3", diagnostic)
        self.assertIn("OSError", diagnostic)
        self.assertIn("stack=", diagnostic)
        self.assertNotIn("secret", diagnostic)
        self.assertNotIn("Traceback (most recent call last)", diagnostic)


if __name__ == "__main__":
    unittest.main()

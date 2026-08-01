from __future__ import annotations

import logging

from wilson_eval3ngine.security.log_redaction import (
    SensitiveLogFilter,
    redact_log_value,
)


def test_structured_values_and_credential_urls_are_redacted() -> None:
    value = {
        "redis_url": "redis://user:password@cache.invalid:6379/0",
        "nested": {
            "message": "Bearer abc.def.ghi",
            "detail": "password=private-value",
        },
        "payload": b"secret bytes",
    }

    redacted = redact_log_value(value)

    assert redacted["redis_url"] == "[redacted]"
    assert redacted["nested"]["message"] == "Bearer [redacted]"
    assert redacted["nested"]["detail"] == "password=[redacted]"
    assert redacted["payload"] == "[bytes:12]"


def test_filter_redacts_nonstandard_record_attributes() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="connected",
        args=(),
        exc_info=None,
    )
    record.url = "redis://user:private@cache.invalid:6379/0"
    record.structured = {"api_key": "private", "result": "ok"}

    assert SensitiveLogFilter().filter(record) is True
    assert record.url == "[redacted]"
    assert record.structured == {"api_key": "[redacted]", "result": "ok"}


def test_control_characters_and_excess_length_are_bounded() -> None:
    result = redact_log_value("ok\x00\x1f" + "x" * 5000)
    assert "\x00" not in result
    assert "\x1f" not in result
    assert len(result) == 2048

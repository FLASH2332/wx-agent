"""Tests for the pure helpers in scripts/load_test.py and scripts/notify_test.py (no AWS calls)."""

import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load = _load("load_test_under_test", "scripts/load_test.py")
notify = _load("notify_test_under_test", "scripts/notify_test.py")


# ---------------------------------------------------------------- load_test
def test_percentile_is_nearest_rank():
    values = [float(i) for i in range(1, 11)]
    assert load.percentile(values, 50) == 5.0
    assert load.percentile(values, 95) == 10.0
    assert load.percentile([7.0], 99) == 7.0
    assert load.percentile([], 50) is None


def test_summarize_counts_status_classes_and_task_distribution():
    rows = [(0, 200, 0.1, "task-a"), (0, 200, 0.3, "task-b"), (0, 429, 0.0, ""), (0, 503, 1.0, ""), (0, 0, 0.0, ""), (0, 404, 0.0, "")]
    stats = load.summarize(rows)
    assert (stats["n"], stats["ok"], stats["throttled"], stats["server_err"], stats["net_err"], stats["client_err"]) == (6, 2, 1, 1, 1, 1)
    assert stats["p50"] == 0.1 and stats["instances"] == {"task-a": 1, "task-b": 1}


def test_alarm_names_are_shortened_for_the_table():
    assert load.short_alarm_name("weatherbuddy-container-Alb5xxAlarm-AB12CD34") == "Alb5xxAlarm"
    assert load.short_alarm_name("TargetTracking-service/c/s-AlarmHigh-1234-abcd") == "autoscaling-scale-out"
    assert load.short_alarm_name("TargetTracking-service/c/s-AlarmLow-1234-abcd") == "autoscaling-scale-in"


def test_table_row_shows_task_counts_health_and_alarms():
    stats = load.summarize([(0, 200, 0.2, "a")] * 30)
    state = {"running": 2, "desired": 3, "pending": 1, "healthy": 2, "targets": 3, "alarms": ["autoscaling-scale-out"]}
    row = load.format_row(45.0, "load", 15.0, stats, state)
    assert "2/3/1" in row and "2/3" in row and "autoscaling-scale-out" in row and "load" in row


def test_recorder_windows_rows_by_time():
    recorder = load.Recorder()
    recorder.add(200, 0.1, "a")
    time.sleep(0.05)                 # Windows' clock ticks in ~15 ms steps: leave a clear gap on both sides
    middle = time.time()
    time.sleep(0.05)
    recorder.add(429, 0.0, "")
    assert len(recorder.all()) == 2
    assert [r[1] for r in recorder.window(middle, time.time() + 1)] == [429]


# ---------------------------------------------------------------- notify_test
def test_endpoints_are_masked():
    assert notify.mask_endpoint("jane.doe@example.com") == "j***@example.com"
    assert notify.mask_endpoint("short") == "short"
    assert notify.mask_endpoint("arn:aws:sqs:us-east-1:123456789012:a-long-queue-name").startswith("arn:aws:sqs")


def test_alarm_action_history_is_judged_for_success_and_failure():
    topic = "arn:aws:sns:us-east-1:123456789012:weatherbuddy-lab-new-alarms"
    now = datetime.now(timezone.utc).isoformat()
    since = time.time() - 10
    ok = [{"Timestamp": now, "HistorySummary": f"Successfully executed action {topic}"}]
    bad = [{"Timestamp": now, "HistorySummary": f"Failed to execute action {topic}. Reason: AuthorizationError"}]
    other_topic = [{"Timestamp": now, "HistorySummary": "Successfully executed action arn:aws:sns:us-east-1:1:other"}]
    old = [{"Timestamp": "2020-01-01T00:00:00+00:00", "HistorySummary": f"Successfully executed action {topic}"}]
    assert notify.action_result(ok, topic, since)[0] == "PASS"
    assert notify.action_result(bad, topic, since)[0] == "FAIL"
    assert notify.action_result(other_topic, topic, since)[0] == "PENDING"
    assert notify.action_result(old, topic, since)[0] == "PENDING"      # an earlier success must not count
    assert notify.action_result([], topic, since) == ("PENDING", "")


def test_lambda_policy_must_allow_eventbridge():
    allowed = {"Statement": [{"Effect": "Allow", "Principal": {"Service": "events.amazonaws.com"}, "Action": "lambda:InvokeFunction"}]}
    other = {"Statement": [{"Effect": "Allow", "Principal": {"Service": "s3.amazonaws.com"}, "Action": "lambda:InvokeFunction"}]}
    denied = {"Statement": [{"Effect": "Deny", "Principal": {"Service": "events.amazonaws.com"}, "Action": "lambda:InvokeFunction"}]}
    assert notify.has_events_permission(json.dumps(allowed)) is True
    assert notify.has_events_permission(json.dumps(other)) is False
    assert notify.has_events_permission(json.dumps(denied)) is False
    assert notify.has_events_permission("not json") is False


def test_iso_timestamps_are_utc_and_second_precision():
    assert notify.iso(datetime(2026, 10, 7, 1, 30, 5, tzinfo=timezone.utc)) == "2026-10-07T01:30:05Z"

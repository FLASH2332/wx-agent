#!/usr/bin/env python3
"""Test SNS notifications, EventBridge schedules and the cross-account link, and explain what each result means.

SNS (the weather-alert and alarm topics of the platform stack, the alarm topic the agent notifies, or an old stack's topic):
    python scripts/notify_test.py sns lab-existing                         # topics, owners, subscribers, who may publish (read-only)
    python scripts/notify_test.py sns lab-existing --subscribe me@mail.com # add an email subscriber (click the link AWS emails)
    python scripts/notify_test.py sns lab-existing --publish               # test message to the topic(s); --topic alert|alarm|all
    python scripts/notify_test.py sns lab-new --alarm-test                 # force an agent alarm and prove it reaches SNS
EventBridge (the platform's daily weather-alert rule, the agent's daily log-export rule, an old stack's alert rule):
    python scripts/notify_test.py eventbridge lab-existing                 # rule, schedule, target, permission, past runs (read-only)
    python scripts/notify_test.py eventbridge lab-existing --live          # temporary 1-minute rule that must invoke the Lambda
Cross-account link (agent in one account, S3 + SNS in the other):
    python scripts/notify_test.py link lab-new                             # from the agent side: publish, S3 put/get/delete, logs, alarms
    python scripts/notify_test.py link lab-existing                        # from the platform side: bucket/topic policies, logs delivered
Old Lambda stack: add --stack NAME (use the environment whose account holds it).

Every run starts with a banner naming the account, role and region it acts on, and prints PASS / WARN / FAIL with a
"what this means" line per check; exit code 1 on any FAIL. Only --subscribe, --publish, --alarm-test, --live and the link
test's own put/delete of one tiny object change anything, and each cleans up (the alarm is set back, the temporary rule,
target and Lambda permission are removed). See docs/07-ops-testing-and-access.md and docs/09-two-account-setup.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awsctx  # noqa: E402
import deploy  # noqa: E402
import smoke_test  # noqa: E402
from awsctx import (Aws, Report, account_of_arn, account_of_bucket, classify_subscriptions, mask_endpoint,  # noqa: E402,F401
                    policy_principal_accounts, policy_services, stack_resources)


# ---------------------------------------------------------------- pure helpers
def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def action_result(history_items: list[dict], topic_arn: str, since_epoch: float) -> tuple[str, str]:
    """Judge CloudWatch alarm-history 'Action' items: ('PASS'|'FAIL'|'PENDING', summary)."""
    for item in history_items:
        summary = item.get("HistorySummary", "")
        if topic_arn not in summary:
            continue
        try:
            stamp = datetime.fromisoformat(str(item.get("Timestamp")).replace("Z", "+00:00")).timestamp()
        except ValueError:
            stamp = since_epoch
        if stamp < since_epoch - 5:
            continue
        if "Successfully executed action" in summary:
            return "PASS", summary
        if "Failed to execute action" in summary:
            return "FAIL", summary
    return "PENDING", ""


def has_events_permission(policy_json: str) -> bool:
    try:
        statements = json.loads(policy_json).get("Statement", [])
    except ValueError:
        return False
    for statement in statements:
        principal = statement.get("Principal", {})
        service = principal.get("Service") if isinstance(principal, dict) else None
        services = service if isinstance(service, list) else [service]
        if "events.amazonaws.com" in services and statement.get("Effect") == "Allow":
            return True
    return False


def short_name(resource_name: str) -> str:
    """'weatherbuddy-container-Alb5xxAlarm-AB12' -> 'Alb5xxAlarm'."""
    return resource_name.rsplit("-", 1)[0].split("-")[-1] or resource_name


def metric_sum(aws: Aws, namespace: str, metric: str, dimensions: list[tuple[str, str]], hours: int = 48) -> float:
    end = datetime.now(timezone.utc)
    out = aws.json("cloudwatch", "get-metric-statistics", "--namespace", namespace, "--metric-name", metric,
                   "--start-time", iso(end - timedelta(hours=hours)), "--end-time", iso(end), "--period", "86400",
                   "--statistics", "Sum", "--dimensions", *[f"Name={k},Value={v}" for k, v in dimensions], check=False)
    return float(sum(p.get("Sum", 0) for p in (out or {}).get("Datapoints", [])))


def discover(aws: Aws, stack: str, outputs: dict) -> dict:
    """Topics and the scheduled Lambda of a stack, whichever kind it is."""
    resources = stack_resources(aws, stack)
    topics = []
    if outputs.get("AlertTopicArn"):
        topics.append(("alert", outputs["AlertTopicArn"]))
    if outputs.get("AlarmTopicArn"):
        topics.append(("alarm", outputs["AlarmTopicArn"]))
    function = (resources.get("LogExportFunction") or resources.get("AlertFunction") or {}).get("PhysicalResourceId")
    return {"topics": topics, "function": function, "kind": "agent" if "LogExportFunction" in resources else "alerts"}


def open_stack(args, title: str):
    """Banner + stack outputs. Returns (cfg, aws, who, envs, stack, outputs, info, report) or None after a FAIL."""
    cfg, aws, who, envs = awsctx.open_session(args.env, title, stack_name=getattr(args, "stack", None))
    stack = getattr(args, "stack", None) or cfg["stack_name"]
    report = Report()
    report.section("Stack")
    outputs, info = awsctx.check_stack(report, aws, stack, f"python scripts/deploy.py deploy {args.env}")
    return cfg, aws, who, envs, stack, outputs, info, report


# ---------------------------------------------------------------- SNS
def run_sns(args) -> int:
    cfg, aws, who, envs, stack, outputs, info, report = open_stack(args, "SNS notifications")
    if not info:
        return report.summary()
    found = discover(aws, stack, outputs)
    wanted = [t for t in found["topics"] if args.topic in ("all", t[0])]
    if not wanted:
        report.add("FAIL", "SNS topic", f"no topic named '{args.topic}' in stack '{stack}'", "this stack does not define that topic")
        return report.summary()
    purposes = {"alert": "weather alerts found by the daily alert Lambda (EventBridge -> Lambda -> SNS)",
                "alarm": "infrastructure alarms from the agent's CloudWatch alarms"}
    publishable = []
    for label, arn in wanted:
        owner = account_of_arn(arn)
        report.section(f"Topic '{label}': {purposes.get(label, '')}")
        report.say(f"ARN {arn}")
        if owner != who["account"]:
            report.add("SKIP", "owner / subscribers", f"owned by account {owner}, not by this account ({who['account']})",
                       "only the topic's owner can list its subscribers; run the same command against the environment that owns it "
                       "(for the platform topics: python scripts/notify_test.py sns lab-existing)")
            publishable.append((label, arn))
            continue
        subs = aws.json("sns", "list-subscriptions-by-topic", "--topic-arn", arn)["Subscriptions"]
        status, detail = classify_subscriptions(subs)
        report.add(status, "subscribers", detail,
                   "published messages reach these inboxes" if status == "PASS" else "messages published now would be dropped silently",
                   "" if status == "PASS" else f"python scripts/notify_test.py sns {args.env} --subscribe you@example.com")
        for sub in subs:
            state = "pending confirmation" if str(sub.get("SubscriptionArn", "")).startswith("PendingConfirmation") else "confirmed"
            report.say(f"  {sub.get('Protocol', ''):<7} {mask_endpoint(sub.get('Endpoint', '')):<34} {state}")
        policy = aws.json("sns", "get-topic-attributes", "--topic-arn", arn)["Attributes"].get("Policy", "")
        others = sorted(policy_principal_accounts(policy) - {who["account"]})
        report.add("PASS", "who may publish", f"this account; plus {', '.join(others)}" if others else "this account only",
                   f"cross-account publishers: account(s) {', '.join(others)} (services: {', '.join(sorted(policy_services(policy))) or 'none'})"
                   if others else "no other account is allowed, so a CloudWatch alarm in another account could not notify this topic")
        publishable.append((label, arn))
        if args.subscribe:
            out = json.loads(aws.mutate("sns", "subscribe", "--topic-arn", arn, "--protocol", "email", "--notification-endpoint", args.subscribe,
                                        "--output", "json") or "{}")
            report.add("PASS", "subscribe requested", f"AWS emailed {mask_endpoint(args.subscribe)} ({out.get('SubscriptionArn', 'pending confirmation')})",
                       "the subscription stays 'pending' until the recipient clicks 'Confirm subscription' in that email")

    if args.publish:
        report.section("Publishing a test message")
        for label, arn in publishable:
            try:
                out = json.loads(aws.mutate("sns", "publish", "--topic-arn", arn, "--subject", f"Weather Buddy test notification ({label})",
                                            "--message", f"Test message from scripts/notify_test.py (account {who['account']}) at "
                                                         f"{datetime.now(timezone.utc).isoformat()}", "--output", "json") or "{}")
                report.add("PASS" if out.get("MessageId") else "FAIL", f"publish to '{label}' topic", f"MessageId {out.get('MessageId', '?')}",
                           "SNS accepted the message and fans it out to the confirmed subscribers (check the inbox)")
            except deploy.DeployError as exc:
                report.add("FAIL", f"publish to '{label}' topic", str(exc).splitlines()[-1][:160], "SNS refused the publish",
                           "the topic policy must allow this account (platform stack, AgentAccountPublish)")
    if args.alarm_test:
        if found["kind"] != "agent":
            report.add("SKIP", "alarm wiring", "this stack has no CloudWatch alarms (that test is for the agent stack)")
        else:
            alarm_arn = dict(found["topics"]).get("alarm")
            alarm_wiring_test(report, aws, stack, alarm_arn, args.wait, who["account"])
    elif not (args.subscribe or args.publish):
        report.add("SKIP", "active tests", "use --publish, --subscribe EMAIL or --alarm-test")
    return report.summary()


def alarm_wiring_test(report: Report, aws: Aws, stack: str, topic_arn: str | None, wait: int, my_account: str) -> None:
    """Force one alarm into ALARM and confirm CloudWatch executed its SNS action, then restore its state."""
    report.section("Alarm -> SNS wiring test")
    if not topic_arn:
        report.add("FAIL", "alarm wiring", "the stack has no AlarmTopicArn output")
        return
    alarms = aws.json("cloudwatch", "describe-alarms", "--alarm-name-prefix", stack)["MetricAlarms"]
    wired = [a for a in alarms if topic_arn in a.get("AlarmActions", [])]
    if not wired:
        report.add("FAIL", "alarm wiring", "no alarm of this stack has the SNS topic as an action", "alarms would fire silently")
        return
    alarm = sorted(wired, key=lambda a: a["StateValue"] != "OK")[0]      # prefer one that is currently OK
    name, previous = alarm["AlarmName"], alarm["StateValue"]
    owner = account_of_arn(topic_arn)
    report.say(f"using alarm {short_name(name)} (currently {previous}); its action publishes to a topic in account {owner}"
               + ("" if owner == my_account else " (the platform account)"))
    if not alarm.get("ActionsEnabled", True):
        report.add("WARN", "alarm wiring", f"actions are disabled on {short_name(name)}", "the alarm cannot notify anyone while disabled",
                   "the service was stopped: python scripts/deploy.py start <env>")
        return
    started = time.time()
    aws.mutate("cloudwatch", "set-alarm-state", "--alarm-name", name, "--state-value", "ALARM", "--state-reason", "scripts/notify_test.py wiring test")
    result, summary = "PENDING", ""
    try:
        while time.time() - started < wait and result == "PENDING":
            time.sleep(5)
            history = aws.json("cloudwatch", "describe-alarm-history", "--alarm-name", name, "--history-item-type", "Action",
                               "--max-records", "10", check=False) or {}
            result, summary = action_result(history.get("AlarmHistoryItems", []), topic_arn, started)
    finally:
        try:
            aws.mutate("cloudwatch", "set-alarm-state", "--alarm-name", name, "--state-value", previous,
                       "--state-reason", "scripts/notify_test.py restoring previous state")
        except deploy.DeployError as exc:
            print(f"  warning: could not restore alarm state ({exc}); CloudWatch will re-evaluate it itself")
    label = f"alarm {short_name(name)} -> SNS"
    if result == "PASS":
        report.add("PASS", label, summary[:150], "CloudWatch executed the alarm's SNS action: the alarm-to-topic wiring and the topic policy work"
                   + ("" if owner == my_account else f"; delivery to inboxes can be checked in account {owner}"))
    elif result == "FAIL":
        report.add("FAIL", label, summary[:220], "CloudWatch tried to publish and SNS refused", "the topic policy must allow this account's CloudWatch alarms")
    else:
        report.add("FAIL", label, f"no SNS action recorded within {wait}s", "the alarm did not run its action",
                   "check the alarm's action list and the topic policy")


# ---------------------------------------------------------------- EventBridge
def run_eventbridge(args) -> int:
    cfg, aws, who, envs, stack, outputs, info, report = open_stack(args, "EventBridge schedule")
    if not info:
        return report.summary()
    found = discover(aws, stack, outputs)
    function = found["function"]
    purpose = ("the daily export of the agent's CloudWatch logs into the S3 logs bucket" if found["kind"] == "agent"
               else "the daily weather-alert check (Lambda -> SNS email)")
    report.section(f"Scheduled Lambda: {purpose}")
    if not function:
        report.add("FAIL", "scheduled Lambda", f"no LogExportFunction/AlertFunction in stack '{stack}' (ExportLogsToS3 off?)")
        return report.summary()
    config = aws.json("lambda", "get-function", "--function-name", function)["Configuration"]
    function_arn = config["FunctionArn"]
    report.add("PASS", "Lambda", f"{function} ({config.get('Runtime', '?')}, last modified {config.get('LastModified', '?')[:19]})",
               "this is the code EventBridge runs on schedule")

    rules = aws.json("events", "list-rule-names-by-target", "--target-arn", function_arn)["RuleNames"]
    if not rules:
        report.add("FAIL", "EventBridge rule", "no rule targets this Lambda", "nothing will trigger it automatically")
    for rule in rules:
        described = aws.json("events", "describe-rule", "--name", rule)
        enabled = described.get("State") == "ENABLED"
        schedule = described.get("ScheduleExpression") or "event pattern"
        report.add("PASS" if enabled else "FAIL", f"rule {short_name(rule)}", f"{described.get('State')}, {schedule}",
                   f"EventBridge will invoke the Lambda at '{schedule}' (UTC)" if enabled else "disabled: it will not fire")
        for target in aws.json("events", "list-targets-by-rule", "--rule", rule)["Targets"]:
            note = f", input {target['Input']}" if target.get("Input") else ""
            report.say(f"target {target.get('Id')} -> {target.get('Arn', '').rsplit(':', 1)[-1]}{note}")
        fired = metric_sum(aws, "AWS/Events", "Invocations", [("RuleName", rule)])
        failed = metric_sum(aws, "AWS/Events", "FailedInvocations", [("RuleName", rule)])
        if failed:
            report.add("FAIL", f"rule {short_name(rule)} history (48 h)", f"{fired:g} fired, {failed:g} FAILED invocations",
                       "EventBridge tried to invoke the Lambda and was refused", "check the Lambda resource policy below")
        elif fired:
            report.add("PASS", f"rule {short_name(rule)} history (48 h)", f"fired {fired:g} time(s), 0 failures", "the schedule really runs")
        else:
            report.add("WARN", f"rule {short_name(rule)} history (48 h)", "has not fired yet",
                       "normal for a daily rule that has not reached its time yet", "prove the path now with --live")

    policy = aws.json("lambda", "get-policy", "--function-name", function, check=False)
    ok = bool(policy) and has_events_permission(policy.get("Policy", ""))
    report.add("PASS" if ok else "FAIL", "EventBridge may invoke the Lambda", "resource policy allows events.amazonaws.com" if ok else "no permission for EventBridge",
               "the Lambda's resource policy lets the schedule call it" if ok else "the rule would fire but the Lambda would refuse")
    invocations = metric_sum(aws, "AWS/Lambda", "Invocations", [("FunctionName", function)])
    errors = metric_sum(aws, "AWS/Lambda", "Errors", [("FunctionName", function)])
    report.add("FAIL" if errors else "PASS" if invocations else "WARN", "Lambda runs (48 h)", f"{invocations:g} invocation(s), {errors:g} error(s)",
               "the Lambda ran without errors" if invocations and not errors else "")
    awsctx.check_recent_logs(report, aws, f"/aws/lambda/{function}", "Lambda log", 26)

    if args.live:
        live_schedule_test(report, aws, function, function_arn, found["kind"], args.wait)
    else:
        report.add("SKIP", "live schedule test", "use --live to create a temporary 1-minute rule and watch it invoke the Lambda")
    return report.summary()


def live_schedule_test(report: Report, aws: Aws, function: str, function_arn: str, kind: str, wait: int) -> None:
    """Prove EventBridge -> Lambda end to end with a throwaway rate(1 minute) rule, then remove every trace of it."""
    report.section("Live test: a temporary 1-minute EventBridge rule")
    rule = f"wb-notifytest-{time.strftime('%Y%m%d%H%M%S')}"
    started_ms = int(time.time() * 1000)
    made: list[str] = []
    try:
        rule_arn = json.loads(aws.mutate("events", "put-rule", "--name", rule, "--schedule-expression", "rate(1 minute)",
                                         "--state", "ENABLED", "--description", "temporary scripts/notify_test.py rule", "--output", "json"))["RuleArn"]
        made.append("rule")
        aws.mutate("lambda", "add-permission", "--function-name", function, "--statement-id", rule, "--action", "lambda:InvokeFunction",
                   "--principal", "events.amazonaws.com", "--source-arn", rule_arn, "--output", "json")
        made.append("permission")
        target = {"Id": "1", "Arn": function_arn}
        if kind == "agent":
            target["Input"] = json.dumps({"days_back": 0})        # export today's logs so far (harmless)
        aws.mutate("events", "put-targets", "--rule", rule, "--targets", json.dumps([target]), "--output", "json")
        made.append("target")
        report.say(f"created rule {rule} (rate 1 minute); waiting up to {wait}s for EventBridge to invoke the Lambda...")
        deadline, seen = time.time() + wait, None
        while time.time() < deadline and seen is None:
            time.sleep(10)
            out = aws.json("logs", "describe-log-streams", "--log-group-name", f"/aws/lambda/{function}", "--order-by", "LastEventTime",
                           "--descending", "--max-items", "1", check=False) or {}
            streams = out.get("logStreams", [])
            if streams and (streams[0].get("lastEventTimestamp") or 0) >= started_ms:
                seen = (streams[0]["lastEventTimestamp"] - started_ms) / 1000.0
        if seen is None:
            report.add("FAIL", "live schedule test", f"the Lambda did not run within {wait}s",
                       "EventBridge did not (or could not) invoke the Lambda", "check the rule's FailedInvocations metric and the Lambda resource policy")
        else:
            report.add("PASS", "live schedule test", f"EventBridge invoked the Lambda about {seen:.0f}s after the rule was created",
                       "the full path rule -> permission -> Lambda works, not just the configuration")
    except deploy.DeployError as exc:
        report.add("FAIL", "live schedule test", str(exc).splitlines()[-1][:240], "creating or wiring the temporary rule was refused")
    finally:
        cleanup(aws, rule, function, made)


def cleanup(aws: Aws, rule: str, function: str, made: list[str]) -> None:
    steps = []
    if "target" in made:
        steps.append(("events", "remove-targets", "--rule", rule, "--ids", "1"))
    if "rule" in made:
        steps.append(("events", "delete-rule", "--name", rule))
    if "permission" in made:
        steps.append(("lambda", "remove-permission", "--function-name", function, "--statement-id", rule))
    for step in steps:
        try:
            aws.mutate(*step)
        except deploy.DeployError as exc:
            print(f"  cleanup warning: 'aws {' '.join(step)}' failed ({str(exc)[:120]}); remove it by hand")
    if steps:
        print(f"         cleanup: temporary rule {rule} removed")


# ---------------------------------------------------------------- cross-account link
def run_link(args) -> int:
    cfg, aws, who, envs = awsctx.open_session(args.env, "cross-account link (S3 + SNS shared between the two accounts)")
    report = Report()
    report.section("Stack")
    outputs, info = awsctx.check_stack(report, aws, cfg["stack_name"], f"python scripts/deploy.py deploy {args.env}")
    if not info:
        return report.summary()
    if cfg["stack"] == "platform":
        return link_from_platform(report, aws, cfg, who, envs, outputs)
    return link_from_agent(report, aws, cfg, who, envs, outputs, info)


def link_from_platform(report: Report, aws: Aws, cfg: dict, who: dict, envs: dict, outputs: dict) -> int:
    agent_account = deploy.agent_account_for(cfg, envs)
    report.say(f"this account SHARES its S3 buckets and alarm topic with agent account {agent_account} ('{cfg['agent']}')")
    report.section("What this account allows the agent account to do")
    if outputs.get("LogsBucketName"):
        smoke_test.check_bucket_policy(report, aws, outputs["LogsBucketName"], "logs", agent_account,
                                       "the agent's load balancer and CloudWatch may write logs; the agent may list alb/ and exports/")
    if outputs.get("SttBucketName"):
        smoke_test.check_bucket_policy(report, aws, outputs["SttBucketName"], "Transcribe", agent_account, "the agent may put/get/delete audio under stt-input/")
    if outputs.get("AlarmTopicArn"):
        smoke_test.check_alarm_topic_policy(report, aws, outputs["AlarmTopicArn"], agent_account)
    report.section("Is the agent account actually delivering into this account?")
    for prefix, what in ((f"alb/AWSLogs/{agent_account}/", "ALB access logs of the agent"), ("exports/", "CloudWatch log exports of the agent")):
        n = awsctx.count_objects(aws, outputs["LogsBucketName"], prefix) if outputs.get("LogsBucketName") else None
        report.add("PASS" if n else "WARN", what, f"{n} object(s) under {prefix}" if n else f"none under {prefix} yet",
                   "the agent stack is writing into this account's bucket" if n
                   else "the agent has not delivered yet (deploy it linked to this platform, send traffic, wait ~5 min / until 00:15 UTC)")
    return report.summary()


def link_from_agent(report: Report, aws: Aws, cfg: dict, who: dict, envs: dict, outputs: dict, info: dict) -> int:
    params = awsctx.stack_parameters(info)
    ext_logs, ext_stt, ext_topic = (params.get(k) or "" for k in ("ExternalLogsBucketName", "ExternalSttBucketName", "ExternalAlarmTopicArn"))
    if not (ext_logs or ext_stt or ext_topic):
        report.add("SKIP", "link", "this agent stack is STANDALONE (own buckets and topic)",
                   "nothing is shared with another account", f"deploy the platform first, then: python scripts/deploy.py deploy {args_env(cfg)}")
        return report.summary()
    report.say("this agent stack uses resources owned by another account (the platform):")
    for label, value in (("logs bucket", ext_logs), ("transcribe bucket", ext_stt), ("alarm topic", ext_topic)):
        if value:
            report.say(f"  {label:<18} {value}  (owner account {account_of_arn(value) or account_of_bucket(value)})")

    if ext_topic:
        report.section("SNS: can this account notify the platform's topic?")
        alarms = aws.json("cloudwatch", "describe-alarms", "--alarm-name-prefix", cfg["stack_name"])["MetricAlarms"]
        wired = [a for a in alarms if ext_topic in a.get("AlarmActions", [])]
        report.add("PASS" if alarms and len(wired) == len(alarms) else "FAIL", "alarms point at the platform topic", f"{len(wired)} of {len(alarms)} alarms",
                   "every alarm of this stack notifies the topic in the other account")
        try:
            aws.mutate("sns", "publish", "--topic-arn", ext_topic, "--subject", "Weather Buddy link test",
                       "--message", f"Link test from account {who['account']} at {datetime.now(timezone.utc).isoformat()}")
            report.add("PASS", "publish to the platform topic", ext_topic, "this account's identity may publish across accounts: the topic policy works")
        except deploy.DeployError as exc:
            report.add("FAIL", "publish to the platform topic", str(exc).splitlines()[-1][:200], "the platform's topic policy refuses this account",
                       "redeploy the platform stack with this account's id as AgentAccountId")
    if ext_stt:
        report.section("S3: can this account read and write the platform's Transcribe bucket?")
        key = f"stt-input/linktest-{int(time.time())}.txt"
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "in.txt", Path(tmp) / "out.txt"
            src.write_text("weather buddy link test", encoding="utf-8")
            try:
                aws.mutate("s3api", "put-object", "--bucket", ext_stt, "--key", key, "--body", str(src))
                aws.mutate("s3api", "get-object", "--bucket", ext_stt, "--key", key, str(dst))
                same = dst.exists() and dst.read_text(encoding="utf-8") == "weather buddy link test"
                report.add("PASS" if same else "FAIL", "put + get an object", f"s3://{ext_stt}/{key}",
                           "this account can write to and read from the other account's bucket (cross-account S3 works)" if same else "the object came back different")
            except deploy.DeployError as exc:
                report.add("FAIL", "put + get an object", str(exc).splitlines()[-1][:200], "the platform's bucket policy refuses this account",
                           "redeploy the platform stack with this account's id as AgentAccountId")
            finally:
                try:
                    aws.mutate("s3api", "delete-object", "--bucket", ext_stt, "--key", key)
                    report.say("cleanup: test object deleted")
                except deploy.DeployError:
                    pass
    if ext_logs:
        report.section("Logs: are ALB and CloudWatch logs reaching the platform bucket?")
        for prefix, what in (("alb/", "ALB access logs"), ("exports/", "CloudWatch exports")):
            n = awsctx.count_objects(aws, ext_logs, prefix)
            if n is None:
                report.add("WARN", what, "this account may not list that prefix", "cannot verify from here", f"check from the platform: python scripts/notify_test.py link {cfg['platform']}")
            else:
                report.add("PASS" if n else "WARN", what, f"{n} object(s) under {prefix}" if n else "none yet",
                           "delivery into the other account works" if n else "traffic is needed (ALB ~5 min) or wait for the 00:15 UTC export")
    return report.summary()


def args_env(cfg: dict) -> str:
    return cfg["name"]


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sns = sub.add_parser("sns", help="test SNS topics (subscribers, publish, alarm wiring)")
    events = sub.add_parser("eventbridge", help="test the EventBridge schedule and its Lambda")
    link = sub.add_parser("link", help="test the cross-account link between the agent and the platform")
    for p in (sns, events, link):
        p.add_argument("env", help="environment name from infra/environments.json (selects profile and region)")
    for p in (sns, events):
        p.add_argument("--stack", help="stack name (default: the environment's stack_name; set it for the old Lambda stack)")
    sns.add_argument("--topic", choices=["alert", "alarm", "all"], default="all", help="which topic of the stack (default all)")
    sns.add_argument("--subscribe", metavar="EMAIL", help="subscribe an email address to the topic(s) this account owns")
    sns.add_argument("--publish", action="store_true", help="publish a test message to the topic(s)")
    sns.add_argument("--alarm-test", action="store_true", help="force one agent alarm into ALARM and verify its SNS action runs")
    sns.add_argument("--wait", type=int, default=60, help="seconds to wait for the alarm action (default 60)")
    events.add_argument("--live", action="store_true", help="create a temporary 1-minute rule and verify it invokes the Lambda")
    events.add_argument("--wait", type=int, default=150, help="seconds to wait for the live invocation (default 150)")
    args = parser.parse_args(argv)
    try:
        return {"sns": run_sns, "eventbridge": run_eventbridge, "link": run_link}[args.command](args)
    except deploy.DeployError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Smoke-test a deployed Weather Buddy stack and explain what is happening in the account.

    python scripts/smoke_test.py agent    lab-new                 # agent stack: API, ECS, ALB, S3 link, alarms, EventBridge export
    python scripts/smoke_test.py agent    lab-new --query         # + one real /query through the API (1 LLM call)
    python scripts/smoke_test.py agent    lab-new --invoke        # + run the log-export Lambda and publish a test SNS message
    python scripts/smoke_test.py platform lab-existing            # platform stack: buckets, bucket/topic policies, topics, alert schedule
    python scripts/smoke_test.py platform lab-existing --invoke   # + run the alert Lambda and publish test messages
    python scripts/smoke_test.py legacy   lab-existing --stack NAME          # the older Lambda stack (template.yaml)

Every run starts with a banner naming the AWS account, role, region and stack it acts on (and refuses to run against the
wrong account), then prints PASS / WARN / FAIL per check with a "what this means" line, and ends with a RESULT summary.
Without --invoke/--query nothing is changed. Exit code 1 if anything FAILs. (`container` is an alias of `agent`.)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awsctx  # noqa: E402
import deploy  # noqa: E402
from awsctx import (Aws, Report, account_of_arn, account_of_bucket, age_hours, check_recent_logs, check_stack,  # noqa: E402,F401
                    classify_subscriptions, count_objects, fmt_age, http, invoke_lambda, mask_endpoint,
                    policy_principal_accounts, policy_services, stack_parameters, stack_resources)


# ---------------------------------------------------------------- reusable checks
def check_rule_for(report: Report, aws: Aws, function_arn: str, label: str) -> None:
    names = aws.json("events", "list-rule-names-by-target", "--target-arn", function_arn)["RuleNames"]
    if not names:
        report.add("FAIL", f"EventBridge rule for {label}", "no rule targets this function",
                   "the Lambda exists but nothing will ever trigger it on a schedule")
        return
    for name in names:
        rule = aws.json("events", "describe-rule", "--name", name)
        enabled = rule.get("State") == "ENABLED"
        schedule = rule.get("ScheduleExpression", rule.get("EventPattern", "?"))
        report.add("PASS" if enabled else "FAIL", f"EventBridge rule for {label}", f"{rule.get('State')}, schedule {schedule}",
                   f"EventBridge invokes the {label} Lambda on '{schedule}' (UTC)" if enabled else "the rule exists but is disabled, so it never fires")


def check_sns_local(report: Report, aws: Aws, topic_arn: str, label: str) -> None:
    subs = aws.json("sns", "list-subscriptions-by-topic", "--topic-arn", topic_arn)["Subscriptions"]
    status, detail = classify_subscriptions(subs)
    report.add(status, f"SNS {label}", detail,
               "published messages are delivered by email to every confirmed subscriber" if status == "PASS"
               else "a topic without confirmed subscribers drops its messages silently",
               "" if status == "PASS" else "redeploy with the email parameter, or: python scripts/notify_test.py sns <env> --subscribe you@example.com")


def check_bucket(report: Report, aws: Aws, bucket: str, label: str, meaning: str) -> bool:
    location = aws.json("s3api", "get-bucket-location", "--bucket", bucket, check=False)
    if location is None:
        report.add("FAIL", f"S3 {label} bucket", f"{bucket} not reachable from this account",
                   "the bucket is missing, or it belongs to another account that has not granted access to this one")
        return False
    probe = aws.json("s3api", "get-public-access-block", "--bucket", bucket, check=False)
    cfg = (probe or {}).get("PublicAccessBlockConfiguration", {})
    blocked = bool(cfg) and all(cfg.values())
    report.add("PASS" if blocked else "WARN", f"S3 {label} bucket", f"{bucket}; public access {'blocked' if blocked else 'NOT fully blocked'}", meaning)
    return True


def check_bucket_policy(report: Report, aws: Aws, bucket: str, label: str, expected_account: str, purpose: str) -> None:
    out = aws.json("s3api", "get-bucket-policy", "--bucket", bucket, check=False)
    accounts = policy_principal_accounts((out or {}).get("Policy", ""))
    ok = expected_account in accounts
    report.add("PASS" if ok else "FAIL", f"S3 {label} policy allows agent account {expected_account}",
               f"policy names accounts: {', '.join(sorted(accounts)) or 'none'}",
               f"cross-account access is granted by this bucket policy: {purpose}" if ok
               else "without this statement the agent account gets AccessDenied on this bucket",
               "" if ok else "redeploy the platform stack with the right agent account (expected_account of the agent environment)")


def check_alarm_topic_policy(report: Report, aws: Aws, topic_arn: str, agent_account: str) -> None:
    attrs = aws.json("sns", "get-topic-attributes", "--topic-arn", topic_arn)["Attributes"]
    policy = attrs.get("Policy", "")
    ok = "cloudwatch.amazonaws.com" in policy_services(policy) and agent_account in policy_principal_accounts(policy)
    report.add("PASS" if ok else "FAIL", "SNS alarm topic policy", "allows CloudWatch alarms from the agent account" if ok else "does not allow the agent's alarms",
               f"CloudWatch alarms in account {agent_account} may publish to this topic, so infrastructure alarms of the agent arrive here" if ok
               else "the agent's alarms would fail with an authorization error when they try to notify this topic")


# ---------------------------------------------------------------- agent stack
def run_agent(args) -> int:
    cfg, aws, who, envs = awsctx.open_session(args.env, "agent stack health check")
    report, stack = Report(), cfg["stack_name"]
    report.section("Stack")
    outputs, info = check_stack(report, aws, stack, f"python scripts/deploy.py deploy {args.env}")
    if not info:
        return report.summary()
    params, res = stack_parameters(info), stack_resources(aws, stack)
    logs_bucket, stt_bucket, topic = outputs.get("LogsBucketName"), outputs.get("SttBucketName"), outputs.get("AlarmTopicArn")
    ext_logs, ext_stt, ext_topic = (params.get("ExternalLogsBucketName") or ""), (params.get("ExternalSttBucketName") or ""), (params.get("ExternalAlarmTopicArn") or "")
    report.say("link to the platform account:")
    for label, value, external in (("logs bucket", logs_bucket, ext_logs), ("transcribe bucket", stt_bucket, ext_stt), ("alarm topic", topic, ext_topic)):
        owner = account_of_arn(value) or account_of_bucket(value) or "?"
        report.say(f"  {label:<18} {value}  ->  " + (f"EXTERNAL, owned by account {owner} (the platform)" if external else "local to this stack"))

    report.section("Public path: API Gateway -> VPC link -> internal ALB -> ECS task")
    url = outputs.get("FrontendApiUrl", "")
    code, body = http("GET", f"{url}/health", timeout=30)
    if code == 200:
        health = json.loads(body)
        report.add("PASS", "API /health", f"HTTP 200 from task {health.get('instance', '?')}; model {health.get('llm_model')}",
                   "a request from the internet reached a running container through API Gateway and the load balancer")
        if health.get("llm_configured") and health.get("owm_configured"):
            report.add("PASS", "API keys injected", "LLM and OpenWeatherMap keys are present",
                       "Secrets Manager (or the task environment) delivered the keys to the container")
        else:
            report.add("FAIL", "API keys injected", "llm_configured/owm_configured is false",
                       "the container started but did not receive its keys", "check the task's Secrets Manager permissions (UseSecretsManager=false is the fallback)")
    else:
        report.add("FAIL", "API /health", f"HTTP {code}: {body[:120]}", "the public URL does not reach a healthy container",
                   "run 'deploy.py status' and check the ECS service, target health and alarms")

    report.section("Compute: ECS Fargate and the load balancer")
    svc = aws.json("ecs", "describe-services", "--cluster", outputs["ClusterName"], "--services", outputs["ServiceName"])["services"][0]
    running, desired = svc["runningCount"], svc["desiredCount"]
    report.add("PASS" if running >= 1 and running == desired else "FAIL" if running == 0 else "WARN", "ECS service",
               f"{svc['status']}, running {running} / desired {desired}",
               "all wanted tasks are running" if running == desired and running else "tasks are missing; the service is stopped, starting, or crash-looping")
    tg = res.get("TargetGroup", {}).get("PhysicalResourceId")
    if tg:
        targets = aws.json("elbv2", "describe-target-health", "--target-group-arn", tg)["TargetHealthDescriptions"]
        states = [t["TargetHealth"]["State"] for t in targets]
        report.add("PASS" if "healthy" in states else "FAIL", "ALB targets", ", ".join(states) or "no targets",
                   f"the load balancer sees {states.count('healthy')} healthy task(s) and sends traffic only to those")

    report.section("Storage: S3 (logs and Transcribe input)")
    if logs_bucket and not ext_logs:
        check_bucket(report, aws, logs_bucket, "logs", "local bucket for ALB access logs and daily CloudWatch exports")
    elif logs_bucket:
        report.say(f"logs bucket is in account {account_of_bucket(logs_bucket)}: this account cannot read its settings, only the listing the platform policy allows")
    if logs_bucket:
        for prefix, what, when in (("alb/", "ALB access logs", "delivered about every 5 minutes once there is traffic"),
                                   ("exports/", "CloudWatch log exports", "the daily export runs at 00:15 UTC; use --invoke to run it now")):
            n = count_objects(aws, logs_bucket, prefix)
            if n is None:
                report.add("WARN", f"S3 {what}", "this account is not allowed to list that prefix",
                           "the platform bucket policy has no ListBucket statement for this account, so delivery cannot be verified from here",
                           "verify from the platform side: python scripts/smoke_test.py platform <platform env>")
            else:
                report.add("PASS" if n else "WARN", f"S3 {what}", f"{n} object(s) under {prefix}" if n else f"none yet ({when})",
                           "logs are arriving in the bucket" if n else "")
    if stt_bucket and not ext_stt:
        check_bucket(report, aws, stt_bucket, "Transcribe input", "short-lived audio storage (objects expire after 1 day)")
    elif stt_bucket:
        report.say(f"transcribe bucket {stt_bucket} lives in account {account_of_bucket(stt_bucket)}; run: python scripts/notify_test.py link {args.env}")

    report.section("Monitoring: CloudWatch logs and alarms")
    check_recent_logs(report, aws, outputs.get("AppLogGroupName", ""), "agent container", 24)
    alarms = aws.json("cloudwatch", "describe-alarms", "--alarm-name-prefix", stack)["MetricAlarms"]
    firing = [a["AlarmName"] for a in alarms if a["StateValue"] == "ALARM"]
    report.add("FAIL" if firing else "PASS" if alarms else "WARN", "CloudWatch alarms", f"{len(alarms)} alarms, in ALARM: {', '.join(firing) or 'none'}",
               "none of the health/latency/error alarms is firing" if alarms and not firing else "")
    if alarms and topic:
        wired = [a for a in alarms if topic in a.get("AlarmActions", [])]
        owner = account_of_arn(topic)
        report.add("PASS" if len(wired) == len(alarms) else "FAIL", "alarm -> SNS wiring",
                   f"{len(wired)} of {len(alarms)} alarms notify {topic}",
                   f"when an alarm fires it publishes to the topic in account {owner}" + (" (another account: the platform)" if owner != who["account"] else ""))

    report.section("Scheduled job: EventBridge -> log-export Lambda")
    export_fn = res.get("LogExportFunction", {}).get("PhysicalResourceId")
    if export_fn:
        conf = aws.json("lambda", "get-function-configuration", "--function-name", export_fn)
        check_rule_for(report, aws, conf["FunctionArn"], "log export")
        dest = (conf.get("Environment", {}).get("Variables", {}) or {}).get("BUCKET")
        report.add("PASS" if dest == logs_bucket else "FAIL", "export destination", f"exports go to {dest}",
                   "the daily export writes yesterday's logs to the same bucket the stack reports as its log bucket")
    else:
        report.add("SKIP", "EventBridge log export", "ExportLogsToS3 is off")

    report.section("Notifications: SNS")
    if topic and account_of_arn(topic) == who["account"]:
        check_sns_local(report, aws, topic, "alarm topic")
    elif topic:
        report.add("SKIP", "SNS subscribers", f"topic belongs to account {account_of_arn(topic)} (the platform)",
                   "subscribers can only be listed by the topic's owner; run: python scripts/smoke_test.py platform <platform env>")

    if args.query:
        report.section("End to end: one real question")
        started = time.time()
        code, body = http("POST", f"{url}/query", {"text": "What is the weather in Paris right now?", "lang": "en"}, timeout=90)
        ok = code == 200 and json.loads(body).get("response_text")
        report.add("PASS" if ok else "FAIL", "/query", f"HTTP {code} in {time.time() - started:.1f}s",
                   "the whole chain works: API -> ALB -> agent -> LLM -> OpenWeatherMap -> answer" if ok else body[:140])

    if args.invoke:
        report.section("Active tests (these change things, harmlessly)")
        if export_fn:
            ok, detail = invoke_lambda(aws, export_fn, {"days_back": 0})
            report.add("PASS" if ok else "FAIL", "log export Lambda (invoked now)", detail[:160],
                       "CloudWatch was asked to export today's logs; the Lambda's role and the bucket policy decide whether it succeeds")
            if ok and logs_bucket:
                time.sleep(5)
                n = count_objects(aws, logs_bucket, "exports/")
                report.add("PASS" if n else "WARN", "S3 exports after invoke", f"{n} object(s)" if n else "none visible yet",
                           "" if n else "export tasks can take a minute; re-run without --invoke")
        if topic:
            try:
                aws.mutate("sns", "publish", "--topic-arn", topic, "--subject", "Weather Buddy smoke test",
                           "--message", f"Test message from scripts/smoke_test.py (account {who['account']}) at {datetime.now(timezone.utc).isoformat()}")
                report.add("PASS", "SNS test message published", topic, "this account is allowed to publish to the topic (cross-account if it belongs to the platform)")
            except deploy.DeployError as exc:
                report.add("FAIL", "SNS test message published", str(exc)[:200], "publishing to the topic was refused",
                           "check the topic policy in the platform stack (AgentAccountPublish) and that the platform is deployed for this agent account")
    else:
        report.add("SKIP", "active tests", "re-run with --invoke to run the export Lambda and send a test SNS message")
    return report.summary()


# ---------------------------------------------------------------- platform stack
def run_platform(args) -> int:
    cfg, aws, who, envs = awsctx.open_session(args.env, "platform stack health check")
    report, stack = Report(), cfg["stack_name"]
    agent_account = deploy.agent_account_for(cfg, envs)
    report.say(f"shares S3 and SNS with the agent account {agent_account} ('{cfg['agent']}')")
    report.section("Stack")
    outputs, info = check_stack(report, aws, stack, f"python scripts/deploy.py deploy {args.env}")
    if not info:
        return report.summary()
    res = stack_resources(aws, stack)
    deployed_for = outputs.get("AgentAccountId")
    report.add("PASS" if deployed_for == agent_account else "FAIL", "agent account in the stack", f"stack was deployed for {deployed_for}",
               "the resource policies below name the account that runs your agent" if deployed_for == agent_account
               else f"environments.json says the agent is {agent_account}; the policies would allow the wrong account",
               "" if deployed_for == agent_account else f"python scripts/deploy.py deploy {args.env}")

    report.section("S3 buckets")
    logs, stt = outputs.get("LogsBucketName"), outputs.get("SttBucketName")
    if logs and check_bucket(report, aws, logs, "logs", "central archive for the agent's ALB access logs and daily CloudWatch exports"):
        check_bucket_policy(report, aws, logs, "logs", agent_account, "the agent's load balancer and CloudWatch may write logs here")
        for prefix, what in ((f"alb/AWSLogs/{agent_account}/", "agent ALB access logs"), ("exports/", "agent CloudWatch exports")):
            n = count_objects(aws, logs, prefix)
            report.add("PASS" if n else "WARN", f"S3 {what}", f"{n} object(s) under {prefix}" if n else f"none yet under {prefix}",
                       "the other account is delivering logs into this account's bucket: cross-account S3 works" if n
                       else "nothing has arrived yet: deploy the agent linked to this stack and send some traffic (ALB logs arrive about every 5 min; exports run 00:15 UTC)")
    if stt and check_bucket(report, aws, stt, "Transcribe input", "temporary audio for speech-to-text, objects expire after 1 day"):
        check_bucket_policy(report, aws, stt, "Transcribe", agent_account, "the agent may put/get/delete audio under stt-input/")

    report.section("Notifications: SNS topics")
    alert, alarm = outputs.get("AlertTopicArn"), outputs.get("AlarmTopicArn")
    if alert:
        check_sns_local(report, aws, alert, "weather alert topic")
    if alarm:
        check_sns_local(report, aws, alarm, "infrastructure alarm topic")
        check_alarm_topic_policy(report, aws, alarm, agent_account)

    report.section("Scheduled alerts: EventBridge -> Lambda -> SNS")
    fn = res.get("AlertFunction", {}).get("PhysicalResourceId")
    if fn:
        conf = aws.json("lambda", "get-function-configuration", "--function-name", fn)
        check_rule_for(report, aws, conf["FunctionArn"], "daily weather alert")
        target = (conf.get("Environment", {}).get("Variables", {}) or {}).get("SNS_TOPIC_ARN")
        report.add("PASS" if target == alert else "FAIL", "alert Lambda -> topic", f"publishes to {target}",
                   "alerts found by the Lambda are published to the weather alert topic of this stack")
        check_recent_logs(report, aws, f"/aws/lambda/{fn}", "alert Lambda", 26)
    else:
        report.add("FAIL", "alert Lambda", "AlertFunction not found in the stack")

    report.section("Active tests (these change things, harmlessly)" if args.invoke else "Active tests")
    if args.invoke:
        if fn:
            ok, detail = invoke_lambda(aws, fn, {})
            report.add("PASS" if ok else "FAIL", "alert Lambda (invoked now)", (detail if detail.strip() not in ("", "null") else "ran without error")[:160],
                       "it only emails when a real alert exists, so a quiet run is normal; the test messages below prove the email path")
        for label, arn in (("alert", alert), ("alarm", alarm)):
            if arn:
                aws.mutate("sns", "publish", "--topic-arn", arn, "--subject", f"Weather Buddy smoke test ({label} topic)",
                           "--message", f"Test message from scripts/smoke_test.py at {datetime.now(timezone.utc).isoformat()}")
                report.add("PASS", f"SNS test message ({label} topic)", arn, "check the subscribed inbox if the topic has a confirmed subscriber")
    else:
        report.add("SKIP", "active tests", "re-run with --invoke to run the alert Lambda and publish test messages")
    return report.summary()


# ---------------------------------------------------------------- legacy Lambda stack (template.yaml)
def run_legacy(args) -> int:
    cfg, aws, who, envs = awsctx.open_session(args.env, "legacy Lambda stack health check", stack_name=args.stack)
    report = Report()
    report.section("Stack")
    outputs, info = check_stack(report, aws, args.stack)
    if not info:
        return report.summary()
    res = stack_resources(aws, args.stack)
    report.section("Agent endpoints")
    for label, key in (("Function URL", "AgentFunctionUrl"), ("API Gateway", "ApiUrl")):
        url = outputs.get(key)
        if not url:
            report.add("SKIP", label, f"output {key} not found")
            continue
        code, body = http("POST", url, {}, timeout=40)   # empty body: a live agent answers 400 "Missing 'text'"
        report.add("PASS" if code == 400 and "text" in body else "WARN" if code else "FAIL", f"agent via {label}", f"HTTP {code}: {body[:90]}",
                   "the Lambda is alive (an empty request is rejected with 400, as expected)" if code == 400 else "")
    report.section("Notifications and schedule")
    topic = res.get("AlertTopic", {}).get("PhysicalResourceId")
    alert_fn = res.get("AlertFunction", {}).get("PhysicalResourceId")
    if topic:
        check_sns_local(report, aws, topic, "weather alert topic")
    else:
        report.add("FAIL", "SNS alert topic", "AlertTopic not found in the stack")
    if alert_fn:
        arn = aws.json("lambda", "get-function", "--function-name", alert_fn)["Configuration"]["FunctionArn"]
        check_rule_for(report, aws, arn, "daily alert")
        check_recent_logs(report, aws, f"/aws/lambda/{alert_fn}", "alert function", 26)
    else:
        report.add("FAIL", "alert Lambda", "AlertFunction not found in the stack")
    if args.invoke:
        report.section("Active tests (these change things, harmlessly)")
        if alert_fn:
            ok, detail = invoke_lambda(aws, alert_fn, {})
            report.add("PASS" if ok else "FAIL", "alert Lambda (invoked now)", (detail if detail.strip() not in ("", "null") else "ran without error")[:160],
                       "it only emails when an alert exists, so a quiet run is normal")
        if topic:
            aws.mutate("sns", "publish", "--topic-arn", topic, "--subject", "Weather Buddy smoke test",
                       "--message", f"Test message from scripts/smoke_test.py at {datetime.now(timezone.utc).isoformat()}")
            report.add("PASS", "SNS test message published", topic, "check the subscribed inbox")
    else:
        report.add("SKIP", "active tests", "re-run with --invoke to run the alert Lambda and send a test SNS message")
    return report.summary()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="kind", required=True)
    agent = sub.add_parser("agent", aliases=["container"], help="the agent stack (infra/container.yaml)")
    platform = sub.add_parser("platform", help="the platform stack (infra/platform.yaml)")
    legacy = sub.add_parser("legacy", help="the older Lambda stack (template.yaml)")
    for p in (agent, platform, legacy):
        p.add_argument("env", help="environment name from infra/environments.json (selects profile and region)")
        p.add_argument("--invoke", action="store_true", help="run the Lambda and publish a test SNS message (changes things, harmlessly)")
    agent.add_argument("--query", action="store_true", help="also send one real /query (spends one LLM call)")
    legacy.add_argument("--stack", required=True, help="CloudFormation stack name of the old Lambda stack")
    args = parser.parse_args(argv)
    runner = {"agent": run_agent, "container": run_agent, "platform": run_platform, "legacy": run_legacy}[args.kind]
    try:
        return runner(args)
    except deploy.DeployError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

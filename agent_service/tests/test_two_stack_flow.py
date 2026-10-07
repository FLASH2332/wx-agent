"""Two-stack deployment (agent account + platform account): planning, linking, and the test scripts' output.

AWS is replaced by `FakeAws`, which answers `aws <service> <command>` calls with canned, realistic JSON, so these tests run
the real code of scripts/smoke_test.py, scripts/notify_test.py and scripts/deploy.py end to end without any account.
"""

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import awsctx  # noqa: E402
import deploy  # noqa: E402
import load_test  # noqa: E402
import notify_test  # noqa: E402
import smoke_test  # noqa: E402

AGENT = "057016988906"
PLAT = "111122223333"
REGION = "us-east-1"
LOGS = f"wb-lab-existing-logs-{PLAT}-{REGION}"
STT = f"wb-lab-existing-stt-{PLAT}-{REGION}"
ALARM_TOPIC = f"arn:aws:sns:{REGION}:{PLAT}:wb-lab-existing-infra-alarms"
ALERT_TOPIC = f"arn:aws:sns:{REGION}:{PLAT}:wb-lab-existing-weather-alerts"
NOW_MS = lambda: int(time.time() * 1000)  # noqa: E731


# ---------------------------------------------------------------- fake AWS
class FakeAws:
    """json(): canned answers keyed by the first two CLI words. mutate(): recorded, with optional handlers."""

    def __init__(self, responses, mutators=None):
        self.responses, self.mutators = responses, mutators or {}
        self.calls, self.mutations = [], []
        self.cfg = {}

    def json(self, *args, check=True):
        self.calls.append(args)
        key = tuple(args[:2])
        if key not in self.responses:
            raise AssertionError(f"unexpected read: aws {' '.join(args)}")
        value = self.responses[key]
        value = value(args) if callable(value) else value
        if isinstance(value, Exception):
            if check:
                raise value
            return None
        return value

    def mutate(self, *args):
        self.mutations.append(args)
        handler = self.mutators.get(tuple(args[:2]))
        return handler(args) if handler else "{}"


def session(monkeypatch, env, fake, account, expected=None):
    """Patch awsctx.open_session so a script runs against `fake` while still printing the real banner."""
    envs = deploy.load_environments()
    cfg = deploy.get_environment(env, envs)
    cfg["expected_account"] = expected or account
    who = {"account": account, "arn": f"arn:aws:sts::{account}:assumed-role/voclabs/session", "principal": "voclabs"}

    def fake_open(env_name, title, *, stack_name=None, extra=None):
        awsctx.print_banner(title, cfg, who, extra, stack_name)
        return cfg, fake, who, envs

    monkeypatch.setattr(awsctx, "open_session", fake_open)
    monkeypatch.setattr(notify_test.time, "sleep", lambda s: None)
    return cfg, who


def policy(*statements):
    return json.dumps({"Version": "2012-10-17", "Statement": list(statements)})


LOGS_POLICY = policy(
    {"Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::127311923021:root"}, "Action": "s3:PutObject",
     "Resource": f"arn:aws:s3:::{LOGS}/alb/AWSLogs/{AGENT}/*"},
    {"Effect": "Allow", "Principal": {"Service": "logs.us-east-1.amazonaws.com"}, "Action": "s3:PutObject",
     "Condition": {"StringEquals": {"aws:SourceAccount": AGENT}}},
    {"Effect": "Allow", "Principal": {"AWS": f"arn:aws:iam::{AGENT}:root"}, "Action": "s3:ListBucket"})
STT_POLICY = policy({"Effect": "Allow", "Principal": {"AWS": f"arn:aws:iam::{AGENT}:root"}, "Action": ["s3:PutObject", "s3:GetObject"]})
ALARM_POLICY = policy(
    {"Effect": "Allow", "Principal": {"AWS": "*"}, "Action": "SNS:Publish", "Condition": {"StringEquals": {"AWS:SourceOwner": PLAT}}},
    {"Effect": "Allow", "Principal": {"Service": "cloudwatch.amazonaws.com"}, "Action": "sns:Publish",
     "Condition": {"StringEquals": {"aws:SourceAccount": AGENT}}},
    {"Effect": "Allow", "Principal": {"AWS": f"arn:aws:iam::{AGENT}:root"}, "Action": "sns:Publish"})
PAB = {"PublicAccessBlockConfiguration": {k: True for k in ("BlockPublicAcls", "BlockPublicPolicy", "IgnorePublicAcls", "RestrictPublicBuckets")}}


def platform_responses():
    return {
        ("cloudformation", "describe-stacks"): {"Stacks": [{"StackStatus": "CREATE_COMPLETE", "Parameters": [], "Outputs": [
            {"OutputKey": "AgentAccountId", "OutputValue": AGENT}, {"OutputKey": "LogsBucketName", "OutputValue": LOGS},
            {"OutputKey": "SttBucketName", "OutputValue": STT}, {"OutputKey": "AlarmTopicArn", "OutputValue": ALARM_TOPIC},
            {"OutputKey": "AlertTopicArn", "OutputValue": ALERT_TOPIC}, {"OutputKey": "AlertFunctionName", "OutputValue": "fn-alert"}]}]},
        ("cloudformation", "list-stack-resources"): {"StackResourceSummaries": [
            {"LogicalResourceId": "AlertFunction", "PhysicalResourceId": "fn-alert"}]},
        ("s3api", "get-bucket-location"): {"LocationConstraint": None},
        ("s3api", "get-public-access-block"): PAB,
        ("s3api", "get-bucket-policy"): lambda a: {"Policy": LOGS_POLICY if LOGS in a else STT_POLICY},
        ("s3api", "list-objects-v2"): {"Contents": [{"Key": f"alb/AWSLogs/{AGENT}/x.log"}]},
        ("sns", "list-subscriptions-by-topic"): {"Subscriptions": [
            {"Protocol": "email", "Endpoint": "someone@example.com", "SubscriptionArn": f"arn:aws:sns:{REGION}:{PLAT}:t:abc"}]},
        ("sns", "get-topic-attributes"): {"Attributes": {"Policy": ALARM_POLICY}},
        ("lambda", "get-function-configuration"): {"FunctionArn": f"arn:aws:lambda:{REGION}:{PLAT}:function:fn-alert",
                                                   "Environment": {"Variables": {"SNS_TOPIC_ARN": ALERT_TOPIC}}},
        ("lambda", "get-function"): {"Configuration": {"FunctionArn": f"arn:aws:lambda:{REGION}:{PLAT}:function:fn-alert",
                                                       "Runtime": "python3.12", "LastModified": "2026-10-07T01:00:00.000+0000"}},
        ("lambda", "get-policy"): {"Policy": policy({"Effect": "Allow", "Principal": {"Service": "events.amazonaws.com"}})},
        ("events", "list-rule-names-by-target"): {"RuleNames": ["wb-AlertFunctionDailySchedule-ABC"]},
        ("events", "describe-rule"): {"State": "ENABLED", "ScheduleExpression": "cron(30 1 * * ? *)"},
        ("events", "list-targets-by-rule"): {"Targets": [{"Id": "1", "Arn": f"arn:aws:lambda:{REGION}:{PLAT}:function:fn-alert"}]},
        # 2 invocations in 48 h, and no failed invocations / errors
        ("cloudwatch", "get-metric-statistics"): lambda a: {"Datapoints": [] if any(m in a for m in ("FailedInvocations", "Errors")) else [{"Sum": 2.0}]},
        ("logs", "describe-log-streams"): lambda a: {"logStreams": [{"lastEventTimestamp": NOW_MS()}]},
    }


def agent_stack(external=True):
    params = ([{"ParameterKey": "ExternalLogsBucketName", "ParameterValue": LOGS}, {"ParameterKey": "ExternalSttBucketName", "ParameterValue": STT},
               {"ParameterKey": "ExternalAlarmTopicArn", "ParameterValue": ALARM_TOPIC}] if external else [])
    return {"Stacks": [{"StackStatus": "UPDATE_COMPLETE", "Parameters": params, "Outputs": [
        {"OutputKey": "FrontendApiUrl", "OutputValue": "https://abc.execute-api.us-east-1.amazonaws.com"},
        {"OutputKey": "ClusterName", "OutputValue": "weatherbuddy-lab-new"}, {"OutputKey": "ServiceName", "OutputValue": "weatherbuddy-lab-new"},
        {"OutputKey": "LogsBucketName", "OutputValue": LOGS}, {"OutputKey": "SttBucketName", "OutputValue": STT},
        {"OutputKey": "AlarmTopicArn", "OutputValue": ALARM_TOPIC}, {"OutputKey": "AppLogGroupName", "OutputValue": "/ecs/weatherbuddy-lab-new"}]}]}


def agent_responses():
    alarm = {"AlarmName": "weatherbuddy-container-CpuHighAlarm-AB12", "StateValue": "OK", "ActionsEnabled": True, "AlarmActions": [ALARM_TOPIC]}
    return {
        ("cloudformation", "describe-stacks"): agent_stack(),
        ("cloudformation", "list-stack-resources"): {"StackResourceSummaries": [
            {"LogicalResourceId": "TargetGroup", "PhysicalResourceId": "arn:tg"}, {"LogicalResourceId": "LogExportFunction", "PhysicalResourceId": "fn-export"}]},
        ("ecs", "describe-services"): {"services": [{"status": "ACTIVE", "runningCount": 1, "desiredCount": 1, "pendingCount": 0}]},
        ("elbv2", "describe-target-health"): {"TargetHealthDescriptions": [{"TargetHealth": {"State": "healthy"}}]},
        ("s3api", "list-objects-v2"): {"Contents": [{"Key": "alb/AWSLogs/x"}]},
        ("logs", "describe-log-streams"): lambda a: {"logStreams": [{"lastEventTimestamp": NOW_MS()}]},
        ("cloudwatch", "describe-alarms"): {"MetricAlarms": [alarm, {**alarm, "AlarmName": "weatherbuddy-container-Alb5xxAlarm-CD34"}]},
        ("lambda", "get-function-configuration"): {"FunctionArn": f"arn:aws:lambda:{REGION}:{AGENT}:function:fn-export",
                                                   "Environment": {"Variables": {"BUCKET": LOGS}}},
        ("events", "list-rule-names-by-target"): {"RuleNames": ["wb-LogExportFunctionDaily-XYZ"]},
        ("events", "describe-rule"): {"State": "ENABLED", "ScheduleExpression": "cron(15 0 * * ? *)"},
    }


def output(capsys):
    return capsys.readouterr().out


# ---------------------------------------------------------------- deploy: two linked stacks
def test_environments_describe_two_linked_stacks():
    envs = deploy.load_environments()
    agent, platform = deploy.get_environment("lab-new", envs), deploy.get_environment("lab-existing", envs)
    assert (agent["stack"], platform["stack"]) == ("agent", "platform")
    assert agent["platform"] == "lab-existing" and platform["agent"] == "lab-new"
    assert deploy.agent_account_for(platform, envs) == AGENT


def test_platform_needs_the_agent_account_id():
    envs = {"plat": {"stack": "platform", "agent": "agnt", "profile": "x", "region": "r", "stack_name": "s"},
            "agnt": {"stack": "agent", "profile": "y", "region": "r", "stack_name": "s", "expected_account": None}}
    with pytest.raises(deploy.DeployError, match="expected_account"):
        deploy.agent_account_for(deploy.get_environment("plat", envs), envs)


def test_unknown_stack_kind_is_rejected():
    with pytest.raises(deploy.DeployError, match="stack must be"):
        deploy.get_environment("x1", {"x1": {"stack": "weird", "profile": "p", "region": "r", "stack_name": "s"}})


def test_agent_parameters_switch_to_the_platform_resources_only_when_linked():
    cfg = deploy.get_environment("lab-new")
    secrets = {"OWM_API_KEY": "k", "LLM_MODEL_ID": "groq/x"}
    alone = deploy.build_parameter_overrides(cfg, image_uri="i", vpc_id="v", subnet_ids=["a", "b"], secrets=secrets)
    linked = deploy.build_parameter_overrides(cfg, image_uri="i", vpc_id="v", subnet_ids=["a", "b"], secrets=secrets,
                                              platform_outputs={"LogsBucketName": LOGS, "SttBucketName": STT, "AlarmTopicArn": ALARM_TOPIC})
    assert not any(k.startswith("External") for k in alone)
    assert (linked["ExternalLogsBucketName"], linked["ExternalSttBucketName"], linked["ExternalAlarmTopicArn"]) == (LOGS, STT, ALARM_TOPIC)


def test_sam_command_picks_the_template_and_tag_of_each_stack_kind():
    agent = deploy.build_sam_deploy_command("sam", deploy.get_environment("lab-new"), {})
    platform = deploy.build_sam_deploy_command("sam", deploy.get_environment("lab-existing"), {})
    assert agent[agent.index("--template-file") + 1].endswith("container.yaml") and "Stack=agent" in agent
    assert platform[platform.index("--template-file") + 1].endswith("platform.yaml") and "Stack=platform" in platform


def test_saved_state_round_trips_and_a_missing_one_is_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(deploy, "STATE_DIR", tmp_path / "state")
    assert deploy.load_state("lab-existing") == {}
    deploy.save_state("lab-existing", {"LogsBucketName": LOGS}, PLAT)
    state = deploy.load_state("lab-existing")
    assert state["outputs"] == {"LogsBucketName": LOGS} and state["account"] == PLAT and state["saved_at"]


def test_link_resolution_uses_saved_state_standalone_flag_and_explains_itself(monkeypatch, tmp_path):
    monkeypatch.setattr(deploy, "STATE_DIR", tmp_path)
    envs, cfg = deploy.load_environments(), deploy.get_environment("lab-new")
    outputs, note = deploy.resolve_platform_outputs(cfg, envs, standalone=False, offline=True)
    assert outputs == {} and "STANDALONE for now" in note and "deploy lab-existing" in note
    deploy.save_state("lab-existing", {"LogsBucketName": LOGS})
    outputs, note = deploy.resolve_platform_outputs(cfg, envs, standalone=False, offline=True)
    assert outputs["LogsBucketName"] == LOGS and note.startswith("LINKED to platform 'lab-existing'")
    outputs, note = deploy.resolve_platform_outputs(cfg, envs, standalone=True, offline=True)
    assert outputs == {} and "--standalone" in note


def test_aws_failures_are_classified_and_explained_with_the_exact_fix():
    assert deploy.classify_aws_failure("An error occurred (ExpiredToken) when calling ...") == "expired"
    assert deploy.classify_aws_failure("The config profile (wb-existing) could not be found") == "no_profile"
    assert deploy.classify_aws_failure("Unable to locate credentials") == "no_credentials"
    assert deploy.classify_aws_failure("... is not authorized to perform: polly:SynthesizeSpeech") == "denied"
    assert deploy.classify_aws_failure("some other problem") == "other"
    assert "set_lab_credentials.py wb-new" in deploy.explain_aws_error("ExpiredToken", "wb-new") and "EXPIRED" in deploy.explain_aws_error("ExpiredToken", "wb-new")
    assert deploy.explain_aws_error("fine", "wb-new") == ""


def test_platform_dry_run_is_offline_masks_secrets_and_names_the_agent_account(monkeypatch, capsys):
    monkeypatch.setattr(deploy, "read_secrets", lambda: {"OWM_API_KEY": "owm-secret", "LLM_MODEL_ID": "groq/x"})
    assert deploy.main(["deploy", "lab-existing", "--dry-run"]) == 0
    out = output(capsys)
    assert "platform.yaml" in out and f"AgentAccountId={AGENT}" in out and "OwmApiKey=***" in out and "owm-secret" not in out
    assert "docker" not in out.lower().replace("platform", "")        # the platform stack builds no image


def test_agent_dry_run_links_when_the_platform_was_deployed_and_not_with_standalone(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(deploy, "STATE_DIR", tmp_path)
    monkeypatch.setattr(deploy, "read_secrets", lambda: {"OWM_API_KEY": "k", "LLM_API_KEY": "llm-secret", "LLM_MODEL_ID": "groq/x"})
    deploy.save_state("lab-existing", {"LogsBucketName": LOGS, "SttBucketName": STT, "AlarmTopicArn": ALARM_TOPIC})
    assert deploy.main(["deploy", "lab-new", "--dry-run"]) == 0
    linked = output(capsys)
    assert "LINKED to platform 'lab-existing'" in linked and f"ExternalLogsBucketName={LOGS}" in linked and "llm-secret" not in linked
    assert deploy.main(["deploy", "lab-new", "--dry-run", "--standalone"]) == 0
    alone = output(capsys)
    assert "STANDALONE" in alone and "ExternalLogsBucketName" not in alone


def test_accounts_command_reports_valid_expired_and_missing_profiles(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(deploy, "STATE_DIR", tmp_path)

    def fake_run(cmd, **kw):
        profile = cmd[cmd.index("--profile") + 1]
        if profile == "wb-new":
            return SimpleNamespace(returncode=0, stdout=json.dumps({"Account": AGENT, "Arn": f"arn:aws:sts::{AGENT}:assumed-role/voclabs/s"}), stderr="")
        return SimpleNamespace(returncode=255, stdout="", stderr="The config profile (wb-existing) could not be found")

    monkeypatch.setattr(deploy.subprocess, "run", fake_run)
    assert deploy.cmd_accounts(SimpleNamespace()) == 1                      # one problem -> non-zero
    out = output(capsys)
    assert f"OK       account {AGENT} as voclabs" in out
    assert "MISSING  run: python scripts/set_lab_credentials.py wb-existing" in out
    assert "platform not deployed yet" in out


# ---------------------------------------------------------------- awsctx: banner, report, policy helpers
def test_banner_names_account_role_region_stack_and_the_expected_account(capsys):
    cfg = deploy.get_environment("lab-new")
    who = {"account": AGENT, "arn": "x", "principal": "voclabs"}
    awsctx.print_banner("demo", cfg, who)
    out = output(capsys)
    assert f"AWS account : {AGENT}" in out and "profile 'wb-new'" in out and "signed in as voclabs" in out and "us-east-1" in out
    assert "matches environments.json" in out and "weatherbuddy-container" in out and "agent stack" in out


def test_report_prints_meaning_always_and_fix_only_for_problems(capsys):
    report = awsctx.Report()
    report.add("PASS", "good", "fine", "all is well", "unused fix")
    report.add("FAIL", "bad", "broken", "something is off", "do this")
    out = output(capsys)
    assert "what this means: all is well" in out and "fix: do this" in out and "unused fix" not in out
    assert report.summary() == 1 and "FAILED  bad" in output(capsys)


def test_policy_and_name_helpers():
    assert awsctx.policy_principal_accounts(LOGS_POLICY) == {"127311923021", AGENT}
    assert awsctx.policy_principal_accounts(policy({"Effect": "Deny", "Principal": {"AWS": f"arn:aws:iam::{PLAT}:root"}})) == set()
    assert awsctx.policy_services(ALARM_POLICY) == {"cloudwatch.amazonaws.com"}
    assert awsctx.account_of_arn(ALARM_TOPIC) == PLAT and awsctx.account_of_arn("not an arn") is None
    assert awsctx.account_of_bucket(LOGS) == PLAT and awsctx.account_of_bucket("plain-bucket") is None


# ---------------------------------------------------------------- smoke test of the platform account
def test_platform_smoke_test_names_the_account_and_proves_the_cross_account_policies(monkeypatch, capsys):
    session(monkeypatch, "lab-existing", FakeAws(platform_responses()), PLAT)
    assert smoke_test.run_platform(SimpleNamespace(env="lab-existing", invoke=False)) == 0
    out = output(capsys)
    assert f"AWS account : {PLAT}" in out and f"shares S3 and SNS with the agent account {AGENT}" in out
    assert f"S3 logs policy allows agent account {AGENT}" in out and "S3 Transcribe policy allows agent account" in out
    assert "cross-account S3 works" in out                                  # agent logs found in this account's bucket
    assert "SNS alarm topic policy" in out and "allows CloudWatch alarms from the agent account" in out
    assert "EventBridge rule for daily weather alert" in out and "cron(30 1 * * ? *)" in out
    assert "alert Lambda -> topic" in out and "[FAIL]" not in out


def test_platform_smoke_test_fails_loudly_when_the_policy_names_the_wrong_account(monkeypatch, capsys):
    responses = platform_responses()
    responses[("s3api", "get-bucket-policy")] = {"Policy": policy({"Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::999999999999:root"}})}
    session(monkeypatch, "lab-existing", FakeAws(responses), PLAT)
    assert smoke_test.run_platform(SimpleNamespace(env="lab-existing", invoke=False)) == 1
    out = output(capsys)
    assert "[FAIL] S3 logs policy allows agent account" in out and "999999999999" in out and "AccessDenied" in out


def test_platform_smoke_invoke_runs_the_lambda_and_publishes_to_both_topics(monkeypatch, capsys):
    fake = FakeAws(platform_responses(), {("lambda", "invoke"): lambda a: '{"StatusCode": 200}', ("sns", "publish"): lambda a: '{"MessageId": "m-1"}'})
    session(monkeypatch, "lab-existing", fake, PLAT)
    assert smoke_test.run_platform(SimpleNamespace(env="lab-existing", invoke=True)) == 0
    published = [m[m.index("--topic-arn") + 1] for m in fake.mutations if m[:2] == ("sns", "publish")]
    assert sorted(published) == sorted([ALERT_TOPIC, ALARM_TOPIC]) and any(m[:2] == ("lambda", "invoke") for m in fake.mutations)


# ---------------------------------------------------------------- smoke test of the agent account (linked)
def test_agent_smoke_test_explains_that_s3_and_sns_live_in_the_other_account(monkeypatch, capsys):
    fake = FakeAws(agent_responses(), {("sns", "publish"): lambda a: '{"MessageId": "m"}'})
    session(monkeypatch, "lab-new", fake, AGENT)
    monkeypatch.setattr(smoke_test, "http", lambda m, u, b=None, timeout=60: (200, json.dumps(
        {"status": "ok", "instance": "task-1", "llm_model": "groq/x", "llm_configured": True, "owm_configured": True})))
    assert smoke_test.run_agent(SimpleNamespace(env="lab-new", query=False, invoke=True)) == 0
    out = output(capsys)
    assert f"AWS account : {AGENT}" in out and f"EXTERNAL, owned by account {PLAT}" in out
    assert "2 of 2 alarms notify" in out and "(another account: the platform)" in out
    assert "SNS subscribers" in out and "subscribers can only be listed by the topic's owner" in out
    assert not any(c[:2] == ("s3api", "get-bucket-location") for c in fake.calls)     # not this account's bucket: never probed
    assert any(m[:2] == ("sns", "publish") for m in fake.mutations) and "[FAIL]" not in out


# ---------------------------------------------------------------- notify tests
def test_sns_test_on_the_platform_lists_both_topics_and_who_may_publish(monkeypatch, capsys):
    fake = FakeAws(platform_responses(), {("sns", "publish"): lambda a: '{"MessageId": "m-7"}'})
    session(monkeypatch, "lab-existing", fake, PLAT)
    args = SimpleNamespace(env="lab-existing", stack=None, topic="all", subscribe=None, publish=True, alarm_test=False, wait=1)
    assert notify_test.run_sns(args) == 0
    out = output(capsys)
    assert "Topic 'alert'" in out and "Topic 'alarm'" in out and "s***@example.com" in out and "someone@example.com" not in out
    assert f"cross-account publishers: account(s) {AGENT}" in out and "MessageId m-7" in out
    assert len([m for m in fake.mutations if m[:2] == ("sns", "publish")]) == 2


def test_agent_alarm_test_proves_an_alarm_reaches_the_topic_in_the_other_account_and_restores_state(monkeypatch, capsys):
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    responses = agent_responses()
    responses[("cloudwatch", "describe-alarm-history")] = {"AlarmHistoryItems": [
        {"Timestamp": stamp, "HistorySummary": f"Successfully executed action {ALARM_TOPIC}"}]}
    fake = FakeAws(responses)
    session(monkeypatch, "lab-new", fake, AGENT)
    args = SimpleNamespace(env="lab-new", stack=None, topic="alarm", subscribe=None, publish=False, alarm_test=True, wait=30)
    assert notify_test.run_sns(args) == 0
    out = output(capsys)
    assert f"owned by account {PLAT}" in out and "alarm CpuHighAlarm -> SNS" in out and "alarm-to-topic wiring and the topic policy work" in out
    states = [m[m.index("--state-value") + 1] for m in fake.mutations if m[:2] == ("cloudwatch", "set-alarm-state")]
    assert states == ["ALARM", "OK"]                                      # forced, then put back


def test_link_test_from_the_agent_writes_reads_and_deletes_in_the_other_accounts_bucket(monkeypatch, capsys):
    def get_object(args):
        Path(args[-1]).write_text("weather buddy link test", encoding="utf-8")
        return "{}"

    fake = FakeAws(agent_responses(), {("s3api", "get-object"): get_object, ("sns", "publish"): lambda a: '{"MessageId": "m"}'})
    session(monkeypatch, "lab-new", fake, AGENT)
    assert notify_test.run_link(SimpleNamespace(env="lab-new")) == 0
    out = output(capsys)
    assert "uses resources owned by another account" in out and "cross-account S3 works" in out
    assert "publish to the platform topic" in out and "delivery into the other account works" in out
    ops = [m[1] for m in fake.mutations if m[0] == "s3api"]
    assert ops == ["put-object", "get-object", "delete-object"] and "cleanup: test object deleted" in out


def test_link_test_reports_a_standalone_agent_as_nothing_to_link(monkeypatch, capsys):
    responses = agent_responses()
    responses[("cloudformation", "describe-stacks")] = agent_stack(external=False)
    session(monkeypatch, "lab-new", FakeAws(responses), AGENT)
    assert notify_test.run_link(SimpleNamespace(env="lab-new")) == 0
    assert "STANDALONE" in output(capsys)


def test_link_test_from_the_platform_checks_what_it_allows_and_whether_logs_arrive(monkeypatch, capsys):
    session(monkeypatch, "lab-existing", FakeAws(platform_responses()), PLAT)
    assert notify_test.run_link(SimpleNamespace(env="lab-existing")) == 0
    out = output(capsys)
    assert "What this account allows the agent account to do" in out and "the agent stack is writing into this account's bucket" in out


def test_eventbridge_test_reports_rule_permission_history_and_logs(monkeypatch, capsys):
    session(monkeypatch, "lab-existing", FakeAws(platform_responses()), PLAT)
    assert notify_test.run_eventbridge(SimpleNamespace(env="lab-existing", stack=None, live=False, wait=1)) == 0
    out = output(capsys)
    assert "the daily weather-alert check" in out and "EventBridge will invoke the Lambda at 'cron(30 1 * * ? *)'" in out
    assert "fired 2 time(s), 0 failures" in out and "resource policy allows events.amazonaws.com" in out and "[FAIL]" not in out


# ---------------------------------------------------------------- load test narration
def _state(running=1, desired=1, pending=0, healthy=1, alarms=()):
    return {"running": running, "desired": desired, "pending": pending, "healthy": healthy, "targets": healthy, "alarms": list(alarms)}


def test_load_test_narrates_scale_out_in_plain_language():
    lines = load_test.narrate(125.0, _state(), _state(desired=3, pending=2, alarms=["autoscaling-scale-out"]))
    text = "\n".join(lines)
    assert "desired task count 1 -> 3" in text and "scale OUT" in text and "2 task(s) are starting" in text
    assert "ALARM autoscaling-scale-out" in text and "ADD tasks" in text
    later = "\n".join(load_test.narrate(200.0, _state(desired=3, pending=2, alarms=["autoscaling-scale-out"]), _state(running=3, desired=3, healthy=3)))
    assert "running tasks 1 -> 3: a new task is up" in later and "healthy ALB targets 1 -> 3" in later
    assert "autoscaling-scale-out is back to OK" in later
    down = "\n".join(load_test.narrate(900.0, _state(running=3, desired=3, healthy=3), _state(running=2, desired=2, healthy=2)))
    assert "scale IN" in down and "a task was stopped by scale-in" in down
    assert load_test.narrate(10.0, _state(), _state()) == []                  # nothing changed, nothing said


# ---------------------------------------------------------------- open_session: the account safety check
def test_open_session_refuses_a_profile_that_is_the_wrong_account(monkeypatch):
    """Expired-then-repasted credentials from the OTHER lab must never be used against this environment."""
    monkeypatch.setattr(awsctx, "Aws", lambda cfg: SimpleNamespace(cfg=cfg))
    monkeypatch.setattr(awsctx, "get_identity", lambda aws: {"account": "999999999999", "arn": "x", "principal": "voclabs"})
    with pytest.raises(deploy.DeployError, match=f"expects {AGENT}"):
        awsctx.open_session("lab-new", "any test")


def test_open_session_prints_the_banner_when_the_account_matches(monkeypatch, capsys):
    monkeypatch.setattr(awsctx, "Aws", lambda cfg: SimpleNamespace(cfg=cfg))
    monkeypatch.setattr(awsctx, "get_identity", lambda aws: {"account": AGENT, "arn": "x", "principal": "voclabs"})
    cfg, aws, who, envs = awsctx.open_session("lab-new", "banner check")
    out = output(capsys)
    assert f"AWS account : {AGENT}" in out and "banner check" in out and cfg["name"] == "lab-new" and "lab-existing" in envs


def test_every_test_script_opens_its_session_through_the_account_check():
    """smoke_test, notify_test and load_test must all go through awsctx.open_session (banner + wrong-account refusal)."""
    for script in ("smoke_test.py", "notify_test.py", "load_test.py"):
        source = (SCRIPTS / script).read_text(encoding="utf-8")
        assert "open_session(" in source or "open_stack(" in source, script

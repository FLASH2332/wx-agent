"""Shared plumbing for scripts/smoke_test.py, scripts/notify_test.py and scripts/load_test.py.

Every one of those scripts starts with `open_session(...)`, which (1) signs in with the AWS CLI profile of the chosen
environment, (2) refuses to continue if that profile is not the account environments.json expects, and (3) prints a banner
that says WHICH ACCOUNT, role, region and stack the test is about to act on. Results are printed by `Report`, which adds a
"what this means" line (and, on problems, a "fix") under each check so the output explains what is happening in the account.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deploy  # noqa: E402

OK_STACK_STATES = {"CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"}
RULE = "=" * 78


# ---------------------------------------------------------------- reporting
@dataclass
class Check:
    status: str          # PASS | WARN | FAIL | SKIP
    name: str
    detail: str = ""
    meaning: str = ""
    fix: str = ""


class Report:
    def __init__(self):
        self.checks: list[Check] = []

    def section(self, title: str) -> None:
        print(f"\n  -- {title} " + "-" * max(4, 70 - len(title)))

    def say(self, text: str) -> None:
        print(f"         {text}")

    def add(self, status: str, name: str, detail: str = "", meaning: str = "", fix: str = "") -> None:
        self.checks.append(Check(status, name, detail, meaning, fix))
        print(f"  [{status:4}] {name}{': ' + detail if detail else ''}")
        if meaning:
            print(f"         what this means: {meaning}")
        if fix and status in ("WARN", "FAIL"):
            print(f"         fix: {fix}")

    def summary(self) -> int:
        counts = {s: sum(1 for c in self.checks if c.status == s) for s in ("PASS", "WARN", "FAIL", "SKIP")}
        print(f"\n  RESULT: {counts['PASS']} passed, {counts['WARN']} warnings, {counts['FAIL']} failed, {counts['SKIP']} skipped")
        for c in self.checks:
            if c.status == "FAIL":
                print(f"    FAILED  {c.name}: {c.detail}")
        return 1 if counts["FAIL"] else 0


# ---------------------------------------------------------------- pure helpers (unit-tested)
def classify_subscriptions(subscriptions: list[dict]) -> tuple[str, str]:
    if not subscriptions:
        return "WARN", "topic has no subscribers (no email configured, so nobody is notified)"
    pending = [s for s in subscriptions if str(s.get("SubscriptionArn", "")).startswith("PendingConfirmation")]
    confirmed = len(subscriptions) - len(pending)
    if confirmed == 0:
        return "WARN", f"{len(pending)} subscription(s) waiting for the confirmation email link"
    suffix = f", {len(pending)} still pending" if pending else ""
    return "PASS", f"{confirmed} confirmed subscriber(s){suffix}"


def age_hours(epoch_ms: int | None, now: float | None = None) -> float | None:
    if not epoch_ms:
        return None
    return ((now if now is not None else time.time()) * 1000 - epoch_ms) / 3_600_000


def fmt_age(hours: float | None) -> str:
    return "never" if hours is None else (f"{hours * 60:.0f} min ago" if hours < 2 else f"{hours:.1f} h ago")


def account_of_arn(arn: str | None) -> str | None:
    match = re.match(r"^arn:aws[a-z-]*:[a-z0-9-]*:[a-z0-9-]*:(\d{12}):", arn or "")
    return match.group(1) if match else None


def account_of_bucket(name: str | None) -> str | None:
    """Our bucket names embed the owner: wb-<env>-logs-<account>-<region>."""
    match = re.search(r"-(\d{12})-[a-z0-9-]+$", name or "")
    return match.group(1) if match else None


def mask_endpoint(endpoint: str) -> str:
    """me@example.com -> m***@example.com (other endpoints are shortened)."""
    if "@" in endpoint:
        name, _, domain = endpoint.partition("@")
        return f"{name[:1]}***@{domain}"
    return endpoint if len(endpoint) <= 24 else endpoint[:12] + "..." + endpoint[-8:]


def policy_principal_accounts(policy_json: str) -> set[str]:
    """Every 12-digit account that an Allow statement of a resource policy names (AWS principals and aws:SourceAccount)."""
    accounts: set[str] = set()
    try:
        statements = json.loads(policy_json).get("Statement", [])
    except ValueError:
        return accounts
    for st in statements if isinstance(statements, list) else [statements]:
        if st.get("Effect") != "Allow":
            continue
        blob = json.dumps({"p": st.get("Principal"), "c": st.get("Condition")})
        accounts.update(re.findall(r"(?<!\d)(\d{12})(?!\d)", blob))
    return accounts


def policy_services(policy_json: str) -> set[str]:
    services: set[str] = set()
    try:
        statements = json.loads(policy_json).get("Statement", [])
    except ValueError:
        return services
    for st in statements if isinstance(statements, list) else [statements]:
        principal = st.get("Principal", {})
        service = principal.get("Service") if isinstance(principal, dict) else None
        services.update(service if isinstance(service, list) else [service] if service else [])
    return services


# ---------------------------------------------------------------- AWS access
class Aws:
    """Thin wrapper over deploy.Runner: JSON reads, text reads and (explicitly named) mutating calls."""

    def __init__(self, env_cfg: dict):
        self.runner = deploy.Runner(env_cfg)
        self.cfg = env_cfg

    def json(self, *args: str, check: bool = True):
        out = self.runner.aws(*args, "--output", "json", check=check, readonly=True)
        return json.loads(out) if out else None

    def text(self, *args: str, check: bool = True) -> str:
        return self.runner.aws(*args, "--output", "text", check=check, readonly=True)

    def mutate(self, *args: str) -> str:
        return self.runner.aws(*args)


def http(method: str, url: str, body: dict | None = None, timeout: int = 60) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def get_identity(aws: Aws) -> dict:
    data = aws.json("sts", "get-caller-identity")
    arn = data["Arn"]
    return {"account": data["Account"], "arn": arn, "principal": arn.split("/")[1] if "/" in arn else arn}


def stack_description(env_cfg: dict) -> str:
    return {"agent": "agent stack: Docker/ECS, API Gateway, ALB, CloudWatch",
            "platform": "platform stack: S3, SNS, EventBridge alerts"}.get(env_cfg.get("stack"), "stack")


def print_banner(title: str, env_cfg: dict, who: dict, extra: list[str] | None = None, stack_name: str | None = None) -> None:
    expected = env_cfg.get("expected_account")
    print(RULE)
    print(f" Weather Buddy test: {title}")
    print(RULE)
    print(f" environment : {env_cfg['name']}  ({stack_description(env_cfg)})")
    print(f" AWS account : {who['account']}   <- profile '{env_cfg['profile']}', signed in as {who['principal']}, region {env_cfg['region']}")
    print(f" expected    : " + (f"{expected} (matches environments.json)" if expected else "not set in environments.json (set expected_account as a safety check)"))
    print(f" stack       : {stack_name or env_cfg['stack_name']}")
    for line in extra or []:
        print(f" {line}")
    print("-" * 78)


def open_session(env_name: str, title: str, *, stack_name: str | None = None, extra: list[str] | None = None):
    """Sign in, verify the account, print the banner. Returns (env_cfg, aws, identity, all_envs)."""
    envs = deploy.load_environments()
    cfg = deploy.get_environment(env_name, envs)
    aws = Aws(cfg)
    who = get_identity(aws)           # an expired/missing profile fails here with a clear fix (deploy.explain_aws_error)
    deploy.verify_account(cfg, who["account"])
    print_banner(title, cfg, who, extra, stack_name)
    return cfg, aws, who, envs


# ---------------------------------------------------------------- CloudFormation helpers
def stack_resources(aws: Aws, stack: str) -> dict[str, dict]:
    items = aws.json("cloudformation", "list-stack-resources", "--stack-name", stack)["StackResourceSummaries"]
    return {i["LogicalResourceId"]: i for i in items}


def check_stack(report: Report, aws: Aws, stack: str, fix_hint: str = "") -> tuple[dict, dict]:
    """Returns (outputs, stack info) or ({}, {}) with a FAIL when the stack does not exist."""
    data = aws.json("cloudformation", "describe-stacks", "--stack-name", stack, check=False)
    if not data:
        report.add("FAIL", "stack exists", f"'{stack}' not found in this account/region",
                   "nothing has been deployed here under that name (or it was deleted)", fix_hint)
        return {}, {}
    info = data["Stacks"][0]
    status = info["StackStatus"]
    report.add("PASS" if status in OK_STACK_STATES else "FAIL", "stack status", status,
               "CloudFormation finished creating/updating every resource" if status in OK_STACK_STATES
               else "CloudFormation did not finish cleanly; read the stack events for the first failed resource")
    return {o["OutputKey"]: o["OutputValue"] for o in info.get("Outputs") or []}, info


def stack_parameters(info: dict) -> dict:
    return {p["ParameterKey"]: p.get("ParameterValue") for p in info.get("Parameters") or []}


def check_recent_logs(report: Report, aws: Aws, log_group: str, label: str, warn_after_hours: float) -> None:
    out = aws.json("logs", "describe-log-streams", "--log-group-name", log_group, "--order-by", "LastEventTime",
                   "--descending", "--max-items", "1", check=False)
    streams = (out or {}).get("logStreams") or []
    if not streams:
        report.add("WARN", f"logs {label}", f"no log streams in {log_group} yet",
                   "the component has not written any log line yet (it has not run, or it has no traffic)")
        return
    hours = age_hours(streams[0].get("lastEventTimestamp"))
    ok = hours is not None and hours <= warn_after_hours
    report.add("PASS" if ok else "WARN", f"logs {label}", f"last event {fmt_age(hours)} in {log_group}",
               "the component is alive and writing logs" if ok else f"nothing logged for more than {warn_after_hours:g} h")


def count_objects(aws: Aws, bucket: str, prefix: str) -> int | None:
    """Number of objects (max 50) under a prefix, or None when this account may not list the bucket."""
    try:
        out = aws.json("s3api", "list-objects-v2", "--bucket", bucket, "--prefix", prefix, "--max-items", "50")
    except deploy.DeployError as exc:
        if deploy.classify_aws_failure(str(exc)) == "denied":
            return None
        raise
    return len((out or {}).get("Contents") or [])


def invoke_lambda(aws: Aws, function: str, payload: dict) -> tuple[bool, str]:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        out_file = Path(tmp) / "out.json"
        meta = aws.mutate("lambda", "invoke", "--function-name", function, "--cli-binary-format", "raw-in-base64-out",
                          "--payload", json.dumps(payload), str(out_file))
        result = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
    failed = "FunctionError" in (meta or "")
    return (not failed), (result or meta)[:300]

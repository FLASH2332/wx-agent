#!/usr/bin/env python3
"""Deploy and operate the two Weather Buddy stacks, each in its own AWS account.

    agent stack    (infra/container.yaml)  Docker agent on ECS Fargate, API Gateway, ALB, CloudWatch   -> env "lab-new"
    platform stack (infra/platform.yaml)   S3 buckets, SNS topics, EventBridge-scheduled weather alerts  -> env "lab-existing"

The two are deployed SEPARATELY. Deploy the platform stack first and the agent stack links to it (its S3 buckets and alarm
topic); deploy the agent stack alone and it creates its own buckets and topic (standalone).

    python scripts/deploy.py accounts                         # which profile is which account, valid or expired, linked or not
    python scripts/deploy.py check    lab-existing            # preflight (identity, tools); then the same for lab-new
    python scripts/deploy.py deploy   lab-existing            # platform: buckets, topics, alert Lambda + EventBridge rule
    python scripts/deploy.py deploy   lab-new                 # agent: ECR -> docker build/push -> stack, linked to the platform
    python scripts/deploy.py deploy   lab-new --standalone    # agent without the platform (own buckets/topic)
    python scripts/deploy.py deploy   lab-new --dry-run       # print every command, change nothing
    python scripts/deploy.py outputs  lab-new                 # stack outputs (the API URL for the frontend); saves link state
    python scripts/deploy.py status   lab-new                 # agent: running/desired tasks, autoscaling bounds, alarms
    python scripts/deploy.py stop     lab-new                 # agent: scale to 0 tasks (saves Fargate cost)
    python scripts/deploy.py start    lab-new                 # agent: scale back up and wait until healthy
    python scripts/deploy.py destroy  lab-new --yes           # delete a stack (keeps the log bucket)
    python scripts/deploy.py destroy  lab-existing --yes --delete-logs

Accounts live in infra/environments.json; the ONLY credentials mechanism is an AWS CLI profile per account, written by
scripts/set_lab_credentials.py. Secrets (OWM_API_KEY, LLM_API_KEY) are read from the repo-root .env and passed as NoEcho
parameters; they are never written to a file or printed.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ENV_FILE = ROOT / "infra" / "environments.json"
STATE_DIR = ROOT / "infra" / ".state"
TEMPLATES = {"agent": ROOT / "infra" / "container.yaml", "platform": ROOT / "infra" / "platform.yaml"}
TEMPLATE = TEMPLATES["agent"]   # kept for older callers
ECR_REPO = "weatherbuddy-agent"
SECRET_PARAMS = {"OwmApiKey", "LlmApiKey"}
SERVICE_LINKED_ROLES = ["ecs.amazonaws.com", "elasticloadbalancing.amazonaws.com", "ecs.application-autoscaling.amazonaws.com"]
# platform stack output -> agent stack parameter
PLATFORM_LINKS = {"LogsBucketName": "ExternalLogsBucketName", "SttBucketName": "ExternalSttBucketName",
                  "AlarmTopicArn": "ExternalAlarmTopicArn"}


class DeployError(Exception):
    pass


# ---------------------------------------------------------------- errors made readable
def classify_aws_failure(text: str) -> str:
    """'expired' | 'no_profile' | 'no_credentials' | 'denied' | 'other' for an AWS CLI/SDK error text."""
    low = (text or "").lower()
    if "expiredtoken" in low or "token included in the request is expired" in low or "session has expired" in low:
        return "expired"
    if "could not be found" in low and "profile" in low:
        return "no_profile"
    if "unable to locate credentials" in low or "nocredentials" in low or "invalidclienttokenid" in low:
        return "no_credentials"
    if "accessdenied" in low or "not authorized" in low or "unauthorizedoperation" in low:
        return "denied"
    return "other"


def explain_aws_error(text: str, profile: str | None) -> str:
    kind, who = classify_aws_failure(text), profile or "<profile>"
    fix = f"python scripts/set_lab_credentials.py {who}"
    if kind == "expired":
        return (f"The credentials in profile '{who}' have EXPIRED (Learner Lab keys last about 4 hours). Start that lab, open "
                f"AWS Details > AWS CLI > Show, then run: {fix}")
    if kind == "no_profile":
        return f"AWS CLI profile '{who}' does not exist yet. Create it with: {fix}"
    if kind == "no_credentials":
        return f"Profile '{who}' has no valid credentials. Refresh them with: {fix}"
    if kind == "denied":
        return (f"AWS denied the call (profile '{who}'). In Learner Lab this is a course-level restriction, not a bug in the "
                "script; the message above names the exact action.")
    return ""


# ---------------------------------------------------------------- pure helpers (unit-tested)
def load_environments(path: Path = ENV_FILE) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def get_environment(name: str, envs: dict | None = None) -> dict:
    envs = envs if envs is not None else load_environments()
    if name not in envs:
        raise DeployError(f"unknown environment '{name}'; choose one of: {', '.join(envs)}")
    cfg = dict(envs[name])
    for key in ("profile", "region", "stack_name"):
        if not cfg.get(key):
            raise DeployError(f"environment '{name}' is missing '{key}' in {ENV_FILE.name}")
    if not re.fullmatch(r"[a-z0-9-]{2,12}", name):
        raise DeployError(f"environment name '{name}' must match [a-z0-9-]{{2,12}} (it becomes the template EnvName)")
    cfg.setdefault("stack", "agent")
    if cfg["stack"] not in TEMPLATES:
        raise DeployError(f"environment '{name}': stack must be one of {sorted(TEMPLATES)}, got '{cfg['stack']}'")
    cfg["name"] = name
    return cfg


def state_path(env_name: str) -> Path:
    return STATE_DIR / f"{env_name}.json"


def save_state(env_name: str, outputs: dict, account: str | None = None) -> None:
    """Remember a deployed stack's outputs locally (gitignored), so the other stack can link to it without both
    accounts needing valid credentials at the same moment."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"saved_at": time.strftime("%Y-%m-%d %H:%M:%S"), "account": account, "outputs": outputs}
    state_path(env_name).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_state(env_name: str) -> dict:
    path = state_path(env_name)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def pick_subnets(subnets: list[dict], limit: int = 3) -> list[str]:
    """One subnet per availability zone, public-IP-on-launch first (needed: no NAT gateway)."""
    by_az: dict[str, dict] = {}
    for subnet in sorted(subnets, key=lambda s: (not s.get("MapPublicIpOnLaunch"), s["SubnetId"])):
        by_az.setdefault(subnet["AvailabilityZone"], subnet)
    chosen = sorted(by_az.values(), key=lambda s: s["AvailabilityZone"])[:limit]
    if len(chosen) < 2:
        raise DeployError("need subnets in at least two availability zones (set vpc_id/subnet_ids in environments.json)")
    return [s["SubnetId"] for s in chosen]


def build_parameter_overrides(env_cfg: dict, *, image_uri: str, vpc_id: str, subnet_ids: list[str],
                              secrets: dict, role_name: str = "LabRole", platform_outputs: dict | None = None) -> dict:
    """Agent stack parameters. Empty values are omitted so the template defaults apply. `platform_outputs` (from the
    platform stack) switches the agent to the platform's S3 buckets and alarm topic."""
    params = {
        "EnvName": env_cfg["name"],
        "ImageUri": image_uri,
        "VpcId": vpc_id,
        "SubnetIds": ",".join(subnet_ids),
        "RoleName": role_name,
        "OwmApiKey": secrets.get("OWM_API_KEY", ""),
        "LlmApiKey": secrets.get("LLM_API_KEY", ""),
        "LlmModelId": secrets.get("LLM_MODEL_ID", ""),
        "LlmBaseUrl": secrets.get("LLM_BASE_URL", ""),
        "RouterModelId": secrets.get("ROUTER_MODEL_ID", ""),
    }
    for output_key, parameter in PLATFORM_LINKS.items():
        params[parameter] = (platform_outputs or {}).get(output_key, "")
    params.update({k: str(v) for k, v in (env_cfg.get("parameters") or {}).items()})
    return {k: v for k, v in params.items() if v not in ("", None)}


def build_platform_overrides(env_cfg: dict, *, agent_account_id: str, secrets: dict, role_name: str = "LabRole") -> dict:
    """Platform stack parameters (the agent account id drives every cross-account resource policy)."""
    params = {
        "EnvName": env_cfg["name"],
        "RoleName": role_name,
        "AgentAccountId": agent_account_id,
        "OwmApiKey": secrets.get("OWM_API_KEY", ""),
    }
    params.update({k: str(v) for k, v in (env_cfg.get("parameters") or {}).items()})
    return {k: v for k, v in params.items() if v not in ("", None)}


def agent_account_for(platform_cfg: dict, envs: dict) -> str:
    agent_env = platform_cfg.get("agent")
    if not agent_env or agent_env not in envs:
        raise DeployError(f"environment '{platform_cfg['name']}' needs \"agent\": \"<env name>\" in {ENV_FILE.name} (the account that runs the agent)")
    account = (envs[agent_env] or {}).get("expected_account")
    if not account or not re.fullmatch(r"\d{12}", str(account)):
        raise DeployError(f"set expected_account (12 digits) on '{agent_env}' in {ENV_FILE.name}: the platform stack needs the agent account id for its resource policies")
    return str(account)


def build_sam_deploy_command(sam: str, env_cfg: dict, overrides: dict) -> list[str]:
    command = [
        sam, "deploy",
        "--template-file", str(TEMPLATES[env_cfg.get("stack", "agent")]),
        "--stack-name", env_cfg["stack_name"],
        "--region", env_cfg["region"],
        "--profile", env_cfg["profile"],
        "--capabilities", "CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND",
        "--resolve-s3",
        "--no-confirm-changeset", "--no-fail-on-empty-changeset",
        "--tags", "Project=weather-buddy", f"Env={env_cfg['name']}", f"Stack={env_cfg.get('stack', 'agent')}",
        "--parameter-overrides",
    ]
    command += [f"{k}={v}" for k, v in overrides.items()]
    return command


def mask_command(command: list[str]) -> str:
    """Printable command with every secret parameter value replaced."""
    masked = []
    for part in command:
        key, sep, _ = part.partition("=")
        masked.append(f"{key}=***" if sep and key in SECRET_PARAMS else part)
    return " ".join(masked)


def read_secrets(env_path: Path | None = None) -> dict:
    """OWM/LLM settings from .env, using the same legacy GROQ_* mapping as the app itself."""
    from dotenv import dotenv_values

    from agent_service.config import Settings

    values = {k: v for k, v in dotenv_values(env_path or ROOT / ".env").items() if v is not None}
    s = Settings.from_env(values)
    return {"OWM_API_KEY": s.owm_api_key, "LLM_API_KEY": s.llm_api_key, "LLM_MODEL_ID": s.llm_model_id,
            "LLM_BASE_URL": s.llm_base_url, "ROUTER_MODEL_ID": s.router_model_id}


# ---------------------------------------------------------------- command execution
class Runner:
    def __init__(self, env_cfg: dict, dry_run: bool = False):
        self.cfg, self.dry_run = env_cfg, dry_run

    def aws(self, *args: str, check: bool = True, readonly: bool = False) -> str:
        """Run an aws CLI command. Mutating by default: dry-run prints it instead of running it."""
        cmd = ["aws", "--profile", self.cfg["profile"], "--region", self.cfg["region"], *args]
        return self._run(cmd, check=check, readonly=readonly)

    def _run(self, cmd: list[str], *, check: bool = True, readonly: bool = False, input_text: str | None = None) -> str:
        shown = mask_command(cmd)
        if self.dry_run and not readonly:
            print(f"  [dry-run] {shown}")
            return ""
        result = subprocess.run(cmd, capture_output=True, text=True, input=input_text)
        if check and result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            hint = explain_aws_error(detail, self.cfg.get("profile"))
            raise DeployError(f"command failed: {shown}\n{detail[:600]}" + (f"\n=> {hint}" if hint else ""))
        return result.stdout.strip()


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        hints = {"aws": "install the AWS CLI v2", "docker": "install and start Docker Desktop",
                 "sam": "pip install aws-sam-cli  (or the SAM CLI installer)"}
        raise DeployError(f"'{name}' not found on PATH: {hints.get(name, '')}")
    return path


def identity(runner: Runner) -> tuple[str, str]:
    out = runner._run(["aws", "--profile", runner.cfg["profile"], "--region", runner.cfg["region"], "sts", "get-caller-identity", "--output", "json"], readonly=True)
    data = json.loads(out)
    return data["Account"], data["Arn"]


def verify_account(cfg: dict, account: str) -> None:
    if cfg.get("expected_account") and cfg["expected_account"] != account:
        raise DeployError(f"profile '{cfg['profile']}' is account {account}, but environments.json expects {cfg['expected_account']} for "
                          f"'{cfg['name']}'. Wrong credentials were pasted into that profile.")


def discover_network(runner: Runner) -> tuple[str, list[str]]:
    if runner.cfg.get("vpc_id") and runner.cfg.get("subnet_ids"):
        return runner.cfg["vpc_id"], list(runner.cfg["subnet_ids"])
    vpcs = json.loads(runner._run(["aws", "--profile", runner.cfg["profile"], "--region", runner.cfg["region"], "ec2", "describe-vpcs",
                                   "--filters", "Name=isDefault,Values=true", "--output", "json"], readonly=True))["Vpcs"]
    if not vpcs:
        raise DeployError("no default VPC in this account/region; set vpc_id and subnet_ids in environments.json")
    vpc_id = vpcs[0]["VpcId"]
    subnets = json.loads(runner._run(["aws", "--profile", runner.cfg["profile"], "--region", runner.cfg["region"], "ec2", "describe-subnets",
                                      "--filters", f"Name=vpc-id,Values={vpc_id}", "--output", "json"], readonly=True))["Subnets"]
    return vpc_id, pick_subnets(subnets)


def ensure_ecr_repo(runner: Runner, account: str) -> str:
    uri = f"{account}.dkr.ecr.{runner.cfg['region']}.amazonaws.com/{ECR_REPO}"
    if runner.dry_run:
        print(f"  [dry-run] ensure ECR repository {ECR_REPO} exists")
        return uri
    exists = runner._run(["aws", "--profile", runner.cfg["profile"], "--region", runner.cfg["region"], "ecr", "describe-repositories",
                          "--repository-names", ECR_REPO], check=False, readonly=True)
    if not exists:
        print(f"  creating ECR repository {ECR_REPO}")
        runner.aws("ecr", "create-repository", "--repository-name", ECR_REPO, "--image-scanning-configuration", "scanOnPush=true")
    return uri


def ensure_service_linked_roles(runner: Runner) -> None:
    """Best effort: the first ECS/ELB/autoscaling use in an account needs these roles. Already-exists and
    access-denied are fine (the stack create will surface a real problem with a clear message)."""
    for service in SERVICE_LINKED_ROLES:
        out = runner._run(["aws", "--profile", runner.cfg["profile"], "iam", "create-service-linked-role", "--aws-service-name", service],
                          check=False)
        print(f"  service-linked role {service}: {'requested' if out or runner.dry_run else 'already present or not permitted (continuing)'}")


def docker_build_and_push(runner: Runner, account: str, image_uri: str, repo_uri: str) -> None:
    docker = require_tool("docker") if not runner.dry_run else "docker"
    registry = repo_uri.split("/")[0]
    print(f"  docker login {registry}")
    if not runner.dry_run:
        password = runner._run(["aws", "--profile", runner.cfg["profile"], "--region", runner.cfg["region"], "ecr", "get-login-password"], readonly=True)
        runner._run([docker, "login", "--username", "AWS", "--password-stdin", registry], input_text=password)
    else:
        print("  [dry-run] aws ecr get-login-password | docker login --username AWS --password-stdin " + registry)
    runner._run([docker, "build", "--platform", "linux/amd64", "-f", "agent_service/Dockerfile", "-t", image_uri, str(ROOT)])
    runner._run([docker, "push", image_uri])


def stack_outputs(runner: Runner) -> dict:
    out = runner._run(["aws", "--profile", runner.cfg["profile"], "--region", runner.cfg["region"], "cloudformation", "describe-stacks",
                       "--stack-name", runner.cfg["stack_name"], "--query", "Stacks[0].Outputs", "--output", "json"], readonly=True)
    return {o["OutputKey"]: o["OutputValue"] for o in json.loads(out or "[]")}


def resolve_platform_outputs(cfg: dict, envs: dict, *, standalone: bool, offline: bool) -> tuple[dict, str]:
    """Outputs of the platform stack this agent environment links to, with a one-line explanation."""
    platform = cfg.get("platform")
    if standalone:
        return {}, "STANDALONE (--standalone): the agent stack creates its own S3 buckets and SNS topic"
    if not platform:
        return {}, "STANDALONE (no \"platform\" set for this environment): own S3 buckets and SNS topic"
    state = load_state(platform)
    if state.get("outputs"):
        return state["outputs"], f"LINKED to platform '{platform}' (outputs saved {state.get('saved_at', '?')}): its S3 buckets and alarm topic are used"
    if not offline:
        try:
            outputs = stack_outputs(Runner(get_environment(platform, envs)))
            if outputs:
                save_state(platform, outputs)
                return outputs, f"LINKED to platform '{platform}' (read live from its account)"
        except DeployError:
            pass
    return {}, (f"STANDALONE for now: platform '{platform}' has not been deployed (or its credentials are not valid here). "
                f"Deploy it first with 'deploy {platform}' to link; deploying now creates local buckets and topic")


# ---------------------------------------------------------------- subcommands
def _print_account(cfg: dict, account: str, arn: str) -> None:
    role = arn.split("/")[1] if "/" in arn else arn
    kind = "platform stack (S3, SNS, EventBridge)" if cfg["stack"] == "platform" else "agent stack (Docker, ECS, API Gateway, ALB, CloudWatch)"
    print(f"  environment {cfg['name']}: {kind}")
    print(f"  account     {account}  (signed in as {role}; profile {cfg['profile']}, region {cfg['region']})")


def cmd_accounts(args) -> int:
    envs = load_environments()
    print("== accounts (one AWS CLI profile per account; refresh with scripts/set_lab_credentials.py)")
    problems = 0
    for name in envs:
        cfg = get_environment(name, envs)
        proc = subprocess.run(["aws", "--profile", cfg["profile"], "sts", "get-caller-identity", "--output", "json"], capture_output=True, text=True)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            role = data["Arn"].split("/")[1] if "/" in data["Arn"] else data["Arn"]
            expected = cfg.get("expected_account")
            if expected and expected != data["Account"]:
                status, problems = f"WRONG ACCOUNT: signed in to {data['Account']}, expected {expected}", problems + 1
            else:
                note = "" if expected else "  (set expected_account in environments.json as a safety check)"
                status = f"OK       account {data['Account']} as {role}{note}"
        else:
            kind = classify_aws_failure(proc.stderr)
            status = {"expired": "EXPIRED  run: python scripts/set_lab_credentials.py " + cfg["profile"],
                      "no_profile": "MISSING  run: python scripts/set_lab_credentials.py " + cfg["profile"]}.get(
                kind, f"ERROR    {(proc.stderr or proc.stdout).strip()[:120]}")
            problems += 1
        print(f"  {name:<13} {cfg['stack']:<9} profile {cfg['profile']:<12} {cfg['region']:<10} {status}")
    print("\n== links between the stacks")
    for name in envs:
        cfg = get_environment(name, envs)
        if cfg["stack"] == "agent":
            platform = cfg.get("platform")
            state = load_state(platform) if platform else {}
            if not platform:
                print(f"  {name}: standalone (no platform configured)")
            elif state.get("outputs"):
                print(f"  {name} -> {platform}: linked; platform outputs saved {state.get('saved_at', '?')} (buckets, alarm topic)")
            else:
                print(f"  {name} -> {platform}: platform not deployed yet (no saved outputs); the agent would deploy standalone")
    print("\n  Tip: Learner Lab keys last about 4 hours. Each account has its own lab, so refresh both when you start a session.")
    return 1 if problems else 0


def cmd_check(args) -> int:
    envs = load_environments()
    cfg = get_environment(args.env, envs)
    runner = Runner(cfg)
    print(f"== check '{args.env}'")
    tools = ("aws", "sam") if cfg["stack"] == "platform" else ("aws", "docker", "sam")
    for tool in tools:
        print(f"  {tool}: {shutil.which(tool) or 'NOT FOUND'}")
    account, arn = identity(runner)
    _print_account(cfg, account, arn)
    verify_account(cfg, account)
    if cfg["stack"] == "platform":
        agent_account = agent_account_for(cfg, envs)
        print(f"  agent account the policies will allow: {agent_account} ('{cfg['agent']}')")
        print(f"  OWM_API_KEY in .env: {'yes' if read_secrets().get('OWM_API_KEY') else 'MISSING'}")
        print("  ready: python scripts/deploy.py deploy " + args.env)
        return 0
    vpc, subnets = discover_network(runner)
    print(f"  network: {vpc} subnets {', '.join(subnets)}")
    docker_ok = subprocess.run([shutil.which("docker") or "docker", "info"], capture_output=True).returncode == 0
    print(f"  docker daemon: {'running' if docker_ok else 'NOT RUNNING (start Docker Desktop)'}")
    _, note = resolve_platform_outputs(cfg, envs, standalone=False, offline=False)
    print(f"  link: {note}")
    return 0


def _deploy_platform(args, cfg: dict, envs: dict) -> int:
    runner = Runner(cfg, dry_run=args.dry_run)
    print(f"== deploy platform '{args.env}'{' [DRY RUN]' if args.dry_run else ''}")
    agent_account = agent_account_for(cfg, envs)
    if args.dry_run:
        account = "<this-account-id>"
        print(f"  environment {args.env}: platform stack; profile {cfg['profile']}, region {cfg['region']}")
    else:
        require_tool("aws"), require_tool("sam")
        account, arn = identity(runner)
        _print_account(cfg, account, arn)
        verify_account(cfg, account)
        if account == agent_account:
            print("  note: this is the same account as the agent; the cross-account policies are harmless but pointless here")
    print(f"  shares S3 buckets and SNS topics with agent account {agent_account} ('{cfg['agent']}')")
    secrets = read_secrets()
    if not secrets.get("OWM_API_KEY"):
        raise DeployError("missing OWM_API_KEY in .env (the daily alert Lambda needs it)")
    overrides = build_platform_overrides(cfg, agent_account_id=agent_account, secrets=secrets)
    command = build_sam_deploy_command("sam" if args.dry_run else require_tool("sam"), cfg, overrides)
    print("  sam deploy ...")
    if args.dry_run:
        print("  [dry-run] " + mask_command(command))
        return 0
    subprocess.run(command, check=True)
    code = cmd_outputs(args)
    emails = sorted({cfg.get("parameters", {}).get(k) for k in ("AlertEmail", "AlarmEmail")} - {None, ""})
    if emails:
        print(f"\n  EMAIL: AWS just sent 'Subscription Confirmation' messages to {', '.join(emails)} (one per topic; check Spam too).")
        print(f"         Nothing is delivered until you click 'Confirm subscription' in each. Then: python scripts/notify_test.py sns {args.env} --publish")
    print(f"\n  next: deploy the agent so it links to these resources:  python scripts/deploy.py deploy {cfg['agent']}")
    return code


def cmd_deploy(args) -> int:
    envs = load_environments()
    cfg = get_environment(args.env, envs)
    if cfg["stack"] == "platform":
        return _deploy_platform(args, cfg, envs)
    runner = Runner(cfg, dry_run=args.dry_run)
    print(f"== deploy agent '{args.env}'{' [DRY RUN]' if args.dry_run else ''}")
    if not args.dry_run:
        for tool in ("aws", "sam") + (() if args.image_uri else ("docker",)):
            require_tool(tool)
        account, arn = identity(runner)
        _print_account(cfg, account, arn)
        verify_account(cfg, account)
        vpc_id, subnet_ids = discover_network(runner)
    else:
        account, vpc_id, subnet_ids = "<account-id>", "<default-vpc>", ["<subnet-a>", "<subnet-b>"]
        print(f"  environment {args.env}: agent stack; profile {cfg['profile']}, region {cfg['region']}")
    print(f"  network: {vpc_id} / {', '.join(subnet_ids)}")

    platform_outputs, note = resolve_platform_outputs(cfg, envs, standalone=args.standalone, offline=args.dry_run)
    print(f"  link: {note}")
    if platform_outputs.get("AgentAccountId") and not args.dry_run and platform_outputs["AgentAccountId"] != account:
        raise DeployError(f"the platform stack was deployed for agent account {platform_outputs['AgentAccountId']}, but this profile is "
                          f"account {account}. Redeploy the platform with the right expected_account, or use --standalone.")
    for key, parameter in PLATFORM_LINKS.items():
        if platform_outputs.get(key):
            print(f"    {parameter} = {platform_outputs[key]}")

    secrets = read_secrets()
    missing = [k for k in ("OWM_API_KEY", "LLM_MODEL_ID") if not secrets.get(k)]
    if missing:
        raise DeployError(f"missing in .env: {', '.join(missing)}")

    ensure_service_linked_roles(runner)
    if args.image_uri:
        image_uri = args.image_uri
    else:
        repo_uri = ensure_ecr_repo(runner, account)
        image_uri = f"{repo_uri}:agent-{time.strftime('%Y%m%d-%H%M%S')}"
        docker_build_and_push(runner, account, image_uri, repo_uri)
    print(f"  image: {image_uri}")

    overrides = build_parameter_overrides(cfg, image_uri=image_uri, vpc_id=vpc_id, subnet_ids=subnet_ids, secrets=secrets,
                                          platform_outputs=platform_outputs)
    command = build_sam_deploy_command(require_tool("sam") if not args.dry_run else "sam", cfg, overrides)
    print("  sam deploy ...")
    if args.dry_run:
        print("  [dry-run] " + mask_command(command))
        return 0
    subprocess.run(command, check=True)
    return cmd_outputs(args)


def cmd_outputs(args) -> int:
    envs = load_environments()
    cfg = get_environment(args.env, envs)
    runner = Runner(cfg)
    outputs = stack_outputs(runner)
    for key, value in outputs.items():
        print(f"  {key}: {value}")
    if outputs:
        try:
            save_state(args.env, outputs, identity(runner)[0])
        except DeployError:
            save_state(args.env, outputs)
        print(f"  (outputs saved to infra/.state/{args.env}.json so the other stack can link to them)")
    if cfg["stack"] == "agent" and "FrontendApiUrl" in outputs:
        print(f"\nfrontend/.env.local:  NEXT_PUBLIC_API_URL={outputs['FrontendApiUrl']}")
        print(f"verify:               curl {outputs['FrontendApiUrl']}/health")
    return 0


def cmd_destroy(args) -> int:
    if not args.yes:
        raise DeployError("destroy deletes the stack and its resources; re-run with --yes")
    envs = load_environments()
    cfg = get_environment(args.env, envs)
    runner = Runner(cfg)
    account, arn = identity(runner)
    _print_account(cfg, account, arn)
    verify_account(cfg, account)
    outputs = stack_outputs(runner)
    if cfg["stack"] == "platform":
        print("  WARNING: the agent stack may use this stack's S3 buckets and alarm topic. Destroying it breaks ALB log delivery and "
              "alarm notifications until you redeploy the platform or redeploy the agent with --standalone.")
    stt_bucket, logs_bucket = outputs.get("SttBucketName"), outputs.get("LogsBucketName")
    if stt_bucket and (cfg["stack"] == "platform" or not _external_stt(cfg)):
        print(f"  emptying {stt_bucket}")
        runner.aws("s3", "rm", f"s3://{stt_bucket}", "--recursive")
    runner._run([require_tool("sam"), "delete", "--stack-name", runner.cfg["stack_name"], "--region", runner.cfg["region"],
                 "--profile", runner.cfg["profile"], "--no-prompts"])
    if cfg["stack"] == "platform" and state_path(args.env).exists():
        state_path(args.env).unlink()
    if args.delete_logs and logs_bucket and (cfg["stack"] == "platform" or not _external_logs(cfg)):
        print(f"  deleting log bucket {logs_bucket}")
        runner.aws("s3", "rb", f"s3://{logs_bucket}", "--force")
        print("  deleted, including the logs. A fresh 'deploy' can now reuse the name.")
    else:
        print("  deleted. The log bucket was kept on purpose (its fixed name blocks a redeploy: use --delete-logs to remove it).")
    if cfg["stack"] == "agent":
        print("  The ECR repository and its images are untouched.")
    return 0


def _external_stt(cfg: dict) -> bool:
    return bool(load_state(cfg.get("platform", "")).get("outputs", {}).get("SttBucketName")) if cfg.get("platform") else False


def _external_logs(cfg: dict) -> bool:
    return bool(load_state(cfg.get("platform", "")).get("outputs", {}).get("LogsBucketName")) if cfg.get("platform") else False


def plan_scale(outputs: dict, params: dict, account: str, *, stop: bool) -> list[list[str]]:
    """aws CLI argument lists that stop or start the service.

    Autoscaling must be changed too: with its minimum at 1 it would immediately start a task again."""
    cluster, service = outputs["ClusterName"], outputs["ServiceName"]
    role = f"arn:aws:iam::{account}:role/{params.get('RoleName') or 'LabRole'}"
    min_count = 0 if stop else int(params.get("MinCount") or 1)
    max_count = int(params.get("MaxCount") or 3)
    desired = 0 if stop else max(int(params.get("DesiredCount") or 1), min_count)
    commands: list[list[str]] = []
    if (params.get("EnableAutoScaling") or "true") == "true":
        commands.append([
            "application-autoscaling", "register-scalable-target", "--service-namespace", "ecs",
            "--scalable-dimension", "ecs:service:DesiredCount", "--resource-id", f"service/{cluster}/{service}",
            "--min-capacity", str(min_count), "--max-capacity", str(max_count), "--role-arn", role])
    commands.append(["ecs", "update-service", "--cluster", cluster, "--service", service, "--desired-count", str(desired)])
    return commands


def stack_info(runner: Runner) -> tuple[dict, dict]:
    out = runner._run(["aws", "--profile", runner.cfg["profile"], "--region", runner.cfg["region"], "cloudformation", "describe-stacks",
                       "--stack-name", runner.cfg["stack_name"], "--query", "Stacks[0]", "--output", "json"], readonly=True)
    if not out or out == "null":
        raise DeployError(f"stack '{runner.cfg['stack_name']}' not found in this account/region (deploy it first)")
    stack = json.loads(out)
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs") or []}
    params = {p["ParameterKey"]: p.get("ParameterValue") for p in stack.get("Parameters") or []}
    return outputs, params


def _alarm_names(runner: Runner) -> list[str]:
    out = runner._run(["aws", "--profile", runner.cfg["profile"], "--region", runner.cfg["region"], "cloudwatch", "describe-alarms",
                       "--alarm-name-prefix", runner.cfg["stack_name"], "--query", "MetricAlarms[].AlarmName", "--output", "json"], readonly=True)
    return json.loads(out or "[]")


def _agent_only(cfg: dict, what: str) -> bool:
    if cfg["stack"] == "platform":
        print(f"  '{cfg['name']}' is the platform stack: S3, SNS, EventBridge and a Lambda cost nothing while idle, so there is "
              f"nothing to {what}. Use 'destroy' to remove it.")
        return True
    return False


def _scale(args, *, stop: bool) -> int:
    cfg = get_environment(args.env)
    if _agent_only(cfg, "stop or start"):
        return 0
    runner = Runner(cfg, dry_run=args.dry_run)
    account, _ = identity(runner)
    verify_account(cfg, account)
    outputs, params = stack_info(runner)
    verb = "stopping" if stop else "starting"
    print(f"== {verb} '{args.env}' (account {account}){' [DRY RUN]' if args.dry_run else ''}")
    for command in plan_scale(outputs, params, account, stop=stop):
        print(f"  aws {command[0]} {command[1]} ...")
        runner.aws(*command)
    # While stopped there are no healthy targets, so the outage alarms would fire and email you.
    alarms = _alarm_names(runner)
    if alarms:
        action = "disable-alarm-actions" if stop else "enable-alarm-actions"
        print(f"  cloudwatch {action} ({len(alarms)} alarms)")
        runner.aws("cloudwatch", action, "--alarm-names", *alarms)
    if stop:
        print("  stopped: no tasks run, so no Fargate charge. The ALB (about $0.54/day) and secret still bill; use 'destroy' to stop everything.")
        return 0
    if not args.dry_run:
        print("  waiting for the service to become healthy (up to ~10 min)...")
        runner.aws("ecs", "wait", "services-stable", "--cluster", outputs["ClusterName"], "--services", outputs["ServiceName"], readonly=True)
    url = outputs.get("FrontendApiUrl", "<deployed url>")
    print(f"  started. curl {url}/health")
    return 0


def cmd_stop(args) -> int:
    return _scale(args, stop=True)


def cmd_start(args) -> int:
    return _scale(args, stop=False)


def cmd_status(args) -> int:
    cfg = get_environment(args.env)
    runner = Runner(cfg)
    account, arn = identity(runner)
    _print_account(cfg, account, arn)
    verify_account(cfg, account)
    outputs, params = stack_info(runner)
    if cfg["stack"] == "platform":
        print(f"  stack {cfg['stack_name']}: deployed")
        for key in ("LogsBucketName", "SttBucketName", "AlarmTopicArn", "AlertTopicArn", "AlertFunctionName", "AgentAccountId"):
            if key in outputs:
                print(f"    {key}: {outputs[key]}")
        print("  deeper checks: python scripts/smoke_test.py platform " + args.env)
        return 0
    cluster, service = outputs["ClusterName"], outputs["ServiceName"]
    svc = json.loads(runner._run(["aws", "--profile", runner.cfg["profile"], "--region", runner.cfg["region"], "ecs", "describe-services",
                                  "--cluster", cluster, "--services", service, "--query", "services[0]", "--output", "json"], readonly=True))
    print(f"  service {service}: {svc.get('status')}  running {svc.get('runningCount')} / desired {svc.get('desiredCount')}  pending {svc.get('pendingCount')}")
    targets = json.loads(runner._run(["aws", "--profile", runner.cfg["profile"], "--region", runner.cfg["region"], "application-autoscaling",
                                      "describe-scalable-targets", "--service-namespace", "ecs", "--resource-ids", f"service/{cluster}/{service}",
                                      "--output", "json"], readonly=True, check=False) or '{"ScalableTargets": []}')["ScalableTargets"]
    if targets:
        print(f"  autoscaling: min {targets[0]['MinCapacity']} / max {targets[0]['MaxCapacity']}")
    alarms = json.loads(runner._run(["aws", "--profile", runner.cfg["profile"], "--region", runner.cfg["region"], "cloudwatch", "describe-alarms",
                                     "--alarm-name-prefix", runner.cfg["stack_name"], "--output", "json"], readonly=True))["MetricAlarms"]
    in_alarm = [a["AlarmName"].split("-")[2] if a["AlarmName"].count("-") >= 2 else a["AlarmName"] for a in alarms if a["StateValue"] == "ALARM"]
    print(f"  alarms: {len(alarms)} total, in ALARM: {', '.join(in_alarm) or 'none'}; actions {'enabled' if alarms and alarms[0].get('ActionsEnabled') else 'disabled'}")
    external = [p for p in ("ExternalLogsBucketName", "ExternalSttBucketName", "ExternalAlarmTopicArn") if params.get(p)]
    print(f"  link: {'uses the platform stack for ' + ', '.join(p.replace('External', '') for p in external) if external else 'standalone (own buckets and topic)'}")
    print(f"  url: {outputs.get('FrontendApiUrl', '?')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("accounts", help="show every account/profile, whether its credentials are valid, and the links between stacks")
    for name in ("check", "deploy", "outputs", "status", "stop", "start", "destroy"):
        p = sub.add_parser(name)
        p.add_argument("env", help="environment name from infra/environments.json")
        if name in ("deploy", "stop", "start"):
            p.add_argument("--dry-run", action="store_true", help="print the commands without running them")
        if name == "deploy":
            p.add_argument("--image-uri", help="agent: deploy an already pushed image instead of building one")
            p.add_argument("--standalone", action="store_true", help="agent: ignore the platform stack (own buckets and topic)")
        if name == "destroy":
            p.add_argument("--yes", action="store_true")
            p.add_argument("--delete-logs", action="store_true", help="also empty and delete the retained S3 log bucket")
    args = parser.parse_args(argv)
    try:
        handlers = {"accounts": cmd_accounts, "check": cmd_check, "deploy": cmd_deploy, "outputs": cmd_outputs, "status": cmd_status,
                    "stop": cmd_stop, "start": cmd_start, "destroy": cmd_destroy}
        return handlers[args.command](args)
    except DeployError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"error: command exited with {exc.returncode}", file=sys.stderr)
        return exc.returncode


if __name__ == "__main__":
    sys.exit(main())

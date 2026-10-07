import configparser
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module   # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


deploy = _load("deploy_under_test", "scripts/deploy.py")
creds = _load("creds_under_test", "scripts/set_lab_credentials.py")


# ---------------------------------------------------------------- environments
def test_environment_names_fit_the_template_pattern_and_have_required_keys():
    envs = deploy.load_environments()
    assert {"lab-new", "lab-existing"} <= set(envs)
    for name in envs:
        cfg = deploy.get_environment(name, envs)
        assert cfg["name"] == name and re.fullmatch(r"[a-z0-9-]{2,12}", name)


def test_unknown_environment_is_a_clear_error():
    with pytest.raises(deploy.DeployError, match="unknown environment"):
        deploy.get_environment("prod")


def test_environment_with_missing_profile_is_rejected():
    with pytest.raises(deploy.DeployError, match="profile"):
        deploy.get_environment("x1", {"x1": {"region": "us-east-1", "stack_name": "s"}})


# ---------------------------------------------------------------- network + parameters
def test_pick_subnets_one_per_az_public_first():
    subnets = [
        {"SubnetId": "s-b1", "AvailabilityZone": "us-east-1b", "MapPublicIpOnLaunch": False},
        {"SubnetId": "s-b2", "AvailabilityZone": "us-east-1b", "MapPublicIpOnLaunch": True},
        {"SubnetId": "s-a", "AvailabilityZone": "us-east-1a", "MapPublicIpOnLaunch": True},
        {"SubnetId": "s-c", "AvailabilityZone": "us-east-1c", "MapPublicIpOnLaunch": True},
        {"SubnetId": "s-d", "AvailabilityZone": "us-east-1d", "MapPublicIpOnLaunch": True},
    ]
    assert deploy.pick_subnets(subnets) == ["s-a", "s-b2", "s-c"]
    with pytest.raises(deploy.DeployError):
        deploy.pick_subnets(subnets[:2])  # both in one AZ


SECRETS = {"OWM_API_KEY": "owm-secret", "LLM_API_KEY": "llm-secret", "LLM_MODEL_ID": "groq/x",
           "LLM_BASE_URL": "", "ROUTER_MODEL_ID": ""}


def _overrides(**extra):
    cfg = deploy.get_environment("lab-new")
    cfg["parameters"] = {**cfg.get("parameters", {}), **extra}
    return cfg, deploy.build_parameter_overrides(cfg, image_uri="123.dkr.ecr/x:1", vpc_id="vpc-1",
                                                 subnet_ids=["s-1", "s-2"], secrets=SECRETS)


def test_parameter_overrides_omit_empty_values_and_apply_account_overrides():
    _, params = _overrides(MaxCount="5")
    assert params["SubnetIds"] == "s-1,s-2" and params["EnvName"] == "lab-new" and params["MaxCount"] == "5"
    assert "LlmBaseUrl" not in params and "RouterModelId" not in params  # template defaults apply
    assert params["OwmApiKey"] == "owm-secret"


def test_sam_command_has_the_account_profile_and_secrets_are_masked_when_printed():
    cfg, params = _overrides()
    command = deploy.build_sam_deploy_command("sam", cfg, params)
    assert command[:2] == ["sam", "deploy"] and "--profile" in command and cfg["profile"] in command
    assert "OwmApiKey=owm-secret" in command            # passed through for real...
    shown = deploy.mask_command(command)
    assert "owm-secret" not in shown and "llm-secret" not in shown and "OwmApiKey=***" in shown   # ...never printed


def _template_parameters(template="container.yaml"):
    yaml = pytest.importorskip("yaml")

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    return yaml.load((ROOT / "infra" / template).read_text(encoding="utf-8"), Loader=Loader)["Parameters"]


def test_every_parameter_the_script_passes_exists_in_the_template():
    declared = set(_template_parameters())
    cfg, params = _overrides()
    params.update(deploy.build_parameter_overrides(cfg, image_uri="i", vpc_id="v", subnet_ids=["a", "b"], secrets=SECRETS,
                                                   platform_outputs={"LogsBucketName": "b1", "SttBucketName": "b2", "AlarmTopicArn": "arn:x"}))
    assert set(params) <= declared, set(params) - declared
    for name, env in deploy.load_environments().items():
        template = {"agent": "container.yaml", "platform": "platform.yaml"}[env.get("stack", "agent")]
        assert set(env.get("parameters", {})) <= set(_template_parameters(template)), f"{name}: parameters not in {template}"


def test_platform_parameters_the_script_passes_exist_and_required_ones_are_supplied():
    template = _template_parameters("platform.yaml")
    cfg = deploy.get_environment("lab-existing")
    params = deploy.build_platform_overrides(cfg, agent_account_id="057016988906", secrets=SECRETS)
    assert set(params) <= set(template), set(params) - set(template)
    assert {k for k, v in template.items() if "Default" not in v} <= set(params)
    assert params["AgentAccountId"] == "057016988906" and params["OwmApiKey"] == "owm-secret"


def test_template_parameters_without_defaults_are_all_supplied_by_the_script():
    template = _template_parameters()
    required = {k for k, v in template.items() if "Default" not in v}
    _, params = _overrides()
    assert required <= set(params), required - set(params)


# ---------------------------------------------------------------- credentials helper
BLOCK = """
[default]
aws_access_key_id=ASIAEXAMPLEKEY1234
aws_secret_access_key=secretsecretsecretsecretsecretsecret12
aws_session_token=tokentokentokentoken==
"""


def test_credentials_block_parsing():
    parsed = creds.parse_credentials_block(BLOCK)
    assert parsed["aws_access_key_id"] == "ASIAEXAMPLEKEY1234" and parsed["aws_session_token"].endswith("==")
    with pytest.raises(ValueError, match="aws_session_token"):
        creds.parse_credentials_block("aws_access_key_id=A\naws_secret_access_key=B\n")


def test_write_profile_keeps_other_profiles_and_sets_the_region(tmp_path):
    credentials_file, config_file = tmp_path / "credentials", tmp_path / "config"
    credentials_file.write_text("[other]\naws_access_key_id = KEEP\n")
    creds.write_profile("wb-new", creds.parse_credentials_block(BLOCK), "us-east-1", credentials_file, config_file)
    creds.write_profile("wb-existing", creds.parse_credentials_block(BLOCK.replace("1234", "9999")), "us-east-1", credentials_file, config_file)
    parser = configparser.RawConfigParser()
    parser.read(credentials_file)
    assert parser["other"]["aws_access_key_id"] == "KEEP"
    assert parser["wb-new"]["aws_access_key_id"] == "ASIAEXAMPLEKEY1234"
    assert parser["wb-existing"]["aws_access_key_id"] == "ASIAEXAMPLEKEY9999"
    config = configparser.RawConfigParser()
    config.read(config_file)
    assert config["profile wb-new"]["region"] == "us-east-1"


# ---------------------------------------------------------------- stop / start planning
OUTPUTS = {"ClusterName": "weatherbuddy-lab-new", "ServiceName": "weatherbuddy-lab-new"}


def test_stop_zeroes_autoscaling_minimum_and_desired_count():
    """Autoscaling with min 1 would restart a task right after a plain desired-count 0."""
    commands = deploy.plan_scale(OUTPUTS, {"MinCount": "1", "MaxCount": "2", "RoleName": "LabRole"}, "057016988906", stop=True)
    scaling, update = commands
    assert scaling[:2] == ["application-autoscaling", "register-scalable-target"]
    assert scaling[scaling.index("--min-capacity") + 1] == "0" and scaling[scaling.index("--max-capacity") + 1] == "2"
    assert scaling[scaling.index("--resource-id") + 1] == "service/weatherbuddy-lab-new/weatherbuddy-lab-new"
    assert scaling[scaling.index("--role-arn") + 1] == "arn:aws:iam::057016988906:role/LabRole"   # no service-linked role needed
    assert update[:2] == ["ecs", "update-service"] and update[update.index("--desired-count") + 1] == "0"


def test_start_restores_the_deployed_minimum_and_desired_count():
    commands = deploy.plan_scale(OUTPUTS, {"MinCount": "2", "MaxCount": "4", "DesiredCount": "1"}, "123456789012", stop=False)
    scaling, update = commands
    assert scaling[scaling.index("--min-capacity") + 1] == "2" and scaling[scaling.index("--max-capacity") + 1] == "4"
    assert update[update.index("--desired-count") + 1] == "2"          # never below the autoscaling minimum


def test_without_autoscaling_only_the_service_is_touched():
    commands = deploy.plan_scale(OUTPUTS, {"EnableAutoScaling": "false"}, "123456789012", stop=True)
    assert [c[0] for c in commands] == ["ecs"]


# ---------------------------------------------------------------- smoke test helpers
smoke = _load("smoke_under_test", "scripts/smoke_test.py")


def test_sns_subscription_classification():
    assert smoke.classify_subscriptions([])[0] == "WARN"
    pending = {"SubscriptionArn": "PendingConfirmation"}
    confirmed = {"SubscriptionArn": "arn:aws:sns:us-east-1:1:topic:abc"}
    assert smoke.classify_subscriptions([pending])[0] == "WARN"
    status, detail = smoke.classify_subscriptions([confirmed, pending])
    assert status == "PASS" and "1 confirmed" in detail and "1 still pending" in detail


def test_log_age_helpers():
    now = 1_000_000.0
    assert smoke.age_hours(None) is None and smoke.fmt_age(None) == "never"
    assert smoke.age_hours(int((now - 3600) * 1000), now) == pytest.approx(1.0)
    assert smoke.fmt_age(0.5) == "30 min ago" and smoke.fmt_age(5.0) == "5.0 h ago"


def test_report_exit_code_only_fails_on_fail(capsys):
    report = smoke.Report()
    report.add("PASS", "a")
    report.add("WARN", "b", "careful")
    report.add("SKIP", "c")
    assert report.summary() == 0
    report.add("FAIL", "d")
    assert report.summary() == 1
    assert "1 failed" in capsys.readouterr().out

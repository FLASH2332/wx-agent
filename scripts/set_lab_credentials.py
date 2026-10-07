#!/usr/bin/env python3
"""Save Learner Lab credentials into a named AWS CLI profile (one profile per account).

Learner Lab -> "AWS Details" -> "Show" next to "AWS CLI" prints a block like

    [default]
    aws_access_key_id=ASIA...
    aws_secret_access_key=...
    aws_session_token=...

Run this, paste that block, then finish input (Ctrl+Z then Enter on Windows, Ctrl+D elsewhere):

    python scripts/set_lab_credentials.py wb-new
    python scripts/set_lab_credentials.py wb-existing

The credentials expire when the lab session ends (about 4 hours): run it again with a fresh block.
Nothing secret is printed.
"""

from __future__ import annotations

import argparse
import configparser
import os
import re
import subprocess
import sys
from pathlib import Path

KEYS = ("aws_access_key_id", "aws_secret_access_key", "aws_session_token")


def parse_credentials_block(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*(aws_access_key_id|aws_secret_access_key|aws_session_token)\s*=\s*(\S+)\s*$", line, re.I)
        if match:
            found[match.group(1).lower()] = match.group(2)
    missing = [k for k in KEYS if k not in found]
    if missing:
        raise ValueError(f"missing {', '.join(missing)} in the pasted text")
    return {k: found[k] for k in KEYS}


def _write_ini(path: Path, section: str, values: dict[str, str]) -> None:
    parser = configparser.RawConfigParser()
    if path.exists():
        parser.read(path)
    if not parser.has_section(section):
        parser.add_section(section)
    for key, value in values.items():
        parser.set(section, key, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as handle:
        parser.write(handle)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def write_profile(profile: str, creds: dict[str, str], region: str,
                  credentials_file: Path | None = None, config_file: Path | None = None) -> None:
    home = Path.home() / ".aws"
    credentials_file = credentials_file or Path(os.environ.get("AWS_SHARED_CREDENTIALS_FILE", home / "credentials"))
    config_file = config_file or Path(os.environ.get("AWS_CONFIG_FILE", home / "config"))
    _write_ini(credentials_file, profile, creds)
    _write_ini(config_file, "default" if profile == "default" else f"profile {profile}", {"region": region})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("profile", help="AWS CLI profile name, e.g. wb-new or wb-existing (see infra/environments.json)")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--no-verify", action="store_true", help="skip the sts get-caller-identity check")
    args = parser.parse_args()

    if sys.stdin.isatty():
        print("Paste the AWS CLI credentials block, then finish input (Ctrl+Z+Enter on Windows, Ctrl+D elsewhere):")
    try:
        creds = parse_credentials_block(sys.stdin.read())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    write_profile(args.profile, creds, args.region)
    print(f"saved profile '{args.profile}' (key ending ...{creds['aws_access_key_id'][-4:]}, region {args.region})")

    if not args.no_verify:
        result = subprocess.run(["aws", "sts", "get-caller-identity", "--profile", args.profile, "--query", "Account", "--output", "text"],
                                capture_output=True, text=True)
        if result.returncode == 0:
            print(f"verified: this profile is AWS account {result.stdout.strip()}")
        else:
            print("could not verify (is the AWS CLI installed, and are the credentials current?):", result.stderr.strip()[:200])
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

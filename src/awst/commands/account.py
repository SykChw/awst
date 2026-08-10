"""hello, account, config, login."""
from __future__ import annotations
import argparse
import json as _json
import sys
from awst import aws, fmt
from awst.config import Config
def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("hello", help="Sanity check — verify awst works")
    p.set_defaults(func=_hello)
    p = sub.add_parser("account", help="AWS caller identity")
    p.set_defaults(func=_account)
    p = sub.add_parser("config", help="Show profile, region, account, SSO status")
    p.set_defaults(func=_config)
    p = sub.add_parser("login", help="Run: aws sso login (delegates to AWS CLI)")
    p.set_defaults(func=_login)
def _hello(args: argparse.Namespace, cfg: Config) -> None:
    fmt.ok("awst is working")
    region = cfg.region
    profile = cfg.profile or "(default)"
    print(f"\n  Profile : {profile}")
    print(f"  Region  : {region}")
def _account(args: argparse.Namespace, cfg: Config) -> None:
    try:
        data = aws.j(["sts", "get-caller-identity"], **cfg.aws_args())
    except aws.AWSError as e:
        fmt.error_box("sts get-caller-identity failed", str(e),
                      hints=["SSO expired — run: awst login"])
        sys.exit(1)
    if cfg.json_out:
        print(_json.dumps({"account": data["Account"], "arn": data["Arn"], "user_id": data["UserId"]}, indent=2))
        return
    fmt.kv({"Account": data["Account"], "ARN": data["Arn"], "UserId": data["UserId"]},
           title="AWS Account")
def _config(args: argparse.Namespace, cfg: Config) -> None:
    profile = cfg.profile or "(default)"
    region = cfg.region
    cli_ver = aws.version()
    try:
        data = aws.j(["sts", "get-caller-identity"], **cfg.aws_args())
        account = data.get("Account", "-")
        sso = "authenticated"
    except aws.AWSError:
        account = "-"
        sso = "not authenticated — run: awst login"
    if cfg.json_out:
        print(_json.dumps({"profile": profile, "region": region,
                           "account": account, "cli": cli_ver, "sso": sso}, indent=2))
        return
    fmt.kv({"Profile": profile, "Region": region, "Account": account,
            "CLI": cli_ver, "SSO": sso}, title="awst config")
def _login(args: argparse.Namespace, cfg: Config) -> None:
    import subprocess
    cmd = ["aws", "sso", "login"]
    if cfg.profile:
        cmd += ["--profile", cfg.profile]
    print(f"  Running: {' '.join(cmd)}")
    subprocess.run(cmd)

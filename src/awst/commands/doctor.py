"""awst doctor — environment diagnostics."""
from __future__ import annotations
import argparse
import shutil
from awst import aws, fmt
from awst.config import Config
def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("doctor", help="Diagnose AWS environment")
    p.set_defaults(func=_doctor)
def _check(label: str, ok: bool, warn: bool = False, hint: str = "") -> None:
    if ok:
        fmt.ok(label)
    elif warn:
        fmt.warn(f"{label}" + (f"  [{hint}]" if hint else ""))
    else:
        fmt.err(label, hint)
def _doctor(args: argparse.Namespace, cfg: Config) -> None:
    fmt.heading("AWS Environment")
    # AWS CLI
    found = shutil.which("aws") is not None
    _check(f"AWS CLI  ({aws.version()})", found, hint="install AWS CLI v2")
    # jq (optional but useful)
    has_jq = shutil.which("jq") is not None
    _check("jq (optional)", has_jq, warn=not has_jq, hint="brew install jq")
    # STS / SSO
    ident = None
    try:
        ident = aws.j(["sts", "get-caller-identity"], **cfg.aws_args())
        _check(f"Credentials / SSO  (account {ident['Account']})", True)
    except aws.AWSError as e:
        _check("Credentials / SSO", False, hint="run: awst login")
    region = cfg.region
    _check(f"Region  ({region})", bool(region))
    def probe(label: str, args_: list[str], hint: str = "") -> None:
        try:
            aws.j(args_, **cfg.aws_args())
            _check(label, True)
        except aws.AWSError:
            _check(label, False, warn=True, hint=hint or "may be denied")
    probe("S3 list", ["s3api", "list-buckets"])
    probe("EC2 read", ["ec2", "describe-instances", "--max-results", "5"])
    probe("IAM instance profiles", ["iam", "list-instance-profiles", "--max-items", "1"])
    probe("VPC discovery", ["ec2", "describe-vpcs", "--max-results", "5"])
    probe("Subnet discovery", ["ec2", "describe-subnets", "--max-results", "5"])
    probe("Security groups", ["ec2", "describe-security-groups", "--max-results", "5"])
    fmt.warn("EC2 launch (ec2:RunInstances)  [verify with: awst launch cpu --dry-run]")
    print()
    if ident:
        fmt.ok("Ready.")
    else:
        fmt.err("Fix authentication first.", "awst login")

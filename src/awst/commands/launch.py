"""awst launch — propose and launch EC2 instances."""
from __future__ import annotations
import argparse
import json as _json
import sys
from awst import aws, fmt
from awst.config import Config
from awst.commands.ec2 import get_instances, tag
def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("launch", help="Launch an EC2 instance")
    s = p.add_subparsers(dest="launch_type", metavar="TYPE")
    pc = s.add_parser("cpu", help="Launch smallest CPU instance")
    pc.add_argument("--dry-run", action="store_true", help="Validate without launching")
    pc.add_argument("--type", default="t3.micro", help="Instance type (default: t3.micro)")
    pc.add_argument("--ami", default="", help="AMI ID (auto-discover if empty)")
    pc.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    pc.set_defaults(func=_launch_cpu)
    pg = s.add_parser("gpu", help="Launch a GPU instance")
    pg.add_argument("--dry-run", action="store_true", help="Validate without launching")
    pg.add_argument("--type", default="g4dn.xlarge", help="Instance type (default: g4dn.xlarge)")
    pg.add_argument("--ami", default="", help="AMI ID (auto-discover if empty)")
    pg.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    pg.set_defaults(func=_launch_gpu)
    p.set_defaults(func=lambda a, c: p.print_help())
def _discover_config(cfg: Config) -> dict:
    """Infer best launch config from existing instances."""
    instances = get_instances(cfg)
    if instances:
        # Use config from first real instance as template
        rep = instances[0]
        return {
            "subnet_id": rep.get("SubnetId", ""),
            "sg_ids": [sg["GroupId"] for sg in rep.get("SecurityGroups", [])],
            "key_name": rep.get("KeyName", ""),
            "iam_arn": (rep.get("IamInstanceProfile") or {}).get("Arn", ""),
        }
    # Fall back to first available resources
    config: dict = {"subnet_id": "", "sg_ids": [], "key_name": "", "iam_arn": ""}
    try:
        subnets = aws.j(["ec2", "describe-subnets"], **cfg.aws_args()).get("Subnets", [])
        if subnets:
            config["subnet_id"] = subnets[0]["SubnetId"]
    except aws.AWSError:
        pass
    try:
        sgs = aws.j(["ec2", "describe-security-groups"], **cfg.aws_args()).get("SecurityGroups", [])
        default_sg = next((sg for sg in sgs if sg["GroupName"] == "default"), None)
        if default_sg:
            config["sg_ids"] = [default_sg["GroupId"]]
    except aws.AWSError:
        pass
    try:
        keys = aws.j(["ec2", "describe-key-pairs"], **cfg.aws_args()).get("KeyPairs", [])
        if keys:
            config["key_name"] = keys[0]["KeyName"]
    except aws.AWSError:
        pass
    return config
def _find_ami(cfg: Config, gpu: bool = False) -> str:
    """Find most recent Amazon Linux 2 AMI (or GPU Deep Learning AMI)."""
    try:
        name_filter = "Deep Learning AMI*" if gpu else "amzn2-ami-hvm-*-x86_64-gp2"
        data = aws.j([
            "ec2", "describe-images",
            "--owners", "amazon",
            "--filters",
            f"Name=name,Values={name_filter}",
            "Name=state,Values=available",
            "--query", "sort_by(Images,&CreationDate)[-1].ImageId",
            "--output", "text",
        ], **cfg.aws_args())
        return str(data).strip() if data else ""
    except aws.AWSError:
        return ""
def _do_launch(args: argparse.Namespace, cfg: Config, gpu: bool) -> None:
    instance_type = args.type
    disk_config = _discover_config(cfg)
    ami = args.ami or _find_ami(cfg, gpu=gpu)
    if not ami:
        fmt.err("Could not find an AMI. Use --ami <ami-id> to specify one.")
        sys.exit(1)
    fmt.heading("Proposed Instance")
    proposal = {
        "Type":   instance_type,
        "AMI":    ami,
        "Subnet": disk_config["subnet_id"] or "(none — will use default)",
        "SGs":    ", ".join(disk_config["sg_ids"]) or "(none)",
        "Key":    disk_config["key_name"] or "(none)",
        "IAM":    disk_config["iam_arn"].split("/")[-1] if disk_config["iam_arn"] else "(none)",
        "Mode":   "DRY-RUN" if args.dry_run else "LIVE",
    }
    fmt.kv(proposal)
    if args.dry_run:
        print()
        fmt.warn("Dry-run: validating with AWS …")
        launch_args = _build_launch_args(instance_type, ami, disk_config) + ["--dry-run"]
        try:
            aws.run(launch_args, **cfg.aws_args())
            fmt.ok("Dry-run passed — launch would succeed")
        except aws.AWSError as e:
            if "DryRunOperation" in str(e):
                fmt.ok("Dry-run passed — launch would succeed (DryRunOperation)")
            else:
                fmt.error_box("Dry-run failed", str(e))
        return
    if not args.yes:
        if not fmt.confirm("Launch this instance?", default=False):
            print("  Aborted.")
            return
    try:
        result = aws.j(_build_launch_args(instance_type, ami, disk_config), **cfg.aws_args())
        iid = result["Instances"][0]["InstanceId"]
        fmt.ok(f"Launched: {iid}")
        print(f"\n  awst ec2 inspect {iid}")
        print(f"  awst ssh {iid}")
    except aws.AWSError as e:
        fmt.error_box("Launch failed", str(e), hints=[
            "Missing ec2:RunInstances permission",
            "Missing iam:PassRole permission",
            "Invalid subnet or security group",
            "Instance type unavailable in this AZ",
            "Service quota exceeded",
        ])
        sys.exit(1)
def _build_launch_args(instance_type: str, ami: str, disk_config: dict) -> list[str]:
    args = ["ec2", "run-instances",
            "--instance-type", instance_type,
            "--image-id", ami,
            "--count", "1"]
    if disk_config["subnet_id"]:
        args += ["--subnet-id", disk_config["subnet_id"]]
    if disk_config["sg_ids"]:
        args += ["--security-group-ids"] + disk_config["sg_ids"]
    if disk_config["key_name"]:
        args += ["--key-name", disk_config["key_name"]]
    if disk_config["iam_arn"]:
        args += ["--iam-instance-profile", f"Arn={disk_config['iam_arn']}"]
    return args
def _launch_cpu(args: argparse.Namespace, cfg: Config) -> None:
    _do_launch(args, cfg, gpu=False)
def _launch_gpu(args: argparse.Namespace, cfg: Config) -> None:
    _do_launch(args, cfg, gpu=True)

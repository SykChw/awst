"""EC2 discovery and inspection commands."""
from __future__ import annotations
import argparse
import json as _json
import sys
from awst import aws, fmt
from awst.config import Config
def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("ec2", help="EC2 instance commands")
    s = p.add_subparsers(dest="ec2_cmd", metavar="SUBCOMMAND")
    s.add_parser("list", help="All instances (default)").set_defaults(func=_list)
    s.add_parser("running", help="Running instances + uptime").set_defaults(func=_running)
    s.add_parser("stopped", help="Stopped instances").set_defaults(func=_stopped)
    pi = s.add_parser("inspect", help="Detailed view of one instance")
    pi.add_argument("instance_id", help="Instance ID")
    pi.set_defaults(func=_inspect)
    s.add_parser("configs", help="Group existing instances into known-good configs").set_defaults(func=_configs)
    p.set_defaults(func=lambda a, c: (_list(a, c)))
def _get_instances(cfg: Config, state: str | None = None) -> list[dict]:
    args = ["ec2", "describe-instances"]
    if state:
        args += ["--filters", f"Name=instance-state-name,Values={state}"]
    data = aws.j(args, **cfg.aws_args())
    instances = []
    for r in data.get("Reservations", []):
        instances.extend(r.get("Instances", []))
    return instances
def _tag(inst: dict, key: str = "Name") -> str:
    for t in inst.get("Tags", []):
        if t["Key"] == key:
            return t["Value"]
    return "-"
def _list(args: argparse.Namespace, cfg: Config) -> None:
    try:
        instances = _get_instances(cfg)
    except aws.AWSError as e:
        fmt.error_box("EC2 describe-instances failed", str(e))
        sys.exit(1)
    if cfg.json_out:
        print(_json.dumps([_compact(i) for i in instances], indent=2))
        return
    rows = [[i["InstanceId"], _tag(i), i["InstanceType"],
             i["State"]["Name"], i["Placement"]["AvailabilityZone"],
             i.get("PublicIpAddress", "-")] for i in instances]
    fmt.table(["ID", "NAME", "TYPE", "STATE", "AZ", "PUBLIC_IP"], rows, title="EC2 Instances")
def _running(args: argparse.Namespace, cfg: Config) -> None:
    try:
        instances = _get_instances(cfg, "running")
    except aws.AWSError as e:
        fmt.error_box("EC2 describe-instances failed", str(e))
        sys.exit(1)
    if cfg.json_out:
        print(_json.dumps([_compact(i) for i in instances], indent=2))
        return
    rows = [[i["InstanceId"], _tag(i), i["InstanceType"],
             i["Placement"]["AvailabilityZone"],
             fmt.fmt_uptime(i.get("LaunchTime", ""))] for i in instances]
    fmt.table(["ID", "NAME", "TYPE", "AZ", "UPTIME"], rows, title="Running Instances")
def _stopped(args: argparse.Namespace, cfg: Config) -> None:
    try:
        instances = _get_instances(cfg, "stopped")
    except aws.AWSError as e:
        fmt.error_box("EC2 describe-instances failed", str(e))
        sys.exit(1)
    if cfg.json_out:
        print(_json.dumps([_compact(i) for i in instances], indent=2))
        return
    rows = [[i["InstanceId"], _tag(i), i["InstanceType"]] for i in instances]
    fmt.table(["ID", "NAME", "TYPE"], rows, title="Stopped Instances")
def _inspect(args: argparse.Namespace, cfg: Config) -> None:
    try:
        data = aws.j(["ec2", "describe-instances", "--instance-ids", args.instance_id], **cfg.aws_args())
    except aws.AWSError as e:
        fmt.error_box(f"Cannot inspect {args.instance_id}", str(e))
        sys.exit(1)
    reservations = data.get("Reservations", [])
    if not reservations:
        fmt.err(f"Instance not found: {args.instance_id}")
        sys.exit(1)
    i = reservations[0]["Instances"][0]
    if cfg.json_out:
        print(_json.dumps(i, indent=2, default=str))
        return
    iam_arn = (i.get("IamInstanceProfile") or {}).get("Arn", "-")
    sgs = ", ".join(sg["GroupId"] for sg in i.get("SecurityGroups", []))
    fmt.kv({
        "Name":    _tag(i),
        "State":   i["State"]["Name"],
        "Type":    i["InstanceType"],
        "AZ":      i["Placement"]["AvailabilityZone"],
        "AMI":     i["ImageId"],
        "VPC":     i.get("VpcId", "-"),
        "Subnet":  i.get("SubnetId", "-"),
        "SGs":     sgs or "-",
        "IAM":     iam_arn.split("/")[-1] if iam_arn != "-" else "-",
        "Key":     i.get("KeyName", "-"),
        "Public":  i.get("PublicIpAddress", "-"),
        "Private": i.get("PrivateIpAddress", "-"),
    }, title=f"Instance {args.instance_id}")
def _configs(args: argparse.Namespace, cfg: Config) -> None:
    try:
        instances = _get_instances(cfg)
    except aws.AWSError as e:
        fmt.error_box("EC2 describe-instances failed", str(e))
        sys.exit(1)
    groups: dict[str, list[dict]] = {}
    for i in instances:
        key = "|".join([
            i["InstanceType"],
            i["ImageId"],
            i.get("SubnetId", "-"),
            ",".join(sorted(sg["GroupId"] for sg in i.get("SecurityGroups", []))),
            (i.get("IamInstanceProfile") or {}).get("Arn", "-").split("/")[-1],
            i.get("KeyName", "-"),
        ])
        groups.setdefault(key, []).append(i)
    sorted_groups = sorted(groups.values(), key=len, reverse=True)
    if cfg.json_out:
        print(_json.dumps([[_compact(i) for i in g] for g in sorted_groups], indent=2))
        return
    fmt.heading("Known EC2 configurations")
    if not sorted_groups:
        print("  (no instances — no configs to infer)")
        return
    for n, group in enumerate(sorted_groups, 1):
        rep = group[0]
        states = ", ".join(sorted({i["State"]["Name"] for i in group}))
        ids = " ".join(i["InstanceId"] for i in group)
        sgs = ", ".join(sorted(sg["GroupId"] for sg in rep.get("SecurityGroups", [])))
        iam = (rep.get("IamInstanceProfile") or {}).get("Arn", "-").split("/")[-1]
        print(f"\n  #{n}  ({len(group)} instance{'s' if len(group) > 1 else ''}, states: {states})")
        fmt.kv({
            "Type":   rep["InstanceType"],
            "AMI":    rep["ImageId"],
            "Subnet": rep.get("SubnetId", "-"),
            "SGs":    sgs or "-",
            "IAM":    iam,
            "Key":    rep.get("KeyName", "-"),
            "IDs":    ids,
        })
def _compact(i: dict) -> dict:
    return {
        "id": i["InstanceId"],
        "name": next((t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), None),
        "type": i["InstanceType"],
        "state": i["State"]["Name"],
        "az": i["Placement"]["AvailabilityZone"],
        "public_ip": i.get("PublicIpAddress"),
        "private_ip": i.get("PrivateIpAddress"),
        "ami": i["ImageId"],
        "key": i.get("KeyName"),
        "launch_time": str(i.get("LaunchTime", "")),
    }
# Exported helper for other commands
def get_instances(cfg: Config, state: str | None = None) -> list[dict]:
    return _get_instances(cfg, state)
def tag(inst: dict, key: str = "Name") -> str:
    return _tag(inst, key)

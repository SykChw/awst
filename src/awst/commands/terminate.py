"""awst terminate — safely stop or terminate instances."""
from __future__ import annotations
import argparse
import json as _json
import sys
from awst import aws, fmt
from awst.config import Config
from awst.commands.ec2 import get_instances, tag
def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("terminate", help="Terminate an instance (with confirmation)")
    p.add_argument("instance_id", nargs="?", help="Instance ID (interactive if omitted)")
    p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    p.add_argument("--stop", action="store_true", help="Stop instead of terminate")
    p.add_argument("--dry-run", action="store_true", help="Validate without acting")
    p.set_defaults(func=_terminate)
    ps = sub.add_parser("stop", help="Stop an instance (with confirmation)")
    ps.add_argument("instance_id", nargs="?", help="Instance ID (interactive if omitted)")
    ps.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    ps.add_argument("--dry-run", action="store_true", help="Validate without acting")
    ps.set_defaults(func=_stop_cmd)
def _pick_instance(cfg: Config) -> str | None:
    instances = get_instances(cfg, "running") + get_instances(cfg, "stopped")
    if not instances:
        fmt.err("No instances found")
        return None
    options = [(i["InstanceId"], f"{tag(i):<30} {i['InstanceType']:<14} {i['State']['Name']}")
               for i in instances]
    idx = fmt.pick("Select instance:", options)
    if idx is None:
        return None
    return instances[idx]["InstanceId"]
def _show_instance(cfg: Config, iid: str) -> dict | None:
    try:
        data = aws.j(["ec2", "describe-instances", "--instance-ids", iid], **cfg.aws_args())
    except aws.AWSError as e:
        fmt.error_box(f"Cannot find {iid}", str(e))
        return None
    reservations = data.get("Reservations", [])
    if not reservations:
        return None
    i = reservations[0]["Instances"][0]
    fmt.kv({
        "ID":    i["InstanceId"],
        "Name":  tag(i),
        "Type":  i["InstanceType"],
        "State": i["State"]["Name"],
        "AZ":    i["Placement"]["AvailabilityZone"],
    })
    return i
def _terminate(args: argparse.Namespace, cfg: Config) -> None:
    iid = args.instance_id or _pick_instance(cfg)
    if not iid:
        sys.exit(1)
    i = _show_instance(cfg, iid)
    if not i:
        sys.exit(1)
    action = "stop" if getattr(args, "stop", False) else "TERMINATE"
    if args.dry_run:
        fmt.warn(f"Dry-run: would {action.lower()} {iid}")
        return
    if not args.yes:
        print(f"\n  [bold red]This cannot be undone.[/bold red]" if False else "")
        if not fmt.confirm(f"{action} {iid}?", default=False):
            print("  Aborted.")
            return
    try:
        if action == "stop":
            result = aws.j(["ec2", "stop-instances", "--instance-ids", iid], **cfg.aws_args())
            new_state = result["StoppingInstances"][0]["CurrentState"]["Name"]
        else:
            result = aws.j(["ec2", "terminate-instances", "--instance-ids", iid], **cfg.aws_args())
            new_state = result["TerminatingInstances"][0]["CurrentState"]["Name"]
        fmt.ok(f"{iid} → {new_state}")
    except aws.AWSError as e:
        fmt.error_box(f"{action} failed", str(e))
        sys.exit(1)
def _stop_cmd(args: argparse.Namespace, cfg: Config) -> None:
    args.stop = True
    _terminate(args, cfg)

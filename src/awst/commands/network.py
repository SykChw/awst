"""VPC / subnet / security group discovery."""
from __future__ import annotations
import argparse
import json as _json
import sys
from awst import aws, fmt
from awst.config import Config
def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("network", help="Network discovery (vpcs / subnets / sgs)")
    s = p.add_subparsers(dest="net_cmd", metavar="SUBCOMMAND")
    s.add_parser("vpcs", help="List VPCs").set_defaults(func=_vpcs)
    s.add_parser("subnets", help="List subnets").set_defaults(func=_subnets)
    s.add_parser("sgs", help="List security groups").set_defaults(func=_sgs)
    p.set_defaults(func=_summary)
def _summary(args: argparse.Namespace, cfg: Config) -> None:
    try:
        vpcs = len(aws.j(["ec2", "describe-vpcs"], **cfg.aws_args()).get("Vpcs", []))
        subnets = len(aws.j(["ec2", "describe-subnets"], **cfg.aws_args()).get("Subnets", []))
        sgs = len(aws.j(["ec2", "describe-security-groups"], **cfg.aws_args()).get("SecurityGroups", []))
    except aws.AWSError as e:
        fmt.error_box("Network discovery failed", str(e))
        sys.exit(1)
    fmt.kv({"VPCs": vpcs, "Subnets": subnets, "Security groups": sgs}, title="Network Summary")
    print("\n  Detail: awst network vpcs | subnets | sgs")
def _vpcs(args: argparse.Namespace, cfg: Config) -> None:
    try:
        vpcs = aws.j(["ec2", "describe-vpcs"], **cfg.aws_args()).get("Vpcs", [])
    except aws.AWSError as e:
        fmt.error_box("describe-vpcs failed", str(e))
        sys.exit(1)
    if cfg.json_out:
        print(_json.dumps([{"id": v["VpcId"], "cidr": v["CidrBlock"],
                            "default": v["IsDefault"]} for v in vpcs], indent=2))
        return
    rows = [[v["VpcId"], v["CidrBlock"], str(v["IsDefault"])] for v in vpcs]
    fmt.table(["VPC", "CIDR", "DEFAULT"], rows, title="VPCs")
def _subnets(args: argparse.Namespace, cfg: Config) -> None:
    try:
        subnets = aws.j(["ec2", "describe-subnets"], **cfg.aws_args()).get("Subnets", [])
    except aws.AWSError as e:
        fmt.error_box("describe-subnets failed", str(e))
        sys.exit(1)
    if cfg.json_out:
        print(_json.dumps([{
            "id": s["SubnetId"], "vpc": s["VpcId"], "az": s["AvailabilityZone"],
            "cidr": s["CidrBlock"], "free_ips": s["AvailableIpAddressCount"],
            "public": s.get("MapPublicIpOnLaunch", False),
        } for s in subnets], indent=2))
        return
    rows = [[s["SubnetId"], s["VpcId"], s["AvailabilityZone"], s["CidrBlock"],
             str(s["AvailableIpAddressCount"]),
             "public" if s.get("MapPublicIpOnLaunch") else "private"] for s in subnets]
    fmt.table(["SUBNET", "VPC", "AZ", "CIDR", "FREE_IPS", "TYPE"], rows, title="Subnets")
def _sgs(args: argparse.Namespace, cfg: Config) -> None:
    try:
        sgs = aws.j(["ec2", "describe-security-groups"], **cfg.aws_args()).get("SecurityGroups", [])
    except aws.AWSError as e:
        fmt.error_box("describe-security-groups failed", str(e))
        sys.exit(1)
    if cfg.json_out:
        print(_json.dumps([{
            "id": sg["GroupId"], "name": sg["GroupName"], "vpc": sg.get("VpcId"),
            "inbound": len(sg.get("IpPermissions", [])),
            "outbound": len(sg.get("IpPermissionsEgress", [])),
        } for sg in sgs], indent=2))
        return
    rows = [[sg["GroupId"], sg["GroupName"][:40], sg.get("VpcId", "-"),
             str(len(sg.get("IpPermissions", []))),
             str(len(sg.get("IpPermissionsEgress", [])))] for sg in sgs]
    fmt.table(["ID", "NAME", "VPC", "IN", "OUT"], rows, title="Security Groups")

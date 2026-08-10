"""Instance type discovery (awst types)."""
from __future__ import annotations
import argparse
import json as _json
import sys
from awst import aws, fmt
from awst.config import Config
def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("types", help="Instance types (optionally filter by prefix)")
    p.add_argument("prefix", nargs="?", default="", help="Filter prefix e.g. g4, t3")
    p.set_defaults(func=_types)
def _types(args: argparse.Namespace, cfg: Config) -> None:
    try:
        data = aws.j(["ec2", "describe-instance-types"], **cfg.aws_args())
    except aws.AWSError as e:
        fmt.error_box("describe-instance-types failed", str(e))
        sys.exit(1)
    types = data.get("InstanceTypes", [])
    if args.prefix:
        types = [t for t in types if t["InstanceType"].startswith(args.prefix)]
    types.sort(key=lambda t: t["InstanceType"])
    if cfg.json_out:
        print(_json.dumps([{
            "type": t["InstanceType"],
            "vcpu": t["VCpuInfo"]["DefaultVCpus"],
            "memory_mib": t["MemoryInfo"]["SizeInMiB"],
            "gpus": len(t.get("GpuInfo", {}).get("Gpus", [])),
        } for t in types], indent=2))
        return
    rows = [[
        t["InstanceType"],
        str(t["VCpuInfo"]["DefaultVCpus"]),
        fmt.fmt_mib(t["MemoryInfo"]["SizeInMiB"]),
        str(len(t.get("GpuInfo", {}).get("Gpus", []))),
    ] for t in types]
    fmt.table(["TYPE", "vCPU", "RAM", "GPUs"], rows, title="Instance Types")

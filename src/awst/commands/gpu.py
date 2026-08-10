"""GPU instance type discovery."""
from __future__ import annotations
import argparse
import json as _json
import sys
from awst import aws, fmt
from awst.config import Config
def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("gpu", help="GPU instance types + AZ availability")
    p.set_defaults(func=_gpu)
def _gpu(args: argparse.Namespace, cfg: Config) -> None:
    region = cfg.region
    try:
        types_data = aws.j(["ec2", "describe-instance-types"], **cfg.aws_args())
    except aws.AWSError as e:
        fmt.error_box("describe-instance-types failed", str(e))
        sys.exit(1)
    gpu_types = [
        t for t in types_data.get("InstanceTypes", [])
        if t.get("GpuInfo", {}).get("Gpus")
    ]
    if not gpu_types:
        print(f"  No GPU instance types found in {region}")
        return
    type_names = ",".join(t["InstanceType"] for t in gpu_types)
    try:
        offerings_data = aws.j([
            "ec2", "describe-instance-type-offerings",
            "--location-type", "availability-zone",
            "--filters", f"Name=instance-type,Values={type_names}",
        ], **cfg.aws_args())
        offerings = offerings_data.get("InstanceTypeOfferings", [])
    except aws.AWSError:
        offerings = []
    az_map: dict[str, list[str]] = {}
    for o in offerings:
        az_map.setdefault(o["InstanceType"], []).append(o["Location"])
    if cfg.json_out:
        print(_json.dumps([{
            "type": t["InstanceType"],
            "vcpu": t["VCpuInfo"]["DefaultVCpus"],
            "memory_gb": t["MemoryInfo"]["SizeInMiB"] // 1024,
            "gpu_count": len(t["GpuInfo"]["Gpus"]),
            "gpu_name": t["GpuInfo"]["Gpus"][0].get("Name", "-"),
            "azs": az_map.get(t["InstanceType"], []),
        } for t in sorted(gpu_types, key=lambda t: t["InstanceType"])], indent=2))
        return
    rows = []
    for t in sorted(gpu_types, key=lambda t: t["InstanceType"]):
        gpus = t["GpuInfo"]["Gpus"]
        gpu_str = f"{len(gpus)}x {gpus[0].get('Name', '?')}"
        azs = ", ".join(az_map.get(t["InstanceType"], ["-"]))
        rows.append([
            t["InstanceType"],
            str(t["VCpuInfo"]["DefaultVCpus"]),
            fmt.fmt_mib(t["MemoryInfo"]["SizeInMiB"]),
            gpu_str,
            azs,
        ])
    fmt.table(["TYPE", "vCPU", "RAM", "GPU", "AZs"], rows, title=f"GPU Types ({region})")

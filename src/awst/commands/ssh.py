"""awst ssh — interactive SSH into running instances."""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
from awst import aws, fmt
from awst.config import Config
from awst.commands.ec2 import get_instances, tag
DEFAULT_USERS = ["ec2-user", "ubuntu", "admin", "centos", "fedora"]
def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("ssh", help="SSH into a running instance")
    p.add_argument("instance_id", nargs="?", help="Instance ID (interactive if omitted)")
    p.add_argument("--user", "-u", default="", help="SSH user (default: auto-detect)")
    p.add_argument("--key", "-i", default="", help="Path to private key")
    p.add_argument("--cmd", "-c", default="", help="Run command instead of interactive shell")
    p.add_argument("--print-only", action="store_true", help="Print SSH command, don't run it")
    p.set_defaults(func=_ssh)
def _find_key(key_name: str) -> str:
    """Try ~/.ssh/<keyname>.pem and ~/.ssh/<keyname>."""
    if not key_name or key_name == "-":
        return ""
    candidates = [
        os.path.expanduser(f"~/.ssh/{key_name}.pem"),
        os.path.expanduser(f"~/.ssh/{key_name}"),
        os.path.expanduser(f"~/.ssh/id_rsa"),
        os.path.expanduser(f"~/.ssh/id_ed25519"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return ""
def _pick_instance(cfg: Config) -> dict | None:
    instances = get_instances(cfg, "running")
    if not instances:
        fmt.err("No running instances found")
        return None
    options = [(i["InstanceId"],
                f"{tag(i):<30} {i['InstanceType']:<14} {i.get('PublicIpAddress') or i.get('PrivateIpAddress', '-')}")
               for i in instances]
    idx = fmt.pick("Select instance to SSH into:", options)
    if idx is None:
        return None
    return instances[idx]
def _ssh(args: argparse.Namespace, cfg: Config) -> None:
    if args.instance_id:
        try:
            data = aws.j(["ec2", "describe-instances", "--instance-ids", args.instance_id],
                         **cfg.aws_args())
            inst = data["Reservations"][0]["Instances"][0]
        except (aws.AWSError, IndexError, KeyError):
            fmt.err(f"Instance not found: {args.instance_id}")
            sys.exit(1)
    else:
        inst = _pick_instance(cfg)
        if not inst:
            sys.exit(1)
    host = inst.get("PublicIpAddress") or inst.get("PrivateIpAddress")
    if not host:
        fmt.err("No IP address found on instance")
        fmt.warn("Instance may not have a public IP — check VPC/subnet settings")
        sys.exit(1)
    key_name = inst.get("KeyName", "")
    key_path = args.key or _find_key(key_name)
    user = args.user or _guess_user(inst)
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new"]
    if key_path:
        ssh_cmd += ["-i", key_path]
    ssh_cmd.append(f"{user}@{host}")
    if args.cmd:
        ssh_cmd.append(args.cmd)
    fmt.kv({"Host": host, "User": user, "Key": key_path or "(ssh-agent)", "Instance": inst["InstanceId"]})
    print()
    if args.print_only:
        print("  " + " ".join(ssh_cmd))
        return
    fmt.ok(f"Connecting to {user}@{host} …")
    os.execvp("ssh", ssh_cmd)
def _guess_user(inst: dict) -> str:
    """Guess SSH user from AMI name heuristics."""
    ami_id = inst.get("ImageId", "")
    # Try to get AMI name
    try:
        import subprocess as sp
        r = sp.run(["aws", "ec2", "describe-images", "--image-ids", ami_id,
                    "--query", "Images[0].Name", "--output", "text"],
                   capture_output=True, text=True, timeout=10)
        name = r.stdout.strip().lower()
        if "ubuntu" in name:
            return "ubuntu"
        if "amazon" in name or "amzn" in name:
            return "ec2-user"
        if "centos" in name:
            return "centos"
        if "fedora" in name:
            return "fedora"
        if "debian" in name:
            return "admin"
    except Exception:
        pass
    return "ec2-user"

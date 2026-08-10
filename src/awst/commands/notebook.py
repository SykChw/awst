"""EC2 notebook domain: awst notebook tunnel — Jupyter on EC2 via SSH."""
from __future__ import annotations
import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from awst import aws, fmt
from awst.config import Config
from awst.commands.ec2 import get_instances, tag
from awst.commands.ssh import _find_key, _guess_user
def register(sub: argparse._SubParsersAction) -> None:
    nb = sub.add_parser(
        "notebook",
        help="Jupyter on EC2 via SSH tunnel (SageMaker: awst sm notebook)",
    )
    s = nb.add_subparsers(dest="notebook_action", metavar="ACTION")
    t = s.add_parser("tunnel", help="SSH tunnel to Jupyter on a running EC2 instance")
    t.add_argument("--instance", "-i", default="", help="Instance ID (interactive if omitted)")
    t.add_argument("--user", "-u", default="", help="SSH user")
    t.add_argument("--key", "-k", default="", help="Path to private key")
    t.add_argument("--port", "-p", type=int, default=8888, help="Local port (default: 8888)")
    t.add_argument("--remote-port", type=int, default=8888, help="Remote Jupyter port")
    t.add_argument("--no-browser", action="store_true", help="Don't open browser")
    t.add_argument("--start-jupyter", action="store_true",
                   help="Start Jupyter on remote before tunnelling")
    t.set_defaults(func=_tunnel)
    nb.set_defaults(func=_notebook_help)
def _notebook_help(args: argparse.Namespace, cfg: Config) -> None:
    print("Usage: awst notebook tunnel [options]")
    print("  SSH tunnel localhost:8888 → Jupyter on an EC2 instance.")
    print("  SageMaker managed notebooks: awst sm notebook list|start|stop")
def _pick_instance(cfg: Config) -> dict | None:
    instances = get_instances(cfg, "running")
    if not instances:
        fmt.err("No running instances found")
        return None
    options = [(i["InstanceId"],
                f"{tag(i):<30} {i['InstanceType']:<14} {i.get('PublicIpAddress') or i.get('PrivateIpAddress', '-')}")
               for i in instances]
    idx = fmt.pick("Select instance:", options)
    return instances[idx] if idx is not None else None
def _tunnel(args: argparse.Namespace, cfg: Config) -> None:
    if args.instance:
        try:
            data = aws.j(["ec2", "describe-instances", "--instance-ids", args.instance],
                         **cfg.aws_args())
            inst = data["Reservations"][0]["Instances"][0]
        except (aws.AWSError, IndexError, KeyError):
            fmt.err(f"Instance not found: {args.instance}")
            sys.exit(1)
    else:
        inst = _pick_instance(cfg)
        if not inst:
            sys.exit(1)
    host = inst.get("PublicIpAddress") or inst.get("PrivateIpAddress")
    if not host:
        fmt.err("No IP address on instance")
        sys.exit(1)
    key_path = args.key or _find_key(inst.get("KeyName", ""))
    user = args.user or _guess_user(inst)
    local_port = args.port
    remote_port = args.remote_port
    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=accept-new"]
    if key_path:
        ssh_base += ["-i", key_path]
    if args.start_jupyter:
        fmt.ok("Starting Jupyter on remote …")
        start_cmd = ssh_base + [f"{user}@{host}",
            f"nohup jupyter lab --no-browser --port={remote_port} "
            f"--ip=127.0.0.1 --NotebookApp.token='' "
            f"> ~/jupyter.log 2>&1 &"]
        subprocess.run(start_cmd)
        time.sleep(3)
    tunnel_cmd = ssh_base + [
        "-N", "-L", f"{local_port}:127.0.0.1:{remote_port}",
        f"{user}@{host}",
    ]
    url = f"http://localhost:{local_port}"
    fmt.kv({
        "Instance": inst["InstanceId"],
        "Host":     host,
        "User":     user,
        "Tunnel":   f"localhost:{local_port} → {host}:{remote_port}",
        "URL":      url,
    }, title="EC2 notebook (SSH tunnel)")
    print()
    fmt.ok(f"Tunnel open → {url}")
    print("  Press Ctrl-C to close tunnel\n")
    if not args.no_browser:
        _open_browser(url)
    tunnel = subprocess.Popen(tunnel_cmd)
    try:
        tunnel.wait()
    except KeyboardInterrupt:
        tunnel.send_signal(signal.SIGTERM)
        fmt.ok("Tunnel closed")
def _open_browser(url: str) -> None:
    for cmd in ["open", "xdg-open", "start"]:
        if shutil.which(cmd):
            subprocess.Popen([cmd, url])
            return

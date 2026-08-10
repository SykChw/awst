"""awst sync — rsync local code to a running EC2 instance."""
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import sys
from awst import aws, fmt
from awst.config import Config
from awst.commands.ec2 import get_instances, tag
from awst.commands.ssh import _find_key, _guess_user
def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("sync", help="Sync local directory to EC2 via rsync")
    p.add_argument("local", nargs="?", default=".", help="Local path (default: current dir)")
    p.add_argument("remote", nargs="?", default="~/code", help="Remote path (default: ~/code)")
    p.add_argument("--instance", "-i", default="", help="Instance ID (interactive if omitted)")
    p.add_argument("--user", "-u", default="", help="SSH user")
    p.add_argument("--key", "-k", default="", help="Path to private key")
    p.add_argument("--watch", "-w", action="store_true", help="Watch and re-sync on change (requires watchdog)")
    p.add_argument("--dry-run", action="store_true", help="Show what would be synced")
    p.add_argument("--exclude", action="append", default=[], metavar="PAT",
                   help="Exclude pattern (may repeat). Defaults: .git, __pycache__, *.pyc")
    p.set_defaults(func=_sync)
DEFAULT_EXCLUDES = [".git", "__pycache__", "*.pyc", ".pytest_cache", ".venv", "venv", "*.egg-info", ".DS_Store"]
def _pick_instance(cfg: Config) -> dict | None:
    instances = get_instances(cfg, "running")
    if not instances:
        fmt.err("No running instances found")
        return None
    options = [(i["InstanceId"],
                f"{tag(i):<30} {i['InstanceType']:<14} {i.get('PublicIpAddress') or i.get('PrivateIpAddress', '-')}")
               for i in instances]
    idx = fmt.pick("Select target instance:", options)
    return instances[idx] if idx is not None else None
def _sync(args: argparse.Namespace, cfg: Config) -> None:
    if not shutil.which("rsync"):
        fmt.err("rsync not found", "brew install rsync")
        sys.exit(1)
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
    local = os.path.expanduser(args.local).rstrip("/") + "/"
    remote = f"{user}@{host}:{args.remote}"
    excludes = DEFAULT_EXCLUDES + args.exclude
    rsync_cmd = ["rsync", "-avz", "--progress"]
    if args.dry_run:
        rsync_cmd.append("--dry-run")
    for ex in excludes:
        rsync_cmd += ["--exclude", ex]
    if key_path:
        rsync_cmd += ["-e", f"ssh -i {key_path} -o StrictHostKeyChecking=accept-new"]
    else:
        rsync_cmd += ["-e", "ssh -o StrictHostKeyChecking=accept-new"]
    rsync_cmd += [local, remote]
    fmt.kv({
        "Local":    local,
        "Remote":   remote,
        "Instance": inst["InstanceId"],
        "Dry-run":  str(args.dry_run),
    }, title="Sync")
    print()
    if args.watch:
        _watch_sync(rsync_cmd, local)
    else:
        result = subprocess.run(rsync_cmd)
        if result.returncode == 0:
            fmt.ok("Sync complete")
        else:
            fmt.err(f"rsync exited {result.returncode}")
            sys.exit(result.returncode)
def _watch_sync(rsync_cmd: list[str], watch_path: str) -> None:
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        fmt.err("watchdog not installed", "pip install watchdog")
        sys.exit(1)
    import time
    class Handler(FileSystemEventHandler):
        def __init__(self) -> None:
            self._pending = False
        def on_any_event(self, event):
            if not event.is_directory:
                self._pending = True
    fmt.ok(f"Watching {watch_path} — Ctrl-C to stop")
    handler = Handler()
    observer = Observer()
    observer.schedule(handler, watch_path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(2)
            if handler._pending:
                handler._pending = False
                subprocess.run(rsync_cmd + ["--quiet"])
                fmt.ok("Synced")
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

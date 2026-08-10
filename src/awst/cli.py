"""awst — lightweight AWS CLI wrapper."""
from __future__ import annotations
import argparse
import subprocess
import sys
from awst import aws, fmt
from awst import __version__
from awst.config import Config
from awst.commands import (
    account, doctor, ec2, network,
    images, gpu, types_cmd,
    launch, ssh, sync, terminate, notebook, sagemaker,
)
# Top-level domains handled by awst (everything else → aws passthrough).
awst_COMMANDS = frozenset({
    "hello", "account", "config", "login",
    "doctor",
    "ec2", "network", "images", "gpu", "types",
    "launch", "ssh", "sync", "stop", "terminate",
    "notebook", "sm",
})
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="awst",
        description="AWS CLI wrapper — compact grammar for common tasks; passthrough for the rest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
grammar:  awst [globals] <domain> <resource?> <action?> [target] [flags]
  awst ec2 running --json
  awst sm notebook list
  awst sm notebook start my-nb --yes
  awst notebook tunnel --instance i-xxxx
  awst s3 ls                              # passthrough
  awst aws sts get-caller-identity        # explicit passthrough
Run: awst <domain> -h  for subcommands.  See README.md for full grammar.
""",
    )
    parser.add_argument("--profile", metavar="NAME",
                        help="AWS profile (or AWS_PROFILE)")
    parser.add_argument("--region", metavar="NAME", help="Override region")
    parser.add_argument("--debug", action="store_true",
                        help="Print aws commands (no secrets)")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="JSON output (awst commands only)")
    parser.add_argument("--version", action="version", version=f"awst {__version__}")
    sub = parser.add_subparsers(dest="cmd", metavar="DOMAIN")
    account.register(sub)
    doctor.register(sub)
    ec2.register(sub)
    network.register(sub)
    images.register(sub)
    gpu.register(sub)
    types_cmd.register(sub)
    launch.register(sub)
    ssh.register(sub)
    sync.register(sub)
    terminate.register(sub)
    notebook.register(sub)
    sagemaker.register(sub)
    return parser
def _split_argv(argv: list[str]) -> tuple[dict, list[str]]:
    flags = {"profile": None, "region": None, "debug": False, "json_out": False, "version": False}
    rest: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--json":
            flags["json_out"] = True
        elif arg == "--debug":
            flags["debug"] = True
        elif arg == "--version":
            flags["version"] = True
        elif arg == "--profile" and i + 1 < len(argv):
            flags["profile"] = argv[i + 1]
            i += 1
        elif arg == "--region" and i + 1 < len(argv):
            flags["region"] = argv[i + 1]
            i += 1
        else:
            rest.append(arg)
        i += 1
    return flags, rest
def _config_from_flags(flags: dict) -> Config:
    return Config(
        profile=flags["profile"],
        region=flags["region"],
        debug=flags["debug"],
        json_out=flags["json_out"],
    )
def _passthrough(aws_args: list[str], cfg: Config) -> None:
    cmd = ["aws"]
    if cfg.profile:
        cmd += ["--profile", cfg.profile]
    if cfg._region:
        cmd += ["--region", cfg._region]
    cmd += aws_args
    if cfg.debug:
        print(f"  → {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd)
    sys.exit(result.returncode)
def main() -> None:
    flags, argv = _split_argv(sys.argv[1:])
    if flags["version"]:
        print(f"awst {__version__}")
        sys.exit(0)
    cfg = _config_from_flags(flags)
    if not argv:
        build_parser().print_help()
        sys.exit(0)
    if argv[0] == "aws":
        _passthrough(argv[1:], cfg)
        return
    if argv[0] not in awst_COMMANDS:
        _passthrough(argv, cfg)
        return
    parser = build_parser()
    full_argv: list[str] = []
    if flags["profile"]:
        full_argv += ["--profile", flags["profile"]]
    if flags["region"]:
        full_argv += ["--region", flags["region"]]
    if flags["debug"]:
        full_argv.append("--debug")
    if flags["json_out"]:
        full_argv.append("--json")
    full_argv += argv
    args = parser.parse_args(full_argv)
    try:
        args.func(args, cfg)
    except aws.AWSError as e:
        fmt.error_box("AWS error", str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n  Interrupted")
        sys.exit(130)
if __name__ == "__main__":
    main()

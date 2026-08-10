"""Core AWS CLI subprocess wrapper — every aws call goes through here."""
from __future__ import annotations
import json
import subprocess
import sys
from typing import Any
class AWSError(RuntimeError):
    """AWS CLI returned non-zero."""
    def __init__(self, msg: str, raw: str = ""):
        super().__init__(msg)
        self.raw = raw
FRIENDLY_ERRORS: dict[str, str] = {
    "UnauthorizedOperation": "IAM permission denied — check your permission set or run: awst login",
    "ExpiredToken":          "SSO session expired — run: awst login",
    "NoCredentialProviders": "No credentials found — run: awst login",
    "InvalidClientTokenId":  "Invalid credentials — run: awst login",
    "AccessDenied":          "Access denied — check your IAM permissions",
}
def _build_cmd(args: list[str], profile: str | None, region: str | None) -> list[str]:
    cmd = ["aws"]
    if profile:
        cmd += ["--profile", profile]
    if region:
        cmd += ["--region", region]
    return cmd + args
def run(
    args: list[str],
    profile: str | None = None,
    region: str | None = None,
    debug: bool = False,
    check: bool = True,
) -> str:
    """Run aws CLI, return stdout. Raises AWSError on failure."""
    cmd = _build_cmd(args, profile, region)
    if debug:
        print(f"  → {' '.join(cmd)}", file=sys.stderr)
    r = subprocess.run(cmd, text=True, capture_output=True)
    if check and r.returncode != 0:
        raw = r.stderr.strip() or r.stdout.strip()
        for key, hint in FRIENDLY_ERRORS.items():
            if key in raw:
                raise AWSError(f"{key}: {hint}", raw=raw)
        raise AWSError(raw, raw=raw)
    return r.stdout
def j(
    args: list[str],
    profile: str | None = None,
    region: str | None = None,
    debug: bool = False,
) -> Any:
    """Run aws CLI with --output json, return parsed object."""
    out = run(args + ["--output", "json"], profile=profile, region=region, debug=debug)
    return json.loads(out) if out.strip() else {}
def version() -> str:
    try:
        r = subprocess.run(["aws", "--version"], capture_output=True, text=True)
        return (r.stdout or r.stderr).strip().split()[0]
    except Exception:
        return "unknown"

"""Profile and region resolution — no credentials stored."""
from __future__ import annotations
import os
import subprocess
class Config:
    def __init__(
        self,
        profile: str | None = None,
        region: str | None = None,
        debug: bool = False,
        json_out: bool = False,
    ):
        self.profile = profile or os.environ.get("AWS_PROFILE") or ""
        self._region = region or ""
        self.debug = debug
        self.json_out = json_out
    @property
    def region(self) -> str:
        if self._region:
            return self._region
        args = ["aws", "configure", "get", "region"]
        if self.profile:
            args += ["--profile", self.profile]
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=5)
            v = r.stdout.strip()
            if r.returncode == 0 and v:
                return v
        except Exception:
            pass
        return os.environ.get("AWS_DEFAULT_REGION", "ap-south-1")
    def aws_args(self) -> dict:
        """Common kwargs for aws.run() / aws.j()."""
        return {"profile": self.profile or None, "region": self._region or None, "debug": self.debug}

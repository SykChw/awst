"""AMI discovery."""
from __future__ import annotations
import argparse
import json as _json
import sys
from awst import aws, fmt
from awst.config import Config
def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("images", help="Discover AMIs (self + Amazon)")
    p.add_argument("--gpu", action="store_true", help="Filter GPU/CUDA images")
    p.add_argument("--ubuntu", action="store_true", help="Filter Ubuntu images")
    p.add_argument("--amazon-linux", action="store_true", help="Filter Amazon Linux images")
    p.set_defaults(func=_images)
def _images(args: argparse.Namespace, cfg: Config) -> None:
    try:
        data = aws.j(["ec2", "describe-images", "--owners", "self", "amazon"], **cfg.aws_args())
    except aws.AWSError as e:
        fmt.error_box("describe-images failed", str(e))
        sys.exit(1)
    images = data.get("Images", [])
    def match(name: str) -> bool:
        n = name.lower()
        if args.gpu and not any(k in n for k in ("gpu", "cuda", "deep-learning", "deep_learning")):
            return False
        if args.ubuntu and "ubuntu" not in n:
            return False
        if args.amazon_linux and not any(k in n for k in ("amazon-linux", "amzn")):
            return False
        return True
    images = [i for i in images if match(i.get("Name", ""))]
    images.sort(key=lambda i: i.get("CreationDate", ""), reverse=True)
    if cfg.json_out:
        print(_json.dumps([{"ami": i["ImageId"], "name": i.get("Name"),
                            "created": i.get("CreationDate", "")[:10],
                            "owner": i.get("OwnerId")} for i in images[:30]], indent=2))
        return
    rows = [[i["ImageId"], i.get("Name", "")[:50], i.get("CreationDate", "")[:10]] for i in images[:30]]
    fmt.table(["AMI", "NAME", "CREATED"], rows, title="AMIs")
    print("\n  Filters: --gpu  --ubuntu  --amazon-linux")

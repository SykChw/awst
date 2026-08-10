"""SageMaker domain: awst sm <resource> <action>"""
from __future__ import annotations
import argparse
import json as _json
import sys
from awst import aws, fmt
from awst.config import Config
DEFAULT_MAX = 25
def register(sub: argparse._SubParsersAction) -> None:
    sm = sub.add_parser("sm", help="SageMaker (notebooks, training, processing, Studio)")
    s = sm.add_subparsers(dest="sm_resource", metavar="RESOURCE")
    # awst sm notebook list|start|stop
    nb = s.add_parser("notebook", help="SageMaker notebook instances")
    nbs = nb.add_subparsers(dest="notebook_action", metavar="ACTION")
    nbs.add_parser("list", help="List instances").set_defaults(func=_notebook_list)
    ps = nbs.add_parser("start", help="Start an instance")
    ps.add_argument("name", help="Notebook instance name")
    ps.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    ps.set_defaults(func=_notebook_start)
    pst = nbs.add_parser("stop", help="Stop an instance")
    pst.add_argument("name", help="Notebook instance name")
    pst.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    pst.set_defaults(func=_notebook_stop)
    nb.set_defaults(func=_notebook_list)
    # awst sm training list
    tr = s.add_parser("training", help="Training jobs")
    trs = tr.add_subparsers(dest="training_action", metavar="ACTION")
    tl = trs.add_parser("list", help="List recent jobs")
    tl.add_argument("--max", type=int, default=DEFAULT_MAX, help="Max results")
    tl.set_defaults(func=_training_list)
    tr.set_defaults(func=_training_list)
    # awst sm processing list
    pr = s.add_parser("processing", help="Processing jobs")
    prs = pr.add_subparsers(dest="processing_action", metavar="ACTION")
    pl = prs.add_parser("list", help="List recent jobs")
    pl.add_argument("--max", type=int, default=DEFAULT_MAX, help="Max results")
    pl.set_defaults(func=_processing_list)
    pr.set_defaults(func=_processing_list)
    # awst sm studio domains|apps
    st = s.add_parser("studio", help="SageMaker Studio")
    sts = st.add_subparsers(dest="studio_action", metavar="ACTION")
    sts.add_parser("domains", help="List domains").set_defaults(func=_studio_domains)
    sa = sts.add_parser("apps", help="List apps")
    sa.add_argument("--domain", "-d", default="", help="Domain ID (all if omitted)")
    sa.set_defaults(func=_studio_apps)
    st.set_defaults(func=_studio_domains)
    sm.set_defaults(func=_sm_help)
def _sm_help(args: argparse.Namespace, cfg: Config) -> None:
    print("Usage: awst sm <resource> <action>")
    print("  notebook list | start <name> | stop <name>")
    print("  training list [--max N]")
    print("  processing list [--max N]")
    print("  studio domains | apps [--domain ID]")
def _notebook_list(args: argparse.Namespace, cfg: Config) -> None:
    try:
        data = aws.j(["sagemaker", "list-notebook-instances"], **cfg.aws_args())
    except aws.AWSError as e:
        fmt.error_box("list-notebook-instances failed", str(e))
        sys.exit(1)
    items = data.get("NotebookInstances", [])
    if cfg.json_out:
        print(_json.dumps([_compact_notebook(n) for n in items], indent=2))
        return
    rows = [[
        n["NotebookInstanceName"],
        n.get("InstanceType", "-"),
        n.get("NotebookInstanceStatus", "-"),
        (n.get("CreationTime") or "")[:10],
    ] for n in items]
    fmt.table(["NAME", "TYPE", "STATUS", "CREATED"], rows, title="SageMaker Notebook Instances")
def _notebook_start(args: argparse.Namespace, cfg: Config) -> None:
    name = args.name
    try:
        info = aws.j(["sagemaker", "describe-notebook-instance",
                      "--notebook-instance-name", name], **cfg.aws_args())
    except aws.AWSError as e:
        fmt.error_box(f"Notebook not found: {name}", str(e))
        sys.exit(1)
    status = info.get("NotebookInstanceStatus", "-")
    fmt.kv({"Name": name, "Type": info.get("InstanceType", "-"), "Status": status})
    if status == "InService":
        fmt.ok(f"{name} is already InService")
        if info.get("Url"):
            print(f"  URL: https://{info['Url']}")
        return
    if not args.yes and not fmt.confirm(f"Start notebook {name}?", default=True):
        print("  Aborted.")
        return
    try:
        aws.run(["sagemaker", "start-notebook-instance",
                 "--notebook-instance-name", name], **cfg.aws_args())
        fmt.ok(f"Starting {name} — check: awst sm notebook list")
    except aws.AWSError as e:
        fmt.error_box(f"Start failed: {name}", str(e))
        sys.exit(1)
def _notebook_stop(args: argparse.Namespace, cfg: Config) -> None:
    name = args.name
    try:
        info = aws.j(["sagemaker", "describe-notebook-instance",
                      "--notebook-instance-name", name], **cfg.aws_args())
    except aws.AWSError as e:
        fmt.error_box(f"Notebook not found: {name}", str(e))
        sys.exit(1)
    status = info.get("NotebookInstanceStatus", "-")
    fmt.kv({"Name": name, "Type": info.get("InstanceType", "-"), "Status": status})
    if status == "Stopped":
        fmt.ok(f"{name} is already Stopped")
        return
    if not args.yes and not fmt.confirm(f"Stop notebook {name}?", default=False):
        print("  Aborted.")
        return
    try:
        aws.run(["sagemaker", "stop-notebook-instance",
                 "--notebook-instance-name", name], **cfg.aws_args())
        fmt.ok(f"Stopping {name}")
    except aws.AWSError as e:
        fmt.error_box(f"Stop failed: {name}", str(e))
        sys.exit(1)
def _training_list(args: argparse.Namespace, cfg: Config) -> None:
    max_r = getattr(args, "max", DEFAULT_MAX)
    try:
        data = aws.j(["sagemaker", "list-training-jobs",
                      "--max-results", str(max_r),
                      "--sort-by", "CreationTime",
                      "--sort-order", "Descending"], **cfg.aws_args())
    except aws.AWSError as e:
        fmt.error_box("list-training-jobs failed", str(e))
        sys.exit(1)
    items = data.get("TrainingJobSummaries", [])
    if cfg.json_out:
        print(_json.dumps([_compact_training(j) for j in items], indent=2))
        return
    rows = [[
        j["TrainingJobName"][:40],
        j.get("TrainingJobStatus", "-"),
        j.get("SecondaryStatus", "-")[:20],
        (j.get("CreationTime") or "")[:10],
        (j.get("TrainingEndTime") or "-")[:10],
    ] for j in items]
    fmt.table(["NAME", "STATUS", "SECONDARY", "CREATED", "ENDED"], rows,
              title=f"Training Jobs (last {len(items)})")
def _processing_list(args: argparse.Namespace, cfg: Config) -> None:
    max_r = getattr(args, "max", DEFAULT_MAX)
    try:
        data = aws.j(["sagemaker", "list-processing-jobs",
                      "--max-results", str(max_r),
                      "--sort-by", "CreationTime",
                      "--sort-order", "Descending"], **cfg.aws_args())
    except aws.AWSError as e:
        fmt.error_box("list-processing-jobs failed", str(e))
        sys.exit(1)
    items = data.get("ProcessingJobSummaries", [])
    if cfg.json_out:
        print(_json.dumps([_compact_processing(j) for j in items], indent=2))
        return
    rows = [[
        j["ProcessingJobName"][:40],
        j.get("ProcessingJobStatus", "-"),
        (j.get("CreationTime") or "")[:10],
        (j.get("ProcessingEndTime") or "-")[:10],
    ] for j in items]
    fmt.table(["NAME", "STATUS", "CREATED", "ENDED"], rows,
              title=f"Processing Jobs (last {len(items)})")
def _studio_domains(args: argparse.Namespace, cfg: Config) -> None:
    try:
        data = aws.j(["sagemaker", "list-domains"], **cfg.aws_args())
    except aws.AWSError as e:
        fmt.error_box("list-domains failed", str(e))
        sys.exit(1)
    items = data.get("Domains", [])
    if cfg.json_out:
        print(_json.dumps([_compact_domain(d) for d in items], indent=2))
        return
    rows = [[
        d.get("DomainId", "-"),
        d.get("DomainName", "-"),
        d.get("Status", "-"),
        d.get("Url", "-")[:50],
    ] for d in items]
    fmt.table(["DOMAIN_ID", "NAME", "STATUS", "URL"], rows, title="SageMaker Studio Domains")
def _studio_apps(args: argparse.Namespace, cfg: Config) -> None:
    domain_ids: list[str] = []
    if args.domain:
        domain_ids = [args.domain]
    else:
        try:
            domains = aws.j(["sagemaker", "list-domains"], **cfg.aws_args()).get("Domains", [])
            domain_ids = [d["DomainId"] for d in domains]
        except aws.AWSError as e:
            fmt.error_box("list-domains failed", str(e))
            sys.exit(1)
    all_apps: list[dict] = []
    for did in domain_ids:
        try:
            data = aws.j(["sagemaker", "list-apps", "--domain-id-equals", did], **cfg.aws_args())
            for app in data.get("Apps", []):
                app["_domain_id"] = did
                all_apps.append(app)
        except aws.AWSError:
            continue
    if cfg.json_out:
        print(_json.dumps([_compact_app(a) for a in all_apps], indent=2))
        return
    if not all_apps:
        print("  (no Studio apps found)")
        return
    rows = [[
        a.get("_domain_id", "-"),
        a.get("AppName", "-"),
        a.get("AppType", "-"),
        a.get("Status", "-"),
        a.get("UserProfileName", "-"),
    ] for a in all_apps]
    fmt.table(["DOMAIN", "APP", "TYPE", "STATUS", "USER"], rows, title="SageMaker Studio Apps")
def _compact_notebook(n: dict) -> dict:
    return {
        "name": n.get("NotebookInstanceName"),
        "type": n.get("InstanceType"),
        "status": n.get("NotebookInstanceStatus"),
        "url": n.get("Url"),
        "created": str(n.get("CreationTime", "")),
    }
def _compact_training(j: dict) -> dict:
    return {
        "name": j.get("TrainingJobName"),
        "status": j.get("TrainingJobStatus"),
        "secondary": j.get("SecondaryStatus"),
        "created": str(j.get("CreationTime", "")),
        "ended": str(j.get("TrainingEndTime", "")),
        "arn": j.get("TrainingJobArn"),
    }
def _compact_processing(j: dict) -> dict:
    return {
        "name": j.get("ProcessingJobName"),
        "status": j.get("ProcessingJobStatus"),
        "created": str(j.get("CreationTime", "")),
        "ended": str(j.get("ProcessingEndTime", "")),
        "arn": j.get("ProcessingJobArn"),
    }
def _compact_domain(d: dict) -> dict:
    return {
        "id": d.get("DomainId"),
        "name": d.get("DomainName"),
        "status": d.get("Status"),
        "url": d.get("Url"),
        "created": str(d.get("CreationTime", "")),
    }
def _compact_app(a: dict) -> dict:
    return {
        "domain_id": a.get("_domain_id"),
        "name": a.get("AppName"),
        "type": a.get("AppType"),
        "status": a.get("Status"),
        "user": a.get("UserProfileName"),
    }

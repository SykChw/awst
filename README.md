# awst — AWS CLI wrapper
`awst` is a composable grammar on top of the AWS CLI. It does two things:
1. **Compact commands** for discovery and common workflows (tables or `--json`)
2. **Passthrough** for everything else — identical to `aws`
Think of it like vim motions: a small set of **domains → resources → actions** you combine with **flags** and **pipes** to build complex workflows in one shot.
---
## Install
```bash
cd plugins/ds-custom/skills/aws-tools   # or ~/.assistant/repos/ds-skills/...
pip install -e ".[all]"
awst hello
```
```zsh
# ~/.zshrc — avoid stale shell functions shadowing the binary
unfunction awst 2>/dev/null
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
```
---
## Grammar
```
awst [GLOBAL_FLAGS] <DOMAIN> [RESOURCE] [ACTION] [TARGET] [FLAGS...]
```
| Layer | Role | Examples |
|-------|------|----------|
| **Global flags** | Profile, region, output mode | `--profile`, `--region`, `--json`, `--debug` |
| **Domain** | Top-level service area | `ec2`, `sm`, `network`, `notebook`, `launch` |
| **Resource** | Thing within the domain | `notebook` (EC2: `tunnel`; SM: `list`/`start`/`stop`) |
| **Action** | Verb on that resource | `list`, `start`, `stop`, `running`, `inspect` |
| **Target** | Instance ID, notebook name, path | `i-0abc123`, `my-nb` |
| **Flags** | Modifiers | `--yes`, `--dry-run`, `--max 10`, `--instance` |
**Defaults:** If you omit the action, awst picks the sensible default (`ec2` → `list`, `sm notebook` → `list`, `sm studio` → `domains`).
**Global flags work anywhere in the command:**
```bash
awst ec2 running --json
awst --json ec2 running          # same
```
---
## Two modes
### Mode 1 — awst commands (compact output)
Registered domains get parsed, call `aws` under the hood, return **condensed** tables or `--json`.
### Mode 2 — passthrough (raw AWS CLI)
| Invocation | Behaviour |
|------------|-----------|
| `awst s3 ls` | Unknown domain → `aws s3 ls` |
| `awst aws <args>` | Explicit → `aws <args>` |
| `awst iam get-user` | Passthrough |
Profile and region from awst globals are injected. Output is **exactly** what AWS CLI prints. Use `--output json` (not `--json`) for passthrough.
---
## Command tree
```
awst
├── hello | config | account | login     # meta / auth
├── doctor                               # environment check
│
├── ec2                                  # EC2 instances
│   ├── list | running | stopped         # discovery (default: list)
│   ├── inspect <id>                     # detail
│   └── configs                          # infer launch templates from existing
│
├── network                              # VPC / subnet / SG
│   ├── (default: summary)
│   ├── vpcs | subnets | sgs
│
├── gpu | types [prefix] | images        # compute / AMI discovery
│
├── launch                               # provision EC2
│   ├── cpu [--dry-run] [--yes]
│   └── gpu  [--dry-run] [--yes]
│
├── ssh [<id>]                           # shell into EC2
├── sync [local] [remote]                # rsync → EC2
├── stop | terminate [<id>]              # EC2 lifecycle
│
├── notebook                             # Jupyter on EC2 (NOT SageMaker)
│   └── tunnel [--instance] [--start-jupyter]
│
├── sm                                   # SageMaker
│   ├── notebook list | start <name> | stop <name>
│   ├── training list [--max N]
│   ├── processing list [--max N]
│   └── studio domains | apps [--domain ID]
│
└── aws <args>                           # explicit passthrough
```
### EC2 notebook vs SageMaker notebook
These are **different products** with **different command paths**:
| What you want | Command | How you access it |
|---------------|---------|-------------------|
| Jupyter on **your EC2** | `awst notebook tunnel` | SSH tunnel → `http://localhost:8888` |
| **SageMaker** notebook instance | `awst sm notebook list` | Browser URL from list output |
| Start a stopped SageMaker NB | `awst sm notebook start <name>` | Then open its URL |
`notebook` means two different things depending on domain:
- `awst notebook tunnel` → EC2 (you SSH in)
- `awst sm notebook …` → SageMaker (managed, browser URL)
---
## Domains in detail
### Meta
```bash
awst hello                    # sanity check
awst config                   # profile, region, account, SSO
awst account                  # sts get-caller-identity (compact)
awst login                    # aws sso login
awst doctor                   # CLI, creds, IAM probes
```
### `ec2` — instances
```bash
awst ec2 running              # running + uptime
awst ec2 stopped
awst ec2 list                 # all
awst ec2 inspect i-0abc123    # VPC, subnet, SGs, IAM, IPs
awst ec2 configs              # group by launch config (subnet/SG/AMI/key)
```
Shorthand: none — always use `awst ec2 <action>`.
### `network` — infrastructure
```bash
awst network                  # counts
awst network vpcs
awst network subnets
awst network sgs
```
### `notebook` — EC2 Jupyter
```bash
awst notebook tunnel                           # pick instance, open tunnel
awst notebook tunnel --instance i-0abc123
awst notebook tunnel -i i-0abc123 --start-jupyter
awst notebook tunnel --port 9999 --no-browser
```
Requires: instance **running**, SSH reachable (VPN if private IP), Jupyter installed for `--start-jupyter`.
### Discovery
```bash
awst gpu                      # GPU types + AZ availability
awst types g4                 # instance types (optional prefix)
awst images --gpu             # AMIs
```
### `launch` — provision EC2
```bash
awst launch cpu --dry-run     # validate without creating
awst launch gpu --type g4dn.xlarge --yes
```
Auto-discovers subnet, SGs, key, IAM from `awst ec2 configs`.
### EC2 access
```bash
awst ssh                      # interactive picker
awst ssh i-0abc123 --cmd "nvidia-smi"
awst ssh i-0abc123 --print-only    # show ssh command only
awst sync . ~/code --instance i-0abc123
awst sync . ~/code --watch    # re-sync on change
awst stop i-0abc123 --yes
awst terminate i-0abc123
```
### `sm` — SageMaker
```bash
awst sm notebook list
awst sm notebook list --json
awst sm notebook start my-nb --yes
awst sm notebook stop my-nb --yes
awst sm training list --max 10
awst sm processing list --json
awst sm studio domains
awst sm studio apps
awst sm studio apps --domain d-fe0a0bhfobif
```
---
## Composing complex workflows
The grammar is designed to chain with shell tools. Patterns:
### Discover → filter → act
```bash
# Find running GPU-capable instances, inspect the first
awst ec2 running --json | jq -r '.[] | select(.type | startswith("g")) | .id' | head -1 | \
  xargs -I{} awst ec2 inspect {}
# List InService SageMaker notebooks as names only
awst sm notebook list --json | jq -r '.[] | select(.status=="InService") | .name'
# SSH into first running instance matching a name
ID=$(awst ec2 running --json | jq -r '.[] | select(.name | test("discovery")) | .id' | head -1)
awst ssh "$ID" --print-only
```
### Discover → validate → launch
```bash
awst doctor
awst ec2 configs                    # see what launch will use
awst launch cpu --dry-run           # validate permissions
awst launch cpu --yes               # if dry-run passes
```
### SageMaker session
```bash
awst sm notebook list --json | jq '.[] | {name, status, url}'
awst sm notebook start my-nb --yes
# open URL from list output in browser
```
### EC2 dev session
```bash
awst ec2 running
awst ssh i-0abc123                  # verify access
awst sync ./src ~/project -i i-0abc123
awst notebook tunnel -i i-0abc123 --start-jupyter
```
### When awst doesn't have a command — passthrough
```bash
awst s3 ls s3://my-bucket/
awst aws sagemaker describe-training-job --training-job-name my-job
awst lambda list-functions --output table
```
Use `awst aws` when you want to be explicit that nothing in awst should intercept the command.
---
## Global flags reference
| Flag | Applies to | Effect |
|------|------------|--------|
| `--profile NAME` | all | AWS profile (or `AWS_PROFILE`) |
| `--region NAME` | all | Override region |
| `--json` | awst commands only | Compact structured output |
| `--debug` | all | Print underlying `aws` invocations on stderr |
| `--version` | — | Print awst version |
---
## Architecture
```
src/awst/
├── cli.py           # dispatch: grammar vs passthrough
├── aws.py           # subprocess → aws CLI
├── config.py        # profile / region
├── fmt.py           # tables, confirm, pick
└── commands/        # one file per domain
    ├── ec2.py       # ec2 <action>
    ├── sagemaker.py # sm <resource> <action>
    ├── notebook.py  # notebook tunnel (EC2)
    └── ...
```
**Add a command:** create `commands/foo.py` with `register(sub)`, import in `cli.py`, add domain to `awst_COMMANDS`.
---
## Dependencies
| Tool | Required | For |
|------|----------|-----|
| `aws` CLI v2 | yes | everything |
| Python 3.10+ | yes | awst itself |
| `rich` | optional | prettier tables |
| `rsync` | for `sync` | file transfer |
| `watchdog` | for `sync --watch` | auto re-sync |
| `ssh` | for `ssh`, `notebook tunnel` | remote access |
---
## Troubleshooting
| Problem | Fix |
|---------|-----|
| `command not found: awst_DISPATCH` | Stale zsh function — `unfunction awst; source ~/.zshrc` |
| `awst` not found | `pip install -e ".[all]"` |
| `UnauthorizedOperation` on launch | IAM — use `awst launch cpu --dry-run` to test |
| SSH / notebook tunnel fails | `awst ssh <id> --print-only` — check VPN, key, security group |
| `--json` on passthrough | Use `--output json` instead (that's aws CLI syntax) |

---
name: aws-tools
description: >-
  Use awst for compact AWS output or passthrough to aws CLI. Grammar is
  domain/resource/action: ec2, sm notebook, notebook tunnel, network, launch.
  Trigger on awst, ec2 running, sm notebook, notebook tunnel, doctor, passthrough.
---

# aws-tools
## Grammar
```
awst [--profile P] [--region R] [--json] <domain> [resource] [action] [target] [flags]
```
## Command tree
```
ec2       list|running|stopped|inspect <id>|configs
network   (summary)|vpcs|subnets|sgs
gpu | types | images
launch    cpu|gpu [--dry-run]
ssh | sync | stop | terminate
notebook  tunnel [--instance ID]        # EC2 Jupyter via SSH
sm        notebook list|start|stop <name>
          training list [--max N]
          processing list
          studio domains|apps
```
## Notebooks (two domains, same word)
| Goal | Command |
|------|---------|
| Jupyter on EC2 | `awst notebook tunnel -i <ec2-id>` |
| SageMaker notebook | `awst sm notebook list` → open URL |
| Start SageMaker NB | `awst sm notebook start <name> --yes` |
## Agent patterns
```bash
awst ec2 running --json
awst sm notebook list --json
awst notebook tunnel -i i-xxx --no-browser   # EC2 only
# passthrough when no awst command
awst s3 ls
awst aws sts get-caller-identity
```
## Install
```bash
pip install -e ".[all]"   # from plugins/ds-custom/skills/aws-tools
```

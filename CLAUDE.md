# Context for Claude Code

This is Raghav's PBL-III DevOps assignment (3 tasks × 5 marks). The deadline is tight, so prefer
small, working fixes over redesigns. Keep everything simple and easy to explain.

- Machine: **Windows**, Docker Desktop with built-in Kubernetes (context `docker-desktop`), PowerShell.
- Each task deploys its own app version from its own self-contained folder (app/, tests/,
  requirements*.txt, Dockerfile = the docker build context):
  `app-task1/` = v1 basic (image `carewell-v1`), `app-task2/` = v2 dashboard with blue/green bar
  (`carewell-v2`), `app-task3/` = v3 full secure system (`carewell-v3`). There is no root app.
  Every version must keep `/health`, `/version` (JSON with "version") and the security headers,
  because `scripts/smoke_test.sh` and the k8s probes use them. Tests: `cd app-taskN; python -m pytest tests`.
- Jenkins runs in Docker via `docker-compose.yml` (image built from `jenkins/`), container name
  `pbl3-jenkins`, project name `pbl3-devops` (volume `pbl3-devops_jenkins_home`). It uses the host
  Docker through the socket, and kubeconfig is mounted from `%USERPROFILE%\.kube` (rewritten to
  `kubernetes.docker.internal` by `jenkins/entrypoint.sh`).
- The 3 jobs are auto-created by `jenkins/init.groovy.d/create-jobs.groovy` from `GIT_REPO_URL` in `.env`.
- Images are built locally and used by the cluster directly (`imagePullPolicy: IfNotPresent`), with no registry.
- Pipelines run inside the Linux Jenkins container, so Jenkinsfiles use `sh`, not `bat`.
- Read `README.md` for the full runbook and demo steps.

Rules:
- Never add Claude as author or co-author in commits (no `Co-Authored-By` or any Claude attribution).
- Don't commit `.env` or any real secrets. Gitleaks will fail Task 3 if you do.
- After changing anything the pipelines use, commit and push, because Jenkins pulls from GitHub.
- The SentinelOps project (`Desktop/sentinelops`) runs on the same machine: never modify it. It uses
  host ports 5000/8000, compose project `sentinelops`, images `sentinelops-*`, no Kubernetes.
  Don't reuse those; if something would clash, change this project's side.

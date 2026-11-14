# Context for Claude Code

This is Raghav's PBL-III DevOps assignment (3 tasks × 5 marks). The deadline is tight, so prefer
small, working fixes over redesigns. Keep everything simple and easy to explain.

- Machine: **Windows**, Docker Desktop with built-in Kubernetes (context `docker-desktop`), PowerShell.
- Jenkins runs in Docker via `docker-compose.yml` (image built from `jenkins/`). It uses the host
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

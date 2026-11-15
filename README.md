# PBL-III DevOps: CareWell Hospital

A small Flask hospital app (CareWell Hospital) that grows with each task, and three Jenkins
pipelines, one per task. Each task deploys its **own app version**, so the demo tells a story:
basic site → improved dashboard → full secure system.

| Task | App folder (version) | Image | Jenkins job | Jenkinsfile | App URL |
|---|---|---|---|---|---|
| 1. CI/CD to Kubernetes | `app-task1/` (v1 basic) | `carewell-v1` | `task1-cicd-k8s` | `Jenkinsfile.task1` | http://localhost:30080 |
| 2. Blue-green deployment | `app-task2/` (v2 improved) | `carewell-v2` | `task2-blue-green` | `Jenkinsfile.task2` | live http://localhost:30081, preview http://localhost:30082 |
| 3. DevSecOps (healthcare) | `app-task3/` (v3 final) | `carewell-v3` | `task3-devsecops` | `Jenkinsfile.task3` | http://localhost:30083 |

| Version | What it has |
|---|---|
| v1 BASIC | One page `/`: CareWell Hospital header and a simple patient table (id, name, age, ward). |
| v2 IMPROVED | Dashboard, Patients list with search, Doctors, Appointments, sidebar navigation, and a coloured environment bar from `APP_COLOR` (blue/green). |
| v3 FINAL | Everything in v2 plus patient detail page with vitals and visit history, add-patient form with server-side validation, phone masking (PHI), `AUDIT` access logs and a JSON API. |

Every version has `/health`, `/version` (JSON with `"version"`) and the same security headers,
so the pipelines' smoke test works for all three. Each folder is self-contained
(`app/`, `tests/`, `requirements.txt`, `requirements-dev.txt`, `Dockerfile`) and is the Docker
build context for its pipeline. Run the tests locally with `cd app-task1; python -m pytest tests`
(same for `app-task2` / `app-task3`).

**Stack:** Docker Desktop (with built-in Kubernetes), Jenkins running in Docker, a GitHub repo.

---

## 0. Prerequisites (Windows)

1. Docker Desktop → **Settings → Kubernetes → Enable Kubernetes** (choose **kubeadm**) → Apply. Wait until it's green.
2. Check it in PowerShell:
   ```powershell
   kubectl config use-context docker-desktop
   kubectl get nodes          # 1 node, STATUS Ready
   ```

## 1. Push this repo to GitHub

```powershell
cd pbl3-devops
git init -b main
git add .
git commit -m "PBL-III DevOps: app, Jenkins pipelines, k8s manifests"
git remote add origin https://github.com/<YOUR_USERNAME>/pbl3-devops.git
git push -u origin main
```
The repo must be **public**, so Jenkins can clone it without credentials.

## 2. Start Jenkins (the 3 jobs are created automatically)

```powershell
copy .env.example .env
notepad .env                  # set GIT_REPO_URL to your GitHub repo URL
docker compose up -d --build  # first build takes about 3-5 min
docker logs -f pbl3-jenkins   # wait for "[pbl] job ready" x3 and "Jenkins is fully up and running"
```
Then open **http://localhost:8090**. You should see the 3 jobs.

Check that Jenkins can reach Kubernetes:
```powershell
docker exec pbl3-jenkins kubectl get nodes
```

> The Jenkins container is called `pbl3-jenkins` (not `jenkins`) so it can't clash with other
> projects on this machine. Build history lives in the `pbl3-devops_jenkins_home` volume and is kept.
> If an old container named `jenkins` from an earlier setup is still around, remove it with
> `docker rm -f jenkins` (the volume is not deleted).

---

## Task 1: CI/CD Pipeline → Kubernetes

1. Open `task1-cicd-k8s` → **Build Now**.
2. Stages: Checkout → Unit Tests → Build Docker Image → Deploy to Kubernetes → Smoke Test.
3. Open http://localhost:30080 (v1: header + patient table) and http://localhost:30080/version to see the build number.
4. **CI demo:** change something (for example a patient name in `app-task1/app/main.py`), then `git commit` and `git push`. Within about 2 minutes Jenkins builds by itself (Poll SCM), and `/version` shows the new build number.

```powershell
kubectl -n pbl-task1 get deploy,pods,svc
```

## Task 2: Blue-Green Deployment

1. Open `task2-blue-green` → **Build with Parameters** → ACTION=`deploy` → Build. This first run deploys **blue** and makes it live.
2. In a second PowerShell window, start the traffic watcher:
   ```powershell
   while ($true) { try { (Invoke-WebRequest http://localhost:30081/version -UseBasicParsing).Content } catch { "DOWN" }; Start-Sleep -Milliseconds 500 }
   ```
3. Open http://localhost:30081: the v2 dashboard, with a blue top bar. Build again with ACTION=`deploy` (optionally tick MANUAL_APPROVAL). The new version goes to **green**, gets tested on preview (:30082), and then traffic switches. The watcher flips from `"color":"blue"` to `"color":"green"` with **no DOWN lines**, and the dashboard's top bar turns green (it refreshes every 5 s).
4. Build with ACTION=`rollback`. Traffic goes back to blue instantly.

```powershell
kubectl -n pbl-task2 get deploy -L color
kubectl -n pbl-task2 get svc patient-api-live -o jsonpath="{.spec.selector.color}"
```

## Task 3: DevSecOps for Healthcare

1. Open `task3-devsecops` → **Build with Parameters** → Build. The first run pulls the ZAP image, which is slow. Untick RUN_DAST if you're short on time.
2. Open http://localhost:30083: the full v3 system (click a patient for the detail page, try **Add patient**).
3. Ten stages: Gitleaks → Bandit → Trivy (dependencies) → Hadolint → Unit tests → Build → Trivy (image) → Trivy (k8s YAML) → Secure deploy → OWASP ZAP.
4. Reports are on the build page under **Build Artifacts** (`reports/`).
5. **"Security gate blocks a bad build" demo:**
   - In `app-task3/requirements.txt`, change `flask==3.1.2` to `flask==2.2.0` (has a known HIGH CVE), then commit, push and build. The build **FAILS** at stage 3 and nothing gets deployed.
   - Change it back, then commit, push and build. The build **PASSES**.
6. Show the hardening:
   ```powershell
   kubectl -n pbl-task3 get pods,svc,networkpolicy,secret
   kubectl -n pbl-task3 exec deploy/patient-api -- id          # uid=10001 (not root)
   kubectl -n pbl-task3 exec deploy/patient-api -- touch /x    # fails: read-only filesystem
   kubectl -n pbl-task3 logs deploy/patient-api | findstr AUDIT # audit trail of patient-record access
   ```
   Also try a root pod in the restricted namespace. Kubernetes rejects it:
   ```powershell
   kubectl -n pbl-task3 run hacker --image=nginx
   ```

### Healthcare security controls (for the report)

| Control | Where |
|---|---|
| No secrets in code | Gitleaks gate + K8s Secret generated at deploy time |
| Secure code | Bandit SAST gate |
| No vulnerable libraries or images | Trivy SCA + image scan gates |
| Hardened container | Non-root user (uid 10001), read-only root FS, all Linux capabilities dropped, no privilege escalation, seccomp |
| Cluster policy | Pod Security Admission `restricted` on the namespace |
| Least privilege | Dedicated ServiceAccount, no API token mounted |
| Network isolation | Default-deny NetworkPolicy, only port 5000 allowed in |
| PHI protection | `Cache-Control: no-store` and security headers (CSP, X-Frame-Options, nosniff) |
| Accountability (HIPAA-style audit) | Every patient-record access is logged with an `AUDIT` line |
| Runtime testing | OWASP ZAP DAST against the live app |

> Note: Docker Desktop's default networking doesn't *enforce* NetworkPolicies. The policy is still applied and validated, and it is enforced on clusters with a policy-capable CNI (Calico, Cilium) such as a production EKS or AKS cluster.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `docker exec jenkins kubectl get nodes` fails | Docker Desktop Kubernetes must be the **kubeadm** type and running. Then run `docker compose restart jenkins` (service name; the container is `pbl3-jenkins`). |
| Pods stuck in `ErrImagePull` / `ImagePullBackOff` | The cluster can't see locally built images. Use the kubeadm cluster type, not kind. |
| No jobs in Jenkins | `GIT_REPO_URL` isn't set in `.env`. Fix it, then run `docker compose up -d --force-recreate`. |
| Jenkins can't find the Jenkinsfile | The branch must be `main` and the repo must be public. |
| Smoke test can't connect | Check `curl http://localhost:30080/health` from PowerShell. Make sure no other app uses ports 30080-30083. |
| `container name "/pbl3-jenkins" is already in use` | `docker rm -f pbl3-jenkins`, then `docker compose up -d` (the volume is kept). |
| Reset a task | `kubectl delete ns pbl-task1` (or task2 / task3) |

---

## Running next to SentinelOps (same machine)

This project and SentinelOps (`Desktop/sentinelops`) can run at the same time. Nothing is shared:

| | PBL-III (this repo) | SentinelOps (local `docker-compose.yml`) |
|---|---|---|
| Compose project | `pbl3-devops` | `sentinelops` |
| Containers | `pbl3-jenkins` (+ Kubernetes pods in `pbl-task1/2/3`) | `sentinelops-mysql-1`, `sentinelops-dashboard-1`, `sentinelops-demo-app-1`, `sentinelops-autoheal-1` |
| Host ports | 8090 (Jenkins, 127.0.0.1 only), 30080-30083 (NodePorts) | 5000 (dashboard), 8000 (demo-app) |
| Images | `pbl3-devops-jenkins`, `carewell-v1/v2/v3` | `sentinelops-dashboard`, `sentinelops-demo-app`, `mysql:8`, `willfarrell/autoheal:1.2.0` |
| Volumes | `pbl3-devops_jenkins_home` | `sentinelops_mysql-data` |
| Kubernetes | namespaces `pbl-task1`, `pbl-task2`, `pbl-task3` | not used |

SentinelOps' autoheal only restarts containers labelled `autoheal=true`; nothing in this project has that label.
SentinelOps' own Jenkins runs on its EC2 server (port 8080 there), not on this machine.

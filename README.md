# PBL-III DevOps: Patient Records API

One small healthcare app (a Flask "Patient Records API") and three Jenkins pipelines, one per task:

| Task | Jenkins job | Jenkinsfile | App URL |
|---|---|---|---|
| 1. CI/CD to Kubernetes | `task1-cicd-k8s` | `Jenkinsfile.task1` | http://localhost:30080 |
| 2. Blue-green deployment | `task2-blue-green` | `Jenkinsfile.task2` | live http://localhost:30081, preview http://localhost:30082 |
| 3. DevSecOps (healthcare) | `task3-devsecops` | `Jenkinsfile.task3` | http://localhost:30083 |

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
docker logs -f jenkins        # wait for "[pbl] job ready" x3 and "Jenkins is fully up and running"
```
Then open **http://localhost:8080**. You should see the 3 jobs.

Check that Jenkins can reach Kubernetes:
```powershell
docker exec jenkins kubectl get nodes
```

---

## Task 1: CI/CD Pipeline → Kubernetes

1. Open `task1-cicd-k8s` → **Build Now**.
2. Stages: Checkout → Unit Tests → Build Docker Image → Deploy to Kubernetes → Smoke Test.
3. Open http://localhost:30080/version to see the build number.
4. **CI demo:** change something (for example a patient name in `app/main.py`), then `git commit` and `git push`. Within about 2 minutes Jenkins builds by itself (Poll SCM), and `/version` shows the new build number.

```powershell
kubectl -n pbl-task1 get deploy,pods,svc
```

## Task 2: Blue-Green Deployment

1. Open `task2-blue-green` → **Build with Parameters** → ACTION=`deploy` → Build. This first run deploys **blue** and makes it live.
2. In a second PowerShell window, start the traffic watcher:
   ```powershell
   while ($true) { try { (Invoke-WebRequest http://localhost:30081/version -UseBasicParsing).Content } catch { "DOWN" }; Start-Sleep -Milliseconds 500 }
   ```
3. Build again with ACTION=`deploy` (optionally tick MANUAL_APPROVAL). The new version goes to **green**, gets tested on preview (:30082), and then traffic switches. The watcher flips from `"color":"blue"` to `"color":"green"` with **no DOWN lines**.
4. Build with ACTION=`rollback`. Traffic goes back to blue instantly.

```powershell
kubectl -n pbl-task2 get deploy -L color
kubectl -n pbl-task2 get svc patient-api-live -o jsonpath="{.spec.selector.color}"
```

## Task 3: DevSecOps for Healthcare

1. Open `task3-devsecops` → **Build with Parameters** → Build. The first run pulls the ZAP image, which is slow. Untick RUN_DAST if you're short on time.
2. Ten stages: Gitleaks → Bandit → Trivy (dependencies) → Hadolint → Unit tests → Build → Trivy (image) → Trivy (k8s YAML) → Secure deploy → OWASP ZAP.
3. Reports are on the build page under **Build Artifacts** (`reports/`).
4. **"Security gate blocks a bad build" demo:**
   - In `requirements.txt`, change `flask==3.1.2` to `flask==2.2.0` (has a known HIGH CVE), then commit, push and build. The build **FAILS** at stage 3 and nothing gets deployed.
   - Change it back, then commit, push and build. The build **PASSES**.
5. Show the hardening:
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
| `docker exec jenkins kubectl get nodes` fails | Docker Desktop Kubernetes must be the **kubeadm** type and running. Then run `docker compose restart jenkins`. |
| Pods stuck in `ErrImagePull` / `ImagePullBackOff` | The cluster can't see locally built images. Use the kubeadm cluster type, not kind. |
| No jobs in Jenkins | `GIT_REPO_URL` isn't set in `.env`. Fix it, then run `docker compose up -d --force-recreate`. |
| Jenkins can't find the Jenkinsfile | The branch must be `main` and the repo must be public. |
| Smoke test can't connect | Check `curl http://localhost:30080/health` from PowerShell. Make sure no other app uses ports 30080-30083. |
| Reset a task | `kubectl delete ns pbl-task1` (or task2 / task3) |

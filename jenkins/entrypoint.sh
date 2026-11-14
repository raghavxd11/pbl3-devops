#!/bin/bash
# Make the host's kubeconfig usable from inside this container.
# Docker Desktop's API server is published on the host, so rewrite localhost
# addresses to kubernetes.docker.internal (mapped to the host in docker-compose).
mkdir -p /root/.kube
if [ -f /root/.kube-host/config ]; then
  KUBECONFIG=/root/.kube-host/config kubectl config view --minify --flatten --context docker-desktop \
    | sed -e 's#https://127.0.0.1:#https://kubernetes.docker.internal:#g' -e 's#https://localhost:#https://kubernetes.docker.internal:#g' \
    > /root/.kube/config
  kubectl config use-context docker-desktop >/dev/null 2>&1 || true
  echo "[pbl] kubeconfig ready (context: $(kubectl config current-context 2>/dev/null))"
else
  echo "[pbl] WARNING: no kubeconfig mounted at /root/.kube-host/config"
fi
exec /usr/local/bin/jenkins.sh "$@"

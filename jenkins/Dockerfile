# Jenkins with everything the 3 pipelines need already installed:
# docker CLI, kubectl, trivy, gitleaks, hadolint, bandit
FROM jenkins/jenkins:lts-jdk17

USER root

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates git python3 python3-pip \
 && rm -rf /var/lib/apt/lists/*

# Docker CLI (talks to Docker Desktop through the mounted socket)
RUN ARCH="$(uname -m)" \
 && curl -fsSL "https://download.docker.com/linux/static/stable/${ARCH}/docker-27.3.1.tgz" | tar xz -C /tmp \
 && mv /tmp/docker/docker /usr/local/bin/docker && rm -rf /tmp/docker

# kubectl
RUN DARCH="$(dpkg --print-architecture)" \
 && curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/v1.31.2/bin/linux/${DARCH}/kubectl" \
 && chmod +x /usr/local/bin/kubectl

# Trivy (dependency, image and Kubernetes-manifest scanning)
COPY --from=aquasec/trivy:0.57.1 /usr/local/bin/trivy /usr/local/bin/trivy

# Gitleaks (secret scanning)
RUN DARCH="$(dpkg --print-architecture)"; [ "$DARCH" = "amd64" ] && GARCH=x64 || GARCH=arm64; \
    curl -fsSL "https://github.com/gitleaks/gitleaks/releases/download/v8.21.2/gitleaks_8.21.2_linux_${GARCH}.tar.gz" | tar xz -C /usr/local/bin gitleaks

# Hadolint (Dockerfile linting)
RUN ARCH="$(uname -m)"; [ "$ARCH" = "aarch64" ] && HARCH=arm64 || HARCH=x86_64; \
    curl -fsSLo /usr/local/bin/hadolint "https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-${HARCH}" \
 && chmod +x /usr/local/bin/hadolint

# Bandit (Python SAST)
RUN pip3 install --no-cache-dir --break-system-packages bandit==1.7.10

# Jenkins plugins
RUN jenkins-plugin-cli --plugins workflow-aggregator git pipeline-stage-view timestamper

# Creates the 3 pipeline jobs automatically on startup
COPY init.groovy.d/ /usr/share/jenkins/ref/init.groovy.d/

# Copies your kubeconfig in and points it at Docker Desktop's Kubernetes
COPY entrypoint.sh /usr/local/bin/pbl-entrypoint.sh
RUN chmod +x /usr/local/bin/pbl-entrypoint.sh
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/pbl-entrypoint.sh"]

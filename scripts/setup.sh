#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  setup.sh — Provision a fresh Ubuntu 22.04 / 24.04 VM for the Rinri RAG stack.
#
#  Installs:
#    - NVIDIA GPU driver (skipped if nvidia-smi already works)
#    - Docker Engine + Compose plugin
#    - NVIDIA Container Toolkit
#
#  Target: さくらのクラウド GPU サーバー(V100 32GB)等、Ubuntu の新規 VM。
#
#  Usage (on the VPS, as a user with sudo):
#      curl -fsSL <this-script-url> | sudo bash
#    or
#      sudo bash scripts/setup.sh
#
#  After install, a reboot may be required if the NVIDIA driver was newly
#  installed. The script will print the appropriate next steps.
# -----------------------------------------------------------------------------
set -euo pipefail

# ---- guards -----------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root (use sudo)." >&2
  exit 1
fi

if ! grep -qi ubuntu /etc/os-release; then
  echo "This script targets Ubuntu. Detected: $(cat /etc/os-release | grep ^NAME= || true)" >&2
  exit 1
fi

. /etc/os-release
UBUNTU_CODENAME="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
if [ -z "$UBUNTU_CODENAME" ]; then
  echo "Could not determine Ubuntu codename." >&2
  exit 1
fi
echo "==> Ubuntu $VERSION ($UBUNTU_CODENAME)"

export DEBIAN_FRONTEND=noninteractive

NEED_REBOOT=0

# ---- base packages ----------------------------------------------------------
echo "==> Updating apt and installing base packages"
apt-get update -y
apt-get install -y \
  ca-certificates curl gnupg lsb-release \
  git jq htop tmux

# ---- NVIDIA driver ----------------------------------------------------------
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  echo "==> NVIDIA driver already installed:"
  nvidia-smi | head -n 4 || true
else
  echo "==> Installing NVIDIA driver via ubuntu-drivers autoinstall"
  apt-get install -y ubuntu-drivers-common
  ubuntu-drivers autoinstall
  NEED_REBOOT=1
fi

# ---- Docker Engine ----------------------------------------------------------
if command -v docker >/dev/null 2>&1; then
  echo "==> Docker already installed: $(docker --version)"
else
  echo "==> Installing Docker Engine"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc

  cat > /etc/apt/sources.list.d/docker.list <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME} stable
EOF

  apt-get update -y
  apt-get install -y \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
fi

systemctl enable --now docker

# ---- NVIDIA Container Toolkit ----------------------------------------------
if dpkg -l | grep -q '^ii\s\+nvidia-container-toolkit\s'; then
  echo "==> NVIDIA Container Toolkit already installed"
else
  echo "==> Installing NVIDIA Container Toolkit"
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey |
    gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list

  apt-get update -y
  apt-get install -y nvidia-container-toolkit
fi

echo "==> Configuring Docker to use the NVIDIA runtime"
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# ---- add invoking user to docker group -------------------------------------
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
  if ! id -nG "$SUDO_USER" | tr ' ' '\n' | grep -qx docker; then
    echo "==> Adding $SUDO_USER to docker group"
    usermod -aG docker "$SUDO_USER"
    echo "   (log out and back in for this to take effect)"
  fi
fi

# ---- done -------------------------------------------------------------------
echo
echo "=============================================="
if [ "$NEED_REBOOT" -eq 1 ]; then
  cat <<EOF
  NVIDIA driver was just installed. Please REBOOT:

      sudo reboot

  After reboot, verify with:

      nvidia-smi
      docker run --rm --gpus all ubuntu nvidia-smi
EOF
else
  cat <<EOF
  Setup complete. Verify with:

      nvidia-smi
      docker run --rm --gpus all ubuntu nvidia-smi
EOF
fi
echo "=============================================="

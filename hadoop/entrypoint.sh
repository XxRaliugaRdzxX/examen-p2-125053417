#!/bin/bash
# Prepara el acceso SSH sin contrasena y arranca el comando principal (sshd).
# Las llaves se generan en tiempo de ejecucion (nunca se guardan en la imagen)
# y se comparten con el contenedor 'api' por el volumen /ssh-keys.
set -e

KEYS=/ssh-keys
mkdir -p "$KEYS"

# 1) Llaves de host del servidor SSH: se persisten para que no cambien
#    cuando se recrea el contenedor (evita el aviso de "host key changed").
if ls "$KEYS"/ssh_host_* >/dev/null 2>&1; then
    cp "$KEYS"/ssh_host_* /etc/ssh/
else
    ssh-keygen -A
    cp /etc/ssh/ssh_host_* "$KEYS"/
fi
chmod 600 /etc/ssh/ssh_host_*_key

# 2) Par de llaves del cliente (ssh-keygen sin passphrase)
if [ ! -f "$KEYS/id_ed25519" ]; then
    ssh-keygen -t ed25519 -N "" -C "hadoop@datamart" -f "$KEYS/id_ed25519" -q
fi
chmod 600 "$KEYS/id_ed25519"
chmod 644 "$KEYS/id_ed25519.pub"

# 3) Usuario hadoop: authorized_keys + su propia llave (para 'ssh localhost')
install -d -m 700 -o hadoop -g hadoop /home/hadoop/.ssh
install -m 600 -o hadoop -g hadoop "$KEYS/id_ed25519"     /home/hadoop/.ssh/id_ed25519
install -m 644 -o hadoop -g hadoop "$KEYS/id_ed25519.pub" /home/hadoop/.ssh/id_ed25519.pub
install -m 600 -o hadoop -g hadoop "$KEYS/id_ed25519.pub" /home/hadoop/.ssh/authorized_keys

# 4) root tambien puede hacer 'ssh localhost' (entra como usuario hadoop)
install -d -m 700 /root/.ssh
cat > /root/.ssh/config <<EOF
Host localhost hadoop
    User hadoop
    IdentityFile $KEYS/id_ed25519
    StrictHostKeyChecking accept-new
EOF
sed "s#IdentityFile .*#IdentityFile ~/.ssh/id_ed25519#" /root/.ssh/config > /home/hadoop/.ssh/config
chown hadoop:hadoop /home/hadoop/.ssh/config
chmod 600 /home/hadoop/.ssh/config /root/.ssh/config

exec "$@"

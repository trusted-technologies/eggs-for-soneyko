#!/bin/bash
set -euo pipefail
state=/home/container/.instance
rootfs="$state/rootfs"
mkdir -p "$state"
if [ ! -f "$state/initialized" ]; then
    mkdir -p "$rootfs"
    # All guest files live in the ordinary Wings server volume, including /etc
    # and package-manager state. Recreating the Docker container preserves them.
    tar -C /opt/soneyko/rootfs -cf - . | tar --no-same-owner -C "$rootfs" -xf -
    if [ -d "$rootfs/etc/apt/apt.conf.d" ]; then
        # PRoot cannot give _apt a separate host UID. Keep APT inside the same
        # emulated guest identity; Docker still enforces unprivileged UID 1000.
        # Repository signature verification remains enabled.
        printf 'APT::Sandbox::User "root";\n' > "$rootfs/etc/apt/apt.conf.d/99soneyko-proot"
    fi
    touch "$state/initialized"
fi
mkdir -p "$rootfs/etc" "$rootfs/root" "$rootfs/workspace" "$rootfs/tmp"
cp /etc/resolv.conf "$rootfs/etc/resolv.conf"
cp /etc/hosts "$rootfs/etc/hosts"
shell=/bin/sh
if [ -x "$rootfs/bin/bash" ] || [ -x "$rootfs/usr/bin/bash" ]; then shell=/bin/bash; fi
echo 'Soneyko Linux environment ready'
# Root here is emulated by PRoot; the outer process remains the unprivileged
# container user with the same cgroups, network namespace and disk quota.
if [ "${1:-}" = /usr/local/bin/soneyko-instance ]; then shift; fi
if [ "$#" -eq 0 ]; then set -- "$shell" -il; fi
exec proot -0 -r "$rootfs" -b /dev -b /proc -b /sys \
    -b /home/container:/workspace -w /root \
    /usr/bin/env -i HOME=/root USER=root LOGNAME=root \
    TERM="${TERM:-xterm-256color}" PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    SERVER_PORT="${SERVER_PORT:-}" "$@"

#!/bin/bash
# Downgrade a Pulp system from master to 2.7.
#
# WARNING: This script enabled and disables system-wide yum/dnf repositories and
# performs other system-wide actions. Execute with care.
set -euo pipefail

# Downgrade these plugins to version 2.7.
pushd ~/devel
for repo in pulp{,_puppet,_rpm}; do
    if [ -d "$repo" ]; then
        pushd "$repo"
        git checkout 2.7-dev
        find . -name '*.py[c0]' -delete
        sudo ./pulp-dev.py --install
        popd
    fi
done
popd

# Completely uninstall these plugins. Some or all of these plugins are available
# for Pulp 2.7, but the authors of this script have not (yet!) needed to
# determine which branch(es) should be checked out. Patches welcome.
pushd ~/devel
for repo in pulp_{docker,python}; do
    if [ -d "$repo" ]; then
        pushd "$repo"
        sudo ./pulp-dev.py --uninstall
        popd
    fi
done
popd

set -x

# These aren't used by Pulp 2.7.
sudo rm /etc/httpd/conf.d/pulp_content.conf
sudo rm /etc/httpd/conf.d/pulp_streamer.conf

# Pulp 2.7 is incompatible with python-mongoengine >= 3 and python-pymongo >=
# 0.10.
sudo dnf  -y remove python-{mongoengine,pymongo}
sudo dnf config-manager --disablerepo pulp-nightlies
sudo dnf config-manager --enablerepo pulp-2.7-beta
sudo dnf -y install python-mongoengine-0.8.8 python-pymongo-2.5.2

fmt <<EOF
This script does not touch the Pulp database or change the state of Pulp
services. If downgrading from Pulp master, you may wish to execute the
following:
EOF
cat <<EOF

    mongo pulp_database --eval 'db.dropDatabase()'
    sudo -u apache pulp-manage-db
    prestart

EOF
fmt <<EOF
If upgrading from Pulp 2.6, you may wish to do something similar.
EOF

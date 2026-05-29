#!/bin/bash

set -e

INSTALL_DIR=/APP/wails_tftp
sudo mkdir -p $INSTALL_DIR/
sudo cp wails_tftp/build/bin/wails_tftp $INSTALL_DIR/
sudo sudo setcap cap_net_bind_service=+ep $INSTALL_DIR/wails_tftp
sudo cp icon.png $INSTALL_DIR/
sudo cp wails_tftp.desktop /usr/local/share/applications/
echo finish
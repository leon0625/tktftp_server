#!/bin/bash
INSTALL_DIR=/APP/tktftp
sudo ls
rm -rf dist build
pyinstaller -F tktftp.py --add-data 'icon.png:.' --hidden-import=PIL._tkinter_finder
sudo mkdir -p /APP/tktftp
sudo cp dist/tktftp $INSTALL_DIR/
sudo cp icon.png $INSTALL_DIR/
sudo cp tktftp.desktop /usr/local/share/applications/
sudo cp tktftp.policy /usr/share/polkit-1/actions/
 
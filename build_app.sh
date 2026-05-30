#!/bin/bash
# Build the Netnova Job Scraper desktop app using PyInstaller.
# Run from the AIWORKFLOW project root: bash build_app.sh
# Output: dist/Netnova Job Scraper.app  (macOS)
#         dist/Netnova Job Scraper.exe  (Windows)

set -e

echo "Installing/upgrading PyInstaller..."
pip3 install --quiet pyinstaller==6.6.0 customtkinter==5.2.2 Pillow==10.3.0

echo "Building app..."
pyinstaller \
  --onefile \
  --windowed \
  --name "Netnova Job Scraper" \
  --add-data "log.png:." \
  --add-data "config.json:." \
  --add-data ".env:." \
  app.py

echo ""
echo "✓ Build complete."
echo "  macOS app : dist/Netnova Job Scraper.app"
echo "  Windows   : dist/Netnova Job Scraper.exe"
echo ""
echo "Send the entire 'dist/' folder to your client."

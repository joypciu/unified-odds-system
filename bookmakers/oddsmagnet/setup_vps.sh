#!/bin/bash
# VPS Setup Script for OddsMagnet Parallel Scraper

echo "================================================"
echo "OddsMagnet Parallel Scraper - VPS Setup"
echo "================================================"

# Install Chrome on Ubuntu/Debian VPS
echo ""
echo "Installing Chrome..."
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt-get update
sudo apt-get install -y google-chrome-stable

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install playwright
python -m playwright install chromium

# Verify installation
echo ""
echo "Verifying installation..."
google-chrome --version
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"

echo ""
echo "================================================"
echo "Setup complete!"
echo "================================================"
echo ""
echo "To run the scraper in VPS mode:"
echo "  python oddsmagnet_realtime_parallel.py --mode vps --interval 30"
echo ""
echo "To run as a background service:"
echo "  nohup python oddsmagnet_realtime_parallel.py --mode vps --interval 30 > scraper.log 2>&1 &"
echo ""

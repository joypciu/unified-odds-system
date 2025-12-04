#!/bin/bash
# Unified Odds System - Complete VPS Deployment Script
# This script sets up the unified odds system on Ubuntu VPS with GitHub integration

set -e  # Exit on any error

echo "=========================================="
echo "🚀 Unified Odds System - VPS Deployment"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/ubuntu/services/unified-odds"
SERVICE_NAME="unified-odds"
GITHUB_REPO="git@github.com:joypciu/unified-odds-system.git"  # SSH URL

echo "📍 Project directory: $PROJECT_DIR"
echo "📦 Service name: $SERVICE_NAME"
echo ""

# Function to print colored output
print_step() {
    echo -e "${GREEN}➤ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as ubuntu user
if [ "$USER" != "ubuntu" ]; then
    print_warning "This script should be run as 'ubuntu' user"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 1: Install system dependencies
print_step "Installing system dependencies..."
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    google-chrome-stable \
    xvfb \
    curl \
    wget \
    gawk \
    util-linux

# If Chrome installation failed, try alternative method
if ! command -v google-chrome &> /dev/null; then
    print_warning "Chrome not found, installing via wget..."
    cd /tmp
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo dpkg -i google-chrome-stable_current_amd64.deb || sudo apt-get install -f -y
    rm google-chrome-stable_current_amd64.deb
fi

# Verify Chrome installation
if command -v google-chrome &> /dev/null; then
    CHROME_VERSION=$(google-chrome --version)
    echo "  ✓ Chrome installed: $CHROME_VERSION"
else
    print_error "Chrome installation failed!"
    exit 1
fi

# Step 2: Create project directory
print_step "Setting up project directory..."
sudo mkdir -p "$PROJECT_DIR"
sudo chown ubuntu:ubuntu "$PROJECT_DIR"

# Step 3: Clone or update repository
if [ -d "$PROJECT_DIR/.git" ]; then
    print_step "Repository exists, updating..."
    cd "$PROJECT_DIR"
    git pull origin main
else
    print_step "Cloning repository from GitHub..."
    # Remove directory if it exists but is not a git repo
    if [ -d "$PROJECT_DIR" ]; then
        sudo rm -rf "$PROJECT_DIR"
    fi
    git clone "$GITHUB_REPO" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# Step 4: Setup Python virtual environment
print_step "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Step 5: Install Python dependencies
print_step "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install playwright browsers
print_step "Installing Playwright browsers..."
playwright install chromium

echo "  ✓ Python dependencies installed"

# Step 6: Create necessary directories
print_step "Creating data directories..."
mkdir -p bet365/logs
mkdir -p fanduel/logs
mkdir -p 1xbet
mkdir -p cache_backups
echo "  ✓ Directories created"

# Step 7: Configure systemd service
print_step "Configuring systemd service..."
sudo cp unified-odds.service /etc/systemd/system/
sudo systemctl daemon-reload
echo "  ✓ Service file installed"

# Step 8: Setup log rotation
print_step "Setting up log rotation..."
sudo tee /etc/logrotate.d/unified-odds > /dev/null <<EOF
/var/log/unified-odds/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 ubuntu ubuntu
}
EOF
sudo mkdir -p /var/log/unified-odds
sudo chown ubuntu:ubuntu /var/log/unified-odds
echo "  ✓ Log rotation configured"

# Step 9: Setup GitHub deploy key (if provided)
print_step "Checking for GitHub deploy key..."
if [ ! -f "$HOME/.ssh/unified_odds_deploy" ]; then
    print_warning "No GitHub deploy key found at ~/.ssh/unified_odds_deploy"
    print_warning "For automatic deployments, you should:"
    echo "  1. Generate SSH key: ssh-keygen -t ed25519 -f ~/.ssh/unified_odds_deploy"
    echo "  2. Add public key to GitHub repo: Settings > Deploy keys"
    echo "  3. Configure git to use the key in ~/.ssh/config"
else
    echo "  ✓ GitHub deploy key exists"
    # Configure git to use deploy key
    if [ ! -f "$HOME/.ssh/config" ] || ! grep -q "unified-odds" "$HOME/.ssh/config"; then
        print_step "Configuring SSH for GitHub..."
        cat >> "$HOME/.ssh/config" <<EOF

# Unified Odds System GitHub Deploy Key
Host github.com-unified-odds
    HostName github.com
    User git
    IdentityFile ~/.ssh/unified_odds_deploy
    IdentitiesOnly yes
EOF
        chmod 600 "$HOME/.ssh/config"
        echo "  ✓ SSH config updated"
    fi
fi

# Step 10: Test Chrome with xvfb
print_step "Testing Chrome with xvfb..."
if xvfb-run -a google-chrome --version &> /dev/null; then
    echo "  ✓ Chrome works with xvfb"
else
    print_warning "Chrome test with xvfb failed, but continuing..."
fi

# Step 11: Create update script for easy deployments
print_step "Creating update script..."
cat > "$PROJECT_DIR/update_from_github.sh" <<'UPDATESCRIPT'
#!/bin/bash
# Quick update script for unified odds system

cd /home/ubuntu/services/unified-odds

echo "📥 Pulling latest changes..."
git pull origin main

echo "📦 Updating dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo "🔄 Restarting service..."
sudo systemctl restart unified-odds

sleep 3

echo "✅ Checking status..."
sudo systemctl status unified-odds --no-pager

echo "🎉 Update complete!"
UPDATESCRIPT

chmod +x "$PROJECT_DIR/update_from_github.sh"
echo "  ✓ Update script created at $PROJECT_DIR/update_from_github.sh"

# Step 12: Enable and start service
print_step "Starting unified odds service..."
sudo systemctl enable unified-odds
sudo systemctl restart unified-odds

# Wait for service to start
sleep 5

# Step 13: Check service status
print_step "Checking service status..."
if sudo systemctl is-active --quiet unified-odds; then
    echo -e "${GREEN}  ✓ Service is running!${NC}"
    sudo systemctl status unified-odds --no-pager | head -15
else
    print_error "Service failed to start!"
    echo "Recent logs:"
    sudo journalctl -u unified-odds -n 30 --no-pager
    exit 1
fi

# Step 14: Display useful information
echo ""
echo "=========================================="
echo "🎉 Deployment Complete!"
echo "=========================================="
echo ""
echo "📊 Service Management:"
echo "  Start:   sudo systemctl start unified-odds"
echo "  Stop:    sudo systemctl stop unified-odds"
echo "  Restart: sudo systemctl restart unified-odds"
echo "  Status:  sudo systemctl status unified-odds"
echo "  Logs:    sudo journalctl -u unified-odds -f"
echo ""
echo "🔄 Quick Update:"
echo "  cd $PROJECT_DIR && ./update_from_github.sh"
echo ""
echo "📁 Project Location:"
echo "  $PROJECT_DIR"
echo ""
echo "📝 Data Files:"
echo "  Unified odds: $PROJECT_DIR/unified_odds.json"
echo "  Bet365 data:  $PROJECT_DIR/bet365/*.json"
echo "  FanDuel data: $PROJECT_DIR/fanduel/*.json"
echo "  1xBet data:   $PROJECT_DIR/1xbet/*.json"
echo ""
echo "🌐 API Endpoints (if monitoring is enabled):"
echo "  Status: curl http://localhost:5000/health"
echo "  Odds:   curl http://localhost:5000/odds"
echo ""
echo "🔧 GitHub Deployment:"
echo "  Push to main branch to trigger automatic deployment"
echo "  Webhook will pull changes and restart service"
echo ""
echo "⚠️  Important Notes:"
echo "  1. Make sure config.json has correct email settings"
echo "  2. Chrome will run via xvfb (virtual display)"
echo "  3. Service logs to journalctl and /var/log/unified-odds/"
echo "  4. Memory limit: 2GB, CPU limit: 150%"
echo ""
echo "✅ Setup complete! The system is now running."

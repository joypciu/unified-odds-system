#!/bin/bash
# Unified Odds System - Automated VPS Deployment Script with GitHub SSH Setup
# This script handles EVERYTHING including SSH key generation and GitHub configuration

set -e  # Exit on any error

echo "=========================================="
echo "🚀 Unified Odds System - Auto Deployment"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/ubuntu/services/unified-odds"
SERVICE_NAME="unified-odds"
GITHUB_REPO_OWNER="joypciu"
GITHUB_REPO_NAME="unified-odds-system"
GITHUB_REPO_SSH="git@github.com:${GITHUB_REPO_OWNER}/${GITHUB_REPO_NAME}.git"

echo "📍 Project directory: $PROJECT_DIR"
echo "📦 Service name: $SERVICE_NAME"
echo "📦 GitHub repo: joypciu/$GITHUB_REPO_NAME"
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

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
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
    xvfb \
    curl \
    wget \
    gawk \
    util-linux

# Install Chrome
if ! command -v google-chrome &> /dev/null; then
    print_warning "Chrome not found, installing..."
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

# Step 2: Setup SSH key for GitHub if not exists
print_step "Setting up GitHub SSH access..."

SSH_KEY_PATH="$HOME/.ssh/id_ed25519"
SSH_CONFIG_PATH="$HOME/.ssh/config"

if [ ! -f "$SSH_KEY_PATH" ]; then
    print_info "Generating SSH key..."
    ssh-keygen -t ed25519 -C "ubuntu@vps-unified-odds" -f "$SSH_KEY_PATH" -N ""
    echo "  ✓ SSH key generated"
else
    echo "  ✓ SSH key already exists"
fi

# Add GitHub to known hosts
if ! grep -q "github.com" ~/.ssh/known_hosts 2>/dev/null; then
    ssh-keyscan -H github.com >> ~/.ssh/known_hosts 2>/dev/null
    echo "  ✓ GitHub added to known hosts"
fi

# Configure SSH config for GitHub
if [ ! -f "$SSH_CONFIG_PATH" ]; then
    touch "$SSH_CONFIG_PATH"
    chmod 600 "$SSH_CONFIG_PATH"
fi

if ! grep -q "Host github.com" "$SSH_CONFIG_PATH"; then
    print_info "Configuring SSH for GitHub..."
    cat >> "$SSH_CONFIG_PATH" <<EOF

# Unified Odds System GitHub Access
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
EOF
    chmod 600 "$SSH_CONFIG_PATH"
    echo "  ✓ SSH config updated"
else
    echo "  ✓ SSH config already configured"
fi

# Display public key for user to add to GitHub
echo ""
echo "=========================================="
echo "📋 IMPORTANT: Add this SSH key to GitHub"
echo "=========================================="
echo ""
cat "$SSH_KEY_PATH.pub"
echo ""
echo "👉 Follow these steps:"
echo "   1. Copy the SSH key above"
echo "   2. Go to: https://github.com/joypciu/$GITHUB_REPO_NAME/settings/keys"
echo "   3. Click 'Add deploy key'"
echo "   4. Paste the key and give it a title: 'VPS Deploy Key'"
echo "   5. ✅ Check 'Allow write access' (optional)"
echo "   6. Click 'Add key'"
echo ""
read -p "Press ENTER after you've added the key to GitHub..." 

# Test GitHub SSH connection
print_step "Testing GitHub SSH connection..."
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "  ✓ GitHub SSH connection successful"
else
    print_error "GitHub SSH connection failed!"
    print_error "Please make sure you added the SSH key to GitHub."
    print_error "Visit: https://github.com/${GITHUB_REPO_OWNER}/${GITHUB_REPO_NAME}/settings/keys"
    exit 1
fi

# Step 3: Clone or update repository
print_step "Setting up project directory..."
sudo mkdir -p "$PROJECT_DIR"
sudo chown ubuntu:ubuntu "$PROJECT_DIR"

if [ -d "$PROJECT_DIR/.git" ]; then
    print_step "Repository exists, updating..."
    cd "$PROJECT_DIR"
    git pull origin main
else
    print_step "Cloning repository from GitHub..."
    if [ -d "$PROJECT_DIR" ] && [ "$(ls -A $PROJECT_DIR)" ]; then
        print_warning "Directory exists and is not empty, removing..."
        sudo rm -rf "$PROJECT_DIR"
    fi
    git clone "$GITHUB_REPO_SSH" "$PROJECT_DIR"
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

# Step 7: Setup config.json if it doesn't exist
print_step "Checking configuration file..."
if [ ! -f "config.json" ]; then
    if [ -f "config.json.template" ]; then
        print_warning "config.json not found, creating from template..."
        cp config.json.template config.json
        echo "  ⚠️  Please edit config.json and update email settings:"
        echo "      nano $PROJECT_DIR/config.json"
    else
        print_error "No config.json or config.json.template found!"
    fi
else
    echo "  ✓ config.json exists"
fi

# Step 8: Configure systemd service
print_step "Configuring systemd service..."
sudo cp unified-odds.service /etc/systemd/system/
sudo systemctl daemon-reload
echo "  ✓ Service file installed"

# Step 9: Setup log rotation
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
    echo ""
    print_info "This might be because config.json needs to be configured."
    print_info "Edit config.json and restart: sudo systemctl restart unified-odds"
    # Don't exit, let user fix config
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
echo "⚙️  Configuration:"
echo "  Edit: nano $PROJECT_DIR/config.json"
echo "  Then: sudo systemctl restart unified-odds"
echo ""
echo "📝 Data Files:"
echo "  Unified odds: $PROJECT_DIR/unified_odds.json"
echo "  Bet365 data:  $PROJECT_DIR/bet365/*.json"
echo "  FanDuel data: $PROJECT_DIR/fanduel/*.json"
echo "  1xBet data:   $PROJECT_DIR/1xbet/*.json"
echo ""
echo "🔧 GitHub Actions Setup:"
echo "  Next, configure GitHub Actions for auto-deployment:"
echo "  1. Get your SSH private key:"
echo "     cat ~/.ssh/id_ed25519"
echo "  2. Add these secrets to GitHub repo:"
echo "     Settings → Secrets → Actions → New repository secret"
echo "     - VPS_HOST: 142.44.160.36"
echo "     - VPS_USERNAME: ubuntu"
echo "     - VPS_SSH_KEY: <paste entire private key>"
echo "     - VPS_PORT: 22"
echo "  3. Push to main branch to trigger auto-deployment"
echo ""
echo "✅ Setup complete! The system is now running."
echo ""

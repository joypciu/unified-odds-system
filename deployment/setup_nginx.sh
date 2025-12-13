#!/bin/bash
# Nginx Setup and Configuration Script for Unified Odds System
# Run this script on the VPS to install and configure Nginx

set -e  # Exit on any error

echo "=========================================="
echo "🚀 Nginx Setup for Unified Odds System"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
NC='\033[0m' # No Color

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

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run this script with sudo"
    exit 1
fi

print_step "Step 1: Installing Nginx"
apt-get update
apt-get install -y nginx

print_step "Step 2: Checking Nginx version"
nginx -v

print_step "Step 3: Creating cache directories"
mkdir -p /var/cache/nginx/api_cache
mkdir -p /var/cache/nginx/odds_cache
mkdir -p /var/cache/nginx/html_cache
mkdir -p /var/cache/nginx/proxy_temp

# Set proper permissions
chown -R www-data:www-data /var/cache/nginx
chmod -R 755 /var/cache/nginx

print_step "Step 4: Creating log directory"
mkdir -p /var/log/nginx
chown -R www-data:adm /var/log/nginx

print_step "Step 5: Backing up original Nginx configuration"
if [ ! -f /etc/nginx/nginx.conf.backup ]; then
    cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup
    print_info "Backup created at /etc/nginx/nginx.conf.backup"
else
    print_warning "Backup already exists, skipping"
fi

print_step "Step 6: Copying Nginx configuration files"
PROJECT_DIR="/home/ubuntu/services/unified-odds"

# Copy main site configuration
if [ -f "$PROJECT_DIR/deployment/nginx/unified-odds.conf" ]; then
    cp "$PROJECT_DIR/deployment/nginx/unified-odds.conf" /etc/nginx/sites-available/unified-odds
    print_info "Copied unified-odds.conf to sites-available"
else
    print_error "unified-odds.conf not found in $PROJECT_DIR/deployment/nginx/"
    exit 1
fi

# Create symbolic link to enable site
print_step "Step 7: Enabling site configuration"
ln -sf /etc/nginx/sites-available/unified-odds /etc/nginx/sites-enabled/unified-odds

# Remove default site if exists
if [ -f /etc/nginx/sites-enabled/default ]; then
    print_warning "Removing default Nginx site"
    rm /etc/nginx/sites-enabled/default
fi

print_step "Step 8: Updating main nginx.conf"
print_info "Please manually add cache paths to /etc/nginx/nginx.conf"
print_info "Reference: $PROJECT_DIR/deployment/nginx/nginx-http-block.conf"

print_step "Step 9: Testing Nginx configuration"
if nginx -t; then
    print_info "✓ Nginx configuration test passed"
else
    print_error "Nginx configuration test failed"
    print_info "Run: nginx -t"
    print_info "Check configuration and try again"
    exit 1
fi

print_step "Step 10: Starting/Restarting Nginx"
systemctl enable nginx
systemctl restart nginx

print_step "Step 11: Checking Nginx status"
if systemctl is-active --quiet nginx; then
    print_info "✓ Nginx is running"
else
    print_error "Nginx failed to start"
    print_info "Check logs: journalctl -u nginx -n 50"
    exit 1
fi

print_step "Step 12: Firewall configuration"
if command -v ufw &> /dev/null; then
    print_info "Allowing HTTP and HTTPS through firewall"
    ufw allow 'Nginx Full'
    ufw status
else
    print_warning "UFW not installed, skipping firewall configuration"
fi

echo ""
echo "=========================================="
echo "✅ Nginx Setup Complete!"
echo "=========================================="
echo ""
echo "📊 Status Check:"
echo "  - Nginx status: $(systemctl is-active nginx)"
echo "  - Configuration: /etc/nginx/sites-available/unified-odds"
echo "  - Cache directories: /var/cache/nginx/"
echo "  - Logs: /var/log/nginx/"
echo ""
echo "🧪 Testing:"
echo "  1. Test API: curl http://142.44.160.36/api/health"
echo "  2. Test OddsMagnet: curl -I http://142.44.160.36/oddsmagnet/football/top10"
echo "  3. Check cache headers: Look for 'X-Cache-Status' header"
echo ""
echo "📝 Useful Commands:"
echo "  - Reload config: sudo systemctl reload nginx"
echo "  - Restart Nginx: sudo systemctl restart nginx"
echo "  - View logs: sudo tail -f /var/log/nginx/unified-odds-access.log"
echo "  - Test config: sudo nginx -t"
echo "  - Clear cache: sudo rm -rf /var/cache/nginx/*"
echo ""
echo "🔍 Monitor cache:"
echo "  - Cache size: du -sh /var/cache/nginx/*"
echo "  - Cache status in headers: curl -I http://142.44.160.36/oddsmagnet/football/top10 | grep X-Cache"
echo ""

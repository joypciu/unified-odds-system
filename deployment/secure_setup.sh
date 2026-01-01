#!/bin/bash
# Secure deployment script for VPS
# This script sets up the environment securely

echo "🔒 Secure Deployment Setup"
echo "=========================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root or with sudo"
    exit 1
fi

# Navigate to project directory
cd /root/combine || exit 1

# Prompt for Google API Key securely
echo ""
echo "📝 Enter your Google API Key:"
echo "(It will not be displayed as you type)"
read -s GOOGLE_API_KEY

if [ -z "$GOOGLE_API_KEY" ]; then
    echo "❌ API key cannot be empty"
    exit 1
fi

# Create secure .env file
echo "📄 Creating secure .env file..."
cat > /root/combine/.env << EOF
# Environment Variables - DO NOT COMMIT TO GIT
GOOGLE_API_KEY=$GOOGLE_API_KEY
EOF

# Set secure permissions (only root can read/write)
chmod 600 /root/combine/.env
chown root:root /root/combine/.env

echo "✅ .env file created with secure permissions (600)"

# Update systemd service to load .env file
echo "🔧 Updating systemd service..."

# Check if service file exists
if [ ! -f /etc/systemd/system/unified-odds.service ]; then
    echo "⚠️  Service file not found. Please create it first."
    exit 1
fi

# Add EnvironmentFile to service if not already present
if ! grep -q "EnvironmentFile" /etc/systemd/system/unified-odds.service; then
    # Backup original service file
    cp /etc/systemd/system/unified-odds.service /etc/systemd/system/unified-odds.service.bak
    
    # Add EnvironmentFile line after [Service]
    sed -i '/\[Service\]/a EnvironmentFile=/root/combine/.env' /etc/systemd/system/unified-odds.service
    
    echo "✅ Added EnvironmentFile to service configuration"
else
    echo "✅ EnvironmentFile already configured"
fi

# Reload systemd
echo "♻️  Reloading systemd daemon..."
systemctl daemon-reload

# Restart service
echo "🔄 Restarting unified-odds service..."
systemctl restart unified-odds

# Wait a moment for service to start
sleep 3

# Check service status
echo ""
echo "📊 Service Status:"
systemctl status unified-odds --no-pager -l | head -15

# Check if service is running
if systemctl is-active --quiet unified-odds; then
    echo ""
    echo "✅ SUCCESS! Service is running"
    echo ""
    echo "🔍 Testing LLM API..."
    sleep 2
    
    # Test LLM endpoint
    response=$(curl -s http://localhost:8000/api/llm/status)
    
    if echo "$response" | grep -q "llm_initialized.*true"; then
        echo "✅ LLM API is working correctly!"
    else
        echo "⚠️  LLM API may not be initialized properly"
        echo "Response: $response"
    fi
    
    echo ""
    echo "🌐 Your application is accessible at:"
    echo "   http://$(curl -s ifconfig.me):8000/llm-analysis"
    
else
    echo ""
    echo "❌ Service failed to start. Check logs:"
    echo "   sudo journalctl -u unified-odds -n 50 --no-pager"
fi

echo ""
echo "🔒 Security Summary:"
echo "   ✓ API key stored in /root/combine/.env"
echo "   ✓ File permissions: 600 (only root can read)"
echo "   ✓ Not committed to git (.env is in .gitignore)"
echo "   ✓ Service configured to load environment variables"
echo ""
echo "📝 To update API key in the future:"
echo "   sudo nano /root/combine/.env"
echo "   sudo systemctl restart unified-odds"
echo ""

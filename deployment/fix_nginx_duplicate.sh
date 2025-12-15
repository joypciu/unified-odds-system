#!/bin/bash
# Fix Duplicate Upstream Error in Nginx
# Error: duplicate upstream "unified_odds_backend" in /etc/nginx/sites-enabled/unified-odds.conf:5

set -e

echo "======================================================================"
echo "🔧 FIXING NGINX DUPLICATE UPSTREAM ERROR"
echo "======================================================================"
echo ""

echo "📋 Checking for duplicate nginx configuration files..."
echo ""
echo "Files in sites-enabled:"
ls -la /etc/nginx/sites-enabled/ | grep unified-odds || echo "   No unified-odds files found"
echo ""

echo "Files in sites-available:"
ls -la /etc/nginx/sites-available/ | grep unified-odds || echo "   No unified-odds files found"
echo ""

echo "🗑️  Removing all existing unified-odds configurations..."
sudo rm -f /etc/nginx/sites-enabled/unified-odds.conf
sudo rm -f /etc/nginx/sites-enabled/unified-odds
sudo rm -f /etc/nginx/sites-available/unified-odds.conf
echo "   ✅ Old configurations removed"
echo ""

echo "📝 Installing fresh nginx configuration..."
sudo cp deployment/nginx/unified-odds.conf /etc/nginx/sites-available/unified-odds.conf
sudo chmod 644 /etc/nginx/sites-available/unified-odds.conf
echo "   ✅ Configuration file copied"
echo ""

echo "🔗 Creating symlink in sites-enabled..."
sudo ln -s /etc/nginx/sites-available/unified-odds.conf /etc/nginx/sites-enabled/unified-odds.conf
echo "   ✅ Symlink created"
echo ""

echo "✅ Verifying nginx configuration..."
sudo nginx -t
echo ""

if [ $? -eq 0 ]; then
    echo "🔄 Reloading nginx..."
    sudo systemctl reload nginx
    echo "   ✅ Nginx reloaded successfully"
    echo ""
    
    echo "📊 Checking nginx status..."
    sudo systemctl status nginx --no-pager -l | head -20
    echo ""
    
    echo "======================================================================"
    echo "✅ NGINX CONFIGURATION FIXED"
    echo "======================================================================"
    echo ""
    echo "🌐 Test your endpoints:"
    echo "   curl http://localhost/"
    echo "   curl http://localhost/health"
    echo "   curl http://localhost/oddsmagnet"
    echo ""
else
    echo "❌ Nginx configuration test failed!"
    echo "Please check the error messages above"
    exit 1
fi

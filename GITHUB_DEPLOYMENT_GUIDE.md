# GitHub-Based VPS Deployment Guide
## Unified Odds System - Automatic Deployment

This guide explains how to set up automatic deployment of the Unified Odds System to your VPS using GitHub integration. Every time you push changes to the `main` branch, the VPS will automatically pull the changes and restart the service.

---

## 🎯 Overview

**What this setup does:**
- ✅ Monitors GitHub repository for changes
- ✅ Automatically deploys on push to `main` branch
- ✅ Pulls latest code to VPS
- ✅ Installs/updates dependencies
- ✅ Restarts the service
- ✅ Uses Ubuntu's Chrome (not Windows Chrome)
- ✅ Runs via xvfb (virtual display)
- ✅ Managed by systemd for auto-restart on crash

---

## 📋 Prerequisites

### On Your VPS:
- Ubuntu 20.04+ (tested on Ubuntu 22.04)
- SSH access with sudo privileges
- At least 2GB RAM
- Google Chrome installed
- Git installed

### On GitHub:
- Repository for the unified odds system
- GitHub account with repo access
- Ability to add deploy keys and secrets

---

## 🚀 Initial Setup (One-Time)

### Step 1: Push Code to GitHub

1. **Create a new GitHub repository** (if not already done):
   - Go to https://github.com/new
   - Name it: `unified-odds-system`
   - Make it private (recommended for production data)
   - Do NOT initialize with README (we have one)

2. **Push your code** from the local project folder:

```powershell
# Navigate to your project folder
cd "C:\Users\User\Desktop\thesis\work related task\vps deploy\combine 1xbet, fanduel and bet365 (main)"

# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Unified odds system"

# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/unified-odds-system.git

# Push to main branch
git branch -M main
git push -u origin main
```

### Step 2: Setup VPS Deployment

1. **SSH into your VPS**:
```bash
ssh ubuntu@142.44.160.36
```

2. **Upload the deployment script**:

You can either:
- **Option A**: Use WinSCP to upload `deploy_unified_odds.sh` to `/home/ubuntu/`
- **Option B**: Create it directly on VPS:

```bash
nano ~/deploy_unified_odds.sh
# Paste the content from deploy_unified_odds.sh
# Press Ctrl+X, then Y, then Enter to save
chmod +x ~/deploy_unified_odds.sh
```

3. **Run the deployment script**:
```bash
cd ~
./deploy_unified_odds.sh
```

This will:
- Install Chrome and dependencies
- Clone the GitHub repository
- Create Python virtual environment
- Install Python packages
- Setup systemd service
- Start the unified odds system

4. **Configure your config.json** (if not already done):
```bash
cd /home/ubuntu/services/unified-odds
nano config.json
# Update email credentials and settings
```

### Step 3: Setup GitHub Deploy Key (For Automatic Deployments)

1. **Generate SSH key on VPS**:
```bash
ssh-keygen -t ed25519 -C "unified-odds-deploy" -f ~/.ssh/unified_odds_deploy
```

2. **Display the public key**:
```bash
cat ~/.ssh/unified_odds_deploy.pub
```

3. **Add deploy key to GitHub**:
   - Go to your repository on GitHub
   - Click **Settings** → **Deploy keys** → **Add deploy key**
   - Title: `VPS Deploy Key`
   - Paste the public key
   - ✅ Check "Allow write access" (if you want the VPS to push)
   - Click **Add key**

4. **Configure SSH on VPS**:
```bash
nano ~/.ssh/config
```

Add this configuration:
```
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/unified_odds_deploy
    IdentitiesOnly yes
```

Save and set permissions:
```bash
chmod 600 ~/.ssh/config
```

5. **Test SSH connection**:
```bash
ssh -T git@github.com
# Should see: "Hi YOUR_USERNAME! You've successfully authenticated..."
```

6. **Update git remote to use SSH**:
```bash
cd /home/ubuntu/services/unified-odds
git remote set-url origin git@github.com:YOUR_USERNAME/unified-odds-system.git
```

### Step 4: Setup GitHub Actions Secrets

1. **Generate or use existing VPS SSH private key**:
```bash
# On VPS, display your private key
cat ~/.ssh/id_ed25519
# Or cat ~/.ssh/id_rsa
```

2. **Add secrets to GitHub**:
   - Go to your repository on GitHub
   - Click **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:

| Secret Name | Value | Description |
|------------|-------|-------------|
| `VPS_HOST` | `142.44.160.36` | Your VPS IP address |
| `VPS_USERNAME` | `ubuntu` | VPS SSH username |
| `VPS_SSH_KEY` | `<private key>` | Paste the ENTIRE private key (including BEGIN/END lines) |
| `VPS_PORT` | `22` | SSH port (default 22) |

---

## 🔄 How Automatic Deployment Works

### When You Push Changes:

1. **Local Development**:
```powershell
# Make changes to your code
# Test locally

# Commit and push
git add .
git commit -m "Update: description of changes"
git push origin main
```

2. **GitHub Actions Triggers**:
   - GitHub detects push to `main` branch
   - Runs workflow in `.github/workflows/deploy.yml`
   - Connects to VPS via SSH

3. **VPS Deployment**:
   - Pulls latest code: `git pull origin main`
   - Activates virtual environment
   - Installs/updates dependencies: `pip install -r requirements.txt`
   - Restarts service: `sudo systemctl restart unified-odds`
   - Verifies service is running

4. **You Get Notified**:
   - Check GitHub Actions tab for deployment status
   - Green ✅ = Success
   - Red ❌ = Failed (check logs)

---

## 📊 Managing the Service on VPS

### Check Status
```bash
sudo systemctl status unified-odds
```

### View Logs
```bash
# Real-time logs
sudo journalctl -u unified-odds -f

# Last 50 lines
sudo journalctl -u unified-odds -n 50

# Logs from today
sudo journalctl -u unified-odds --since today
```

### Manual Restart
```bash
sudo systemctl restart unified-odds
```

### Stop/Start
```bash
sudo systemctl stop unified-odds
sudo systemctl start unified-odds
```

### Disable Auto-start
```bash
sudo systemctl disable unified-odds
```

### Enable Auto-start
```bash
sudo systemctl enable unified-odds
```

---

## 🔧 Manual Updates (Without GitHub Actions)

If you want to update manually:

```bash
# SSH into VPS
ssh ubuntu@142.44.160.36

# Use the quick update script
cd /home/ubuntu/services/unified-odds
./update_from_github.sh
```

Or manually:
```bash
cd /home/ubuntu/services/unified-odds
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart unified-odds
```

---

## 🌐 Chrome on Ubuntu (Virtual Display)

### How It Works:
- The system uses `xvfb-run` (X virtual framebuffer) to run Chrome on Ubuntu without a physical display
- `chrome_helper.py` automatically detects the platform (Windows/Linux) and uses the appropriate Chrome installation
- On Ubuntu: Uses `/usr/bin/google-chrome-stable`
- On Windows: Uses `C:\Program Files\Google\Chrome\Application\chrome.exe`

### Key Differences from Windows:

| Feature | Windows | Ubuntu (VPS) |
|---------|---------|--------------|
| Chrome Path | `C:\Program Files\...` | `/usr/bin/google-chrome` |
| Display | Physical monitor | Virtual (xvfb) |
| Launch | Direct | Via `xvfb-run -a` |
| Headless | Optional | Avoided (Cloudflare detection) |

### Testing Chrome on VPS:
```bash
# Test Chrome installation
google-chrome --version

# Test with xvfb
xvfb-run -a google-chrome --version

# Test Chrome can open
xvfb-run -a google-chrome --headless --dump-dom https://www.google.com
```

---

## 📁 Project Structure on VPS

```
/home/ubuntu/services/unified-odds/
├── .git/                          # Git repository
├── .github/workflows/             # GitHub Actions
│   └── deploy.yml
├── venv/                          # Python virtual environment
├── bet365/                        # Bet365 scrapers
├── fanduel/                       # FanDuel scrapers
├── 1xbet/                         # 1xBet scrapers
├── chrome_helper.py               # Cross-platform Chrome helper
├── launch_odds_system.py          # Main runner
├── unified_odds_collector.py      # Data merger
├── config.json                    # Configuration (email, etc.)
├── requirements.txt               # Python dependencies
├── unified-odds.service           # Systemd service file
├── deploy_unified_odds.sh         # Deployment script
└── update_from_github.sh          # Quick update script
```

---

## 🐛 Troubleshooting

### Deployment Failed on GitHub Actions

**Check the Actions tab:**
- Go to your repository → Actions tab
- Click on the failed workflow
- Expand the failed step to see error details

**Common issues:**

1. **SSH connection failed**:
   - Verify `VPS_HOST`, `VPS_USERNAME`, `VPS_PORT` secrets
   - Check if VPS is accessible: `ping 142.44.160.36`
   - Test SSH manually: `ssh ubuntu@142.44.160.36`

2. **Permission denied (publickey)**:
   - Verify `VPS_SSH_KEY` secret contains the complete private key
   - Ensure the key includes `-----BEGIN ... PRIVATE KEY-----` and `-----END ... PRIVATE KEY-----`

3. **Git pull failed**:
   - Check if deploy key is added to GitHub
   - Verify SSH config on VPS
   - Test: `ssh -T git@github.com` on VPS

### Service Not Starting

```bash
# Check detailed status
sudo systemctl status unified-odds

# Check logs
sudo journalctl -u unified-odds -n 100

# Common issues:
# 1. Python dependencies missing
source /home/ubuntu/services/unified-odds/venv/bin/activate
pip install -r /home/ubuntu/services/unified-odds/requirements.txt

# 2. Chrome not installed
google-chrome --version
# If not found:
sudo apt install google-chrome-stable

# 3. Permission issues
sudo chown -R ubuntu:ubuntu /home/ubuntu/services/unified-odds

# 4. Config.json issues
nano /home/ubuntu/services/unified-odds/config.json
# Verify email settings, no syntax errors
```

### Chrome Issues

```bash
# Chrome not found
which google-chrome
# Should return: /usr/bin/google-chrome

# Test Chrome with xvfb
xvfb-run -a google-chrome --version

# Check display
echo $DISPLAY
# Should show something like :99 when running via xvfb

# Install missing dependencies
sudo apt install -y xvfb google-chrome-stable
```

### High Memory Usage

```bash
# Check memory
free -h

# Check service memory
systemctl status unified-odds

# Adjust memory limit in service file
sudo nano /etc/systemd/system/unified-odds.service
# Change: MemoryMax=2G to MemoryMax=3G
sudo systemctl daemon-reload
sudo systemctl restart unified-odds
```

### Data Not Updating

```bash
# Check if scrapers are running
ps aux | grep python

# Check Chrome processes
ps aux | grep chrome

# Check logs for errors
sudo journalctl -u unified-odds -f

# Manually test a scraper
cd /home/ubuntu/services/unified-odds
source venv/bin/activate
python bet365/bet365_pregame_scraper.py
```

---

## 🔐 Security Best Practices

### 1. Protect Sensitive Data
- ❌ **Never commit** `config.json` with real credentials to GitHub
- ✅ Use `config.json.template` as a reference
- ✅ Configure `config.json` directly on VPS after deployment

### 2. SSH Keys
- ✅ Use separate deploy keys for each project
- ✅ Limit deploy key permissions (read-only if possible)
- ✅ Never share private keys

### 3. GitHub Secrets
- ✅ Use GitHub Secrets for all sensitive data
- ✅ Rotate SSH keys periodically
- ✅ Use strong passwords for VPS

### 4. VPS Security
```bash
# Setup firewall
sudo ufw enable
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (if needed)
sudo ufw allow 443/tcp   # HTTPS (if needed)

# Regular updates
sudo apt update && sudo apt upgrade -y
```

---

## 📈 Monitoring

### Check System Resources
```bash
# CPU and memory
htop

# Disk usage
df -h

# Check service resource usage
systemctl status unified-odds
```

### Monitor Data Files
```bash
# Check if data is being collected
ls -lh /home/ubuntu/services/unified-odds/*.json

# Watch unified odds file update in real-time
watch -n 5 'ls -lh /home/ubuntu/services/unified-odds/unified_odds.json'

# View data
cat /home/ubuntu/services/unified-odds/unified_odds.json | jq '.metadata'
```

### Setup Alerts (Optional)
The system includes email alerting. Configure in `config.json`:
```json
{
  "email": {
    "enabled": true,
    "sender_email": "your-email@gmail.com",
    "sender_password": "app-password",
    "admin_email": "admin@example.com"
  }
}
```

---

## 🎯 Quick Reference

### Local Development → VPS

```powershell
# On Windows (local development)
cd "C:\Users\User\Desktop\thesis\work related task\vps deploy\combine 1xbet, fanduel and bet365 (main)"

# Make changes, test locally

# Commit and push
git add .
git commit -m "Your change description"
git push origin main

# GitHub Actions automatically deploys to VPS!
# Check: https://github.com/YOUR_USERNAME/unified-odds-system/actions
```

### Common VPS Commands

```bash
# Quick status check
sudo systemctl status unified-odds

# View live logs
sudo journalctl -u unified-odds -f

# Restart service
sudo systemctl restart unified-odds

# Quick update
cd /home/ubuntu/services/unified-odds && ./update_from_github.sh

# Check Chrome
google-chrome --version

# View data
tail -f /home/ubuntu/services/unified-odds/unified_odds.json
```

---

## ✅ Verification Checklist

After setup, verify everything works:

- [ ] VPS accessible via SSH
- [ ] Chrome installed (`google-chrome --version`)
- [ ] Repository cloned to `/home/ubuntu/services/unified-odds`
- [ ] Virtual environment created (`venv/` folder exists)
- [ ] Dependencies installed (`pip list | grep patchright`)
- [ ] Service file installed (`/etc/systemd/system/unified-odds.service`)
- [ ] Service running (`sudo systemctl status unified-odds`)
- [ ] Deploy key added to GitHub
- [ ] GitHub Actions secrets configured
- [ ] Test push triggers deployment
- [ ] Data files being generated (`unified_odds.json` updating)
- [ ] Logs show no errors (`sudo journalctl -u unified-odds -n 50`)

---

## 📞 Support

### Useful Resources
- GitHub Actions Docs: https://docs.github.com/en/actions
- Ubuntu Chrome: https://www.google.com/chrome/
- Systemd: https://www.freedesktop.org/software/systemd/man/systemd.service.html
- xvfb: https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml

### Common Commands Reference

| Task | Command |
|------|---------|
| Check service | `sudo systemctl status unified-odds` |
| View logs | `sudo journalctl -u unified-odds -f` |
| Restart | `sudo systemctl restart unified-odds` |
| Update code | `cd ~/services/unified-odds && ./update_from_github.sh` |
| Test Chrome | `xvfb-run -a google-chrome --version` |
| Check memory | `free -h` |
| Check disk | `df -h` |

---

## 🎉 Success!

Once everything is set up:
- ✅ Your code is version-controlled on GitHub
- ✅ Changes automatically deploy to VPS
- ✅ Service auto-restarts on crash
- ✅ Chrome runs on Ubuntu via xvfb
- ✅ Data is collected 24/7
- ✅ You can push changes from anywhere!

**Just commit and push - the VPS handles the rest!** 🚀

# ✅ Auto-Deployment Setup Complete & Working!

## Current Status

🎉 **AUTO-DEPLOYMENT IS LIVE AND WORKING!**

- ✅ GitHub Actions configured and tested
- ✅ Both services auto-restart on every push
- ✅ Deployment completes in ~5-10 seconds
- ✅ No manual intervention needed

## Quick Reference

### Deploy Changes (3 Steps)

```bash
# 1. Make changes to your code
vim unified_odds_collector.py

# 2. Commit and push
git add .
git commit -m "Your change description"
git push origin main

# 3. Done! Watch it deploy
```

View deployment: **https://github.com/joypciu/unified-odds-system/actions**

### Access Your System

- **Web UI**: http://142.44.160.36:8000
- **VPS SSH**: `ssh ubuntu@142.44.160.36`
- **Service Status**: `sudo systemctl status unified-odds unified-odds-ui`
- **Logs**: `sudo journalctl -u unified-odds -f`

---

## What Was Configured

### 1. SSH Authentication
- Generated ed25519 key pair on VPS
- Private key added to GitHub Secrets as `VPS_SSH_KEY`
- Public key added to VPS `~/.ssh/authorized_keys`

### 2. Passwordless Sudo
Created `/etc/sudoers.d/github-actions`:
```
ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl
ubuntu ALL=(ALL) NOPASSWD: /usr/bin/pkill
ubuntu ALL=(ALL) NOPASSWD: /bin/fuser
```

### 3. GitHub Secrets
Repository: https://github.com/joypciu/unified-odds-system

Secrets configured:
- `VPS_HOST` = 142.44.160.36
- `VPS_USERNAME` = ubuntu
- `VPS_PORT` = 22
- `VPS_SSH_KEY` = (ed25519 private key)

### 4. Deployment Workflows

**Auto-deploy on push** (`.github/workflows/deploy.yml`):
```yaml
- Triggers on push to main branch
- Pulls latest code
- Kills port 8000 processes
- Restarts both services with --no-block
- Completes in ~10 seconds
```

**Manual deploy with deps** (`.github/workflows/deploy-with-deps.yml`):
```yaml
- Manual trigger only
- Includes pip install -r requirements.txt
- Use when you update dependencies
- Takes ~2 minutes
```

---

## How It Works

### Deployment Flow

1. **You push code** to GitHub main branch
2. **GitHub Actions triggers** deploy.yml workflow
3. **SSH connects** to VPS using ed25519 key
4. **Pulls latest code**: `git reset --hard origin/main`
5. **Kills port conflicts**: `sudo fuser -k 8000/tcp`
6. **Restarts services**: `sudo systemctl restart --no-block`
7. **Services start** in background (~2-3 seconds)
8. **Deployment completes** ✅

### Services Running

- **unified-odds** (Data Collector)
  - Location: `/home/ubuntu/services/unified-odds`
  - Service: `/etc/systemd/system/unified-odds.service`
  - Command: `xvfb-run -a python launch_odds_system.py`
  - Auto-restart: Yes (on-failure)

- **unified-odds-ui** (Web Interface)
  - Location: `/home/ubuntu/services/unified-odds`
  - Service: `/etc/systemd/system/unified-odds-ui.service`
  - Command: `python live_odds_viewer_clean.py`
  - Port: 8000
  - Auto-restart: Yes (on-failure)

---

## Troubleshooting

### Deployment Issues

**GitHub Actions shows error:**
```bash
# Check the Actions tab for detailed logs
# Common issues:
# - SSH key mismatch (re-add VPS_SSH_KEY secret)
# - Port 8000 in use (manually kill: sudo fuser -k 8000/tcp)
# - Service crash (check logs: sudo journalctl -u unified-odds-ui -n 50)
```

**Services not running after deployment:**
```bash
# SSH to VPS
ssh ubuntu@142.44.160.36

# Check service status
sudo systemctl status unified-odds unified-odds-ui

# View recent logs
sudo journalctl -u unified-odds -n 50
sudo journalctl -u unified-odds-ui -n 50

# Restart manually if needed
sudo fuser -k 8000/tcp
sudo systemctl restart unified-odds unified-odds-ui
```

**Need to update dependencies:**
```bash
# Go to GitHub Actions page
# Run "Deploy to VPS (with dependencies update)" workflow manually
# This includes pip install -r requirements.txt
```

### Common Fixes

**Port 8000 conflict:**
```bash
sudo fuser -k 8000/tcp
sudo systemctl restart unified-odds-ui
```

**Service crashed:**
```bash
sudo systemctl restart unified-odds
sudo systemctl restart unified-odds-ui
```

**Git pull conflicts:**
```bash
cd /home/ubuntu/services/unified-odds
git reset --hard origin/main
git clean -fd
```

---

## Files Reference

### On VPS
- `/home/ubuntu/services/unified-odds/` - Project directory
- `/home/ubuntu/services/unified-odds/venv/` - Python virtual environment
- `/home/ubuntu/.ssh/github_deploy` - Private key (used by GitHub Actions)
- `/home/ubuntu/.ssh/github_deploy.pub` - Public key
- `/etc/systemd/system/unified-odds.service` - Main service
- `/etc/systemd/system/unified-odds-ui.service` - UI service
- `/etc/sudoers.d/github-actions` - Passwordless sudo rules

### In Repository
- `.github/workflows/deploy.yml` - Auto-deployment (on push)
- `.github/workflows/deploy-with-deps.yml` - Manual deployment with pip install
- `VPS_GITHUB_DEPLOY_KEY.txt` - Backup of SSH private key (local only)

---

## What's Next?

Your deployment pipeline is fully operational! Just code and push:

```bash
# Example workflow
git checkout -b feature/new-scraper
# ... make changes ...
git add .
git commit -m "Added new scraper"
git push origin feature/new-scraper
# ... create PR, merge to main ...
# → Automatically deploys to VPS!
```

---

## Need Help?

- **View logs**: `ssh ubuntu@142.44.160.36 "sudo journalctl -u unified-odds -f"`
- **Check status**: `ssh ubuntu@142.44.160.36 "sudo systemctl status unified-odds unified-odds-ui"`
- **Restart services**: `ssh ubuntu@142.44.160.36 "sudo systemctl restart unified-odds unified-odds-ui"`
- **Watch deployment**: https://github.com/joypciu/unified-odds-system/actions

### View VPS Services Status
```bash
ssh ubuntu@142.44.160.36
sudo systemctl status unified-odds unified-odds-ui
```

### View Recent Logs
```bash
sudo journalctl -u unified-odds -n 20
sudo journalctl -u unified-odds-ui -n 20
```

### Manual Restart (if needed)
```bash
sudo pkill -9 -f 'live_odds_viewer_clean.py'
sudo systemctl restart unified-odds unified-odds-ui
```

---

**Status**: ✅ Ready! Just add the GitHub Secrets and push your first change to test it!

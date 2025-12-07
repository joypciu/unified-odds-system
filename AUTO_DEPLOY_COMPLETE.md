# ✅ Auto-Deployment Setup Complete!

## What Was Done

1. ✅ **SSH Key Generated** on VPS for GitHub Actions
2. ✅ **SSH Key Added** to VPS authorized_keys
3. ✅ **Deploy Workflow Updated** (`.github/workflows/deploy.yml`)
   - Now pulls from `eternity` remote (Eternity-Labs-BD)
   - Kills port 8000 processes before UI restart
   - Properly handles both services

## Quick Setup (3 Steps)

### Step 1: Add GitHub Secrets

Go to: **https://github.com/Eternity-Labs-BD/unified-odds-system/settings/secrets/actions**

Click "New repository secret" and add these 4 secrets:

1. **VPS_HOST** = `142.44.160.36`
2. **VPS_USERNAME** = `ubuntu`  
3. **VPS_PORT** = `22`
4. **VPS_SSH_KEY** = Copy from `VPS_GITHUB_DEPLOY_KEY.txt` file (entire key including BEGIN/END lines)

### Step 2: Test Deployment

```bash
# Make a small change
echo "# Test auto-deploy" >> README.md

# Commit and push
git add .
git commit -m "Test: Auto-deployment setup"
git push origin main
```

### Step 3: Watch It Deploy

Go to: **https://github.com/Eternity-Labs-BD/unified-odds-system/actions**

You'll see the deployment running in real-time!

---

## How It Works Now

### When You Push to GitHub:
1. **GitHub Actions** triggers automatically
2. **Connects** to your VPS via SSH
3. **Pulls** latest code from `eternity/main` branch
4. **Installs** any new dependencies
5. **Restarts** both services:
   - `unified-odds` (data collector)
   - `unified-odds-ui` (web interface on port 8000)
6. **Verifies** everything is running

### Services Restarted:
- ✅ `unified-odds` - Always restarts
- ✅ `unified-odds-ui` - Kills port 8000 blockers, then restarts

---

## Files You Have

1. **`VPS_GITHUB_DEPLOY_KEY.txt`** - Private SSH key (add to GitHub Secrets)
2. **`.github/workflows/deploy.yml`** - Deployment workflow (already configured)
3. **`GITHUB_ACTIONS_SETUP.md`** - Detailed guide (existing, more info)

---

## What to Do Now

1. ✅ **Add the 4 GitHub Secrets** (see Step 1 above)
2. ✅ **Push a test change** to verify auto-deployment works
3. ✅ **Check GitHub Actions tab** to see deployment progress
4. ✅ Start coding! Every push to `main` will auto-deploy 🚀

---

## Quick Commands

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

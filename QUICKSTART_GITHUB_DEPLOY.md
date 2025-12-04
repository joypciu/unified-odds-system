# 🚀 Quick Start - GitHub-Based VPS Deployment

This is a **quick start guide** for deploying the Unified Odds System to VPS with automatic GitHub integration.

For the **complete detailed guide**, see: [GITHUB_DEPLOYMENT_GUIDE.md](./GITHUB_DEPLOYMENT_GUIDE.md)

---

## ✅ What You Get

- 🔄 **Automatic deployment** when you push to GitHub
- 🖥️ **Cross-platform Chrome support** (Windows local, Ubuntu VPS)
- 🔁 **Auto-restart** on crash via systemd
- 📊 **24/7 data collection** from Bet365, FanDuel, 1xBet
- 📧 **Email alerts** for system issues
- 🌐 **Virtual display** (xvfb) for Chrome on Ubuntu

---

## 🏃 Quick Setup (3 Steps)

### 1️⃣ Push to GitHub (5 minutes)

```powershell
# In your project folder
cd "C:\Users\User\Desktop\thesis\work related task\vps deploy\combine 1xbet, fanduel and bet365 (main)"

# Initialize and push
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/unified-odds-system.git
git branch -M main
git push -u origin main
```

### 2️⃣ Deploy to VPS (10 minutes)

```bash
# SSH into VPS
ssh ubuntu@142.44.160.36

# Upload and run deployment script (or create it on VPS)
chmod +x deploy_unified_odds.sh
./deploy_unified_odds.sh

# Configure your email settings
cd /home/ubuntu/services/unified-odds
nano config.json
# Update email credentials, then save

# Restart service
sudo systemctl restart unified-odds
```

### 3️⃣ Setup GitHub Actions (5 minutes)

**Add these secrets** to your GitHub repository:
- Go to: `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

| Secret Name | Value |
|------------|-------|
| `VPS_HOST` | `142.44.160.36` |
| `VPS_USERNAME` | `ubuntu` |
| `VPS_SSH_KEY` | Your SSH private key (entire key) |
| `VPS_PORT` | `22` |

**Done!** Now every push to `main` auto-deploys to VPS.

---

## 🔄 Daily Usage

### Make Changes & Deploy

```powershell
# Make your changes locally
# Test them

# Commit and push (this auto-deploys!)
git add .
git commit -m "Your changes"
git push origin main

# Check GitHub Actions tab to see deployment progress
```

### Check VPS Status

```bash
# SSH into VPS
ssh ubuntu@142.44.160.36

# Check service status
sudo systemctl status unified-odds

# View live logs
sudo journalctl -u unified-odds -f

# Restart if needed
sudo systemctl restart unified-odds
```

---

## 📂 Files Created

Here's what was added to your project:

```
📁 Project Root
├── .github/workflows/
│   └── deploy.yml                    # ✨ GitHub Actions workflow
├── chrome_helper.py                   # ✨ Cross-platform Chrome support
├── unified-odds.service               # ✨ Systemd service file
├── deploy_unified_odds.sh             # ✨ VPS deployment script
├── update_scrapers_for_ubuntu.py      # ✨ Scraper update tool
├── GITHUB_DEPLOYMENT_GUIDE.md         # ✨ Complete documentation
└── .gitignore                         # ✅ Updated (excludes sensitive data)
```

### What Each File Does:

| File | Purpose |
|------|---------|
| **deploy.yml** | GitHub Actions workflow - auto-deploys on push |
| **chrome_helper.py** | Detects OS and uses correct Chrome path |
| **unified-odds.service** | Systemd service for auto-restart and management |
| **deploy_unified_odds.sh** | One-click VPS setup script |
| **update_scrapers_for_ubuntu.py** | Helps update scrapers to use chrome_helper |
| **.gitignore** | Prevents committing sensitive data & logs |

---

## ⚙️ How Chrome Works on VPS

### Local (Windows)
```
Your Scrapers → Chrome at C:\Program Files\Google\Chrome\... → Physical Display
```

### VPS (Ubuntu)
```
Your Scrapers → chrome_helper.py → Ubuntu Chrome at /usr/bin/google-chrome → xvfb (virtual display)
```

**Key Points:**
- ✅ **chrome_helper.py** automatically detects Windows vs Ubuntu
- ✅ On Ubuntu, uses `/usr/bin/google-chrome-stable`
- ✅ Runs via `xvfb-run` (virtual display, no monitor needed)
- ✅ **No code changes needed** - same Python scripts work on both!

---

## 🔍 Verify Everything Works

### After Initial Deployment:

```bash
# Check service is running
sudo systemctl status unified-odds
# Should show: ● unified-odds.service - Unified Odds Collection System
#              Active: active (running)

# Check Chrome is installed
google-chrome --version
# Should show: Google Chrome 1xx.x.xxxx.xxx

# Check data is being collected
ls -lh /home/ubuntu/services/unified-odds/*.json
# Should see: unified_odds.json with recent timestamp

# Watch logs
sudo journalctl -u unified-odds -f
# Should see scraper activity, no major errors
```

### After Pushing Changes:

1. Go to: `https://github.com/YOUR_USERNAME/unified-odds-system/actions`
2. You should see your latest commit being deployed
3. Green ✅ = Success, Red ❌ = Check logs

---

## 🐛 Quick Troubleshooting

### Service Not Running?
```bash
# Check what went wrong
sudo journalctl -u unified-odds -n 50

# Common fix: restart
sudo systemctl restart unified-odds
```

### GitHub Actions Failed?
- Check the `Actions` tab for error details
- Verify your GitHub secrets are correct
- Make sure SSH key includes the full key (including BEGIN/END lines)

### Chrome Issues?
```bash
# Test Chrome
google-chrome --version

# Test with xvfb
xvfb-run -a google-chrome --version

# Reinstall if needed
sudo apt install -y google-chrome-stable xvfb
```

### Need to Update config.json?
```bash
# Edit config on VPS
cd /home/ubuntu/services/unified-odds
nano config.json
# Make changes, save

# Restart service
sudo systemctl restart unified-odds
```

---

## 🎯 Next Steps

### 1. Check Scraper Compatibility
```powershell
# Run the analysis tool
python update_scrapers_for_ubuntu.py
```

This will show you which scrapers (if any) need updating to use `chrome_helper.py`.

### 2. Setup GitHub Deploy Key (Optional, for git pull from VPS)
```bash
# On VPS
ssh-keygen -t ed25519 -f ~/.ssh/unified_odds_deploy
cat ~/.ssh/unified_odds_deploy.pub
# Add this public key to GitHub: Settings → Deploy keys
```

### 3. Monitor Your System
```bash
# View data being collected
tail -f /home/ubuntu/services/unified-odds/unified_odds.json

# Check memory usage
free -h

# Check process status
htop
```

---

## 📚 Documentation

- **This file**: Quick start guide (you are here)
- **[GITHUB_DEPLOYMENT_GUIDE.md](./GITHUB_DEPLOYMENT_GUIDE.md)**: Complete detailed guide
- **[README.md](./README.md)**: Project overview and features
- **[EMAIL_SETUP_GUIDE.md](./EMAIL_SETUP_GUIDE.md)**: Email alert configuration

---

## 🎉 Success Checklist

After setup, you should have:

- ✅ Code pushed to GitHub
- ✅ VPS running the unified-odds service
- ✅ GitHub Actions configured with secrets
- ✅ Service auto-starts on VPS reboot
- ✅ Chrome working via xvfb on Ubuntu
- ✅ Data files being generated (unified_odds.json)
- ✅ Can push to GitHub and changes auto-deploy
- ✅ Email alerts configured (optional)

---

## 💡 Pro Tips

### Quick Update from VPS
```bash
cd /home/ubuntu/services/unified-odds
./update_from_github.sh
```

### View Recent Changes
```bash
cd /home/ubuntu/services/unified-odds
git log --oneline -10
```

### Check Resource Usage
```bash
# Memory
free -h

# Disk
df -h

# Service resource usage
systemctl status unified-odds
```

### Manual Test a Scraper
```bash
cd /home/ubuntu/services/unified-odds
source venv/bin/activate
xvfb-run -a python bet365/bet365_pregame_scraper.py
```

---

## 🆘 Need Help?

1. **Check the logs**: `sudo journalctl -u unified-odds -f`
2. **Read the full guide**: [GITHUB_DEPLOYMENT_GUIDE.md](./GITHUB_DEPLOYMENT_GUIDE.md)
3. **Test components individually**: Chrome, xvfb, Python scrapers
4. **Verify GitHub Actions**: Check the Actions tab for deployment logs

---

## 🚀 Ready to Deploy?

You're all set! Just follow the 3-step quick setup above and you'll have automatic VPS deployment in ~20 minutes.

**Remember**: Every time you push to `main`, GitHub Actions automatically deploys to your VPS! 🎉

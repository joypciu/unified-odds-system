# 🤖 Automated Deployment Guide - Zero Manual Configuration

This guide uses the **fully automated** deployment script that handles SSH key generation, GitHub setup, and everything else.

---

## ⚡ Quick Start (2 Steps Only!)

### Step 1: Upload and Run Script (5 minutes)

**On your Windows machine**, upload the script via WinSCP:
1. Connect to `142.44.160.36` with user `ubuntu`
2. Upload `deploy_unified_odds_auto.sh` to `/home/ubuntu/`

**Or create it directly on VPS**:
```bash
ssh ubuntu@142.44.160.36

# Create the script
nano ~/deploy_unified_odds_auto.sh
# Paste the entire content from deploy_unified_odds_auto.sh
# Press Ctrl+X, then Y, then Enter to save

# Make it executable
chmod +x ~/deploy_unified_odds_auto.sh

# Run it
./deploy_unified_odds_auto.sh
```

### Step 2: Add SSH Key to GitHub (2 minutes)

The script will:
1. ✅ Install all dependencies
2. ✅ Generate SSH key automatically
3. ✅ Display the public key
4. ⏸️ **Pause and wait for you to add it to GitHub**

When the script pauses, it will show something like:
```
========================================
📋 IMPORTANT: Add this SSH key to GitHub
========================================

ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIK... ubuntu@vps-unified-odds

👉 Follow these steps:
   1. Copy the SSH key above
   2. Go to: https://github.com/joypciu/unified-odds-system/settings/keys
   3. Click 'Add deploy key'
   4. Paste the key and give it a title: 'VPS Deploy Key'
   5. ✅ Check 'Allow write access' (optional)
   6. Click 'Add key'

Press ENTER after you've added the key to GitHub...
```

**Do this:**
1. Copy the SSH key shown
2. Open: https://github.com/joypciu/unified-odds-system/settings/keys
3. Click **"Add deploy key"**
4. Paste the key
5. Title: `VPS Deploy Key`
6. Click **"Add key"**
7. Go back to your terminal and press ENTER

**Done!** The script continues and completes everything automatically.

---

## 🎯 What The Script Does Automatically

### ✅ System Setup
- Installs Python 3, pip, venv
- Installs Git
- Installs Google Chrome
- Installs xvfb (virtual display)

### ✅ SSH Configuration
- Generates SSH key (`~/.ssh/id_ed25519`)
- Configures SSH for GitHub
- Adds GitHub to known hosts
- Tests SSH connection

### ✅ Repository
- Clones from GitHub using SSH
- Sets up git configuration
- Creates all necessary directories

### ✅ Python Environment
- Creates virtual environment
- Installs all dependencies
- Installs Playwright browsers

### ✅ Service Setup
- Installs systemd service
- Configures log rotation
- Enables auto-start
- Starts the service

### ✅ Helper Scripts
- Creates update script (`update_from_github.sh`)
- Sets up config.json (from template if needed)

---

## 📋 After Script Completes

### Configure Email (Optional but Recommended)
```bash
cd /home/ubuntu/services/unified-odds
nano config.json
```

Update these fields:
```json
{
  "email": {
    "sender_email": "ujoywork@gmail.com",
    "sender_password": "lywz budt zbyr dsny",
    "admin_email": "usmanjoycse@gmail.com",
    "enabled": true
  }
}
```

Then restart:
```bash
sudo systemctl restart unified-odds
```

### Setup GitHub Actions (For Auto-Deployment)

The script will show you how to do this at the end. You need to:

1. **Get your SSH private key**:
```bash
cat ~/.ssh/id_ed25519
```

2. **Add GitHub Secrets**:
   - Go to: https://github.com/joypciu/unified-odds-system/settings/secrets/actions
   - Click **"New repository secret"**
   - Add these 4 secrets:

| Secret Name | Value |
|------------|-------|
| `VPS_HOST` | `142.44.160.36` |
| `VPS_USERNAME` | `ubuntu` |
| `VPS_SSH_KEY` | Paste entire private key (from `cat ~/.ssh/id_ed25519`) |
| `VPS_PORT` | `22` |

3. **Test Auto-Deployment**:
```powershell
# On Windows
cd "C:\Users\User\Desktop\thesis\work related task\vps deploy\combine 1xbet, fanduel and bet365 (main)"
echo "# Test" >> README.md
git add .
git commit -m "Test: Auto-deployment"
git push origin main

# Check GitHub Actions tab for deployment status
```

---

## 🔍 Verify Everything Works

```bash
# Check service status
sudo systemctl status unified-odds

# View logs
sudo journalctl -u unified-odds -f

# Check Chrome
google-chrome --version

# Test Chrome with xvfb
xvfb-run -a google-chrome --version

# Check data files
ls -lh /home/ubuntu/services/unified-odds/*.json
```

---

## 🛠️ Service Management

```bash
# Status
sudo systemctl status unified-odds

# Logs (live)
sudo journalctl -u unified-odds -f

# Restart
sudo systemctl restart unified-odds

# Stop
sudo systemctl stop unified-odds

# Start
sudo systemctl start unified-odds

# Quick update from GitHub
cd /home/ubuntu/services/unified-odds
./update_from_github.sh
```

---

## 🐛 Troubleshooting

### Script Fails at SSH Key Addition

If you see "GitHub SSH connection failed":
1. Make sure you copied the ENTIRE SSH key
2. Check you added it here: https://github.com/joypciu/unified-odds-system/settings/keys
3. Click "Add deploy key", paste key, save
4. Run script again: `./deploy_unified_odds_auto.sh`

### Service Not Starting

```bash
# Check what's wrong
sudo journalctl -u unified-odds -n 50

# Usually it's config.json
nano /home/ubuntu/services/unified-odds/config.json
# Fix any issues

# Restart
sudo systemctl restart unified-odds
```

### Chrome Issues

```bash
# Reinstall Chrome
sudo apt remove google-chrome-stable
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f -y

# Restart service
sudo systemctl restart unified-odds
```

---

## 📊 What's Different from Manual Setup?

| Feature | Manual Script | Auto Script |
|---------|--------------|-------------|
| SSH key generation | ❌ Manual | ✅ Automatic |
| GitHub SSH config | ❌ Manual | ✅ Automatic |
| Prompts for key addition | ❌ No | ✅ Yes (with pause) |
| Tests SSH connection | ❌ No | ✅ Yes |
| Error handling | Basic | Comprehensive |
| User guidance | Minimal | Detailed |

---

## ✅ Complete Checklist

After running the auto script:

- [ ] Script completed without errors
- [ ] SSH key added to GitHub
- [ ] Service is running (`sudo systemctl status unified-odds`)
- [ ] Chrome installed (`google-chrome --version`)
- [ ] Config.json edited (email settings)
- [ ] GitHub Actions secrets configured (optional)
- [ ] Data files being generated (`ls -lh *.json`)

---

## 🎉 Success!

The automated script handles:
- ✅ All system dependencies
- ✅ SSH key generation and setup
- ✅ GitHub repository cloning
- ✅ Python environment
- ✅ Service configuration
- ✅ Everything except adding SSH key to GitHub (you do that once)

**Total time**: ~10 minutes including SSH key addition!

---

## 💡 Pro Tips

### Re-run If Needed
The script is **idempotent** - you can run it multiple times safely:
```bash
./deploy_unified_odds_auto.sh
```

### Update After Changes
```bash
cd /home/ubuntu/services/unified-odds
./update_from_github.sh
```

### Monitor in Real-Time
```bash
# Terminal 1: Watch logs
sudo journalctl -u unified-odds -f

# Terminal 2: Watch data
watch -n 5 'ls -lh /home/ubuntu/services/unified-odds/*.json'
```

---

**That's it!** This automated script does everything for you. Just run it and add the SSH key to GitHub when prompted! 🚀

# GitHub Actions Setup Guide for Beginners

This guide will help you set up automatic deployment from GitHub to your VPS server. Once configured, every time you push code to GitHub, it will automatically deploy to your VPS!

---

## 📋 What You'll Need

- ✅ A GitHub account
- ✅ Your code in a GitHub repository
- ✅ A VPS server with SSH access
- ✅ 10 minutes of your time

---

## 🚀 Step-by-Step Setup

### Step 1: Push Your Code to GitHub

If you haven't already, create a GitHub repository and push your code:

```bash
# Navigate to your project folder
cd "path/to/your/project"

# Initialize git (if not done)
git init

# Add all files
git add .

# Make first commit
git commit -m "Initial commit"

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/unified-odds-system.git

# Push to GitHub
git branch -M main
git push -u origin main
```

---

### Step 2: Generate SSH Key on Your VPS

SSH into your VPS and create an SSH key pair:

```bash
# Connect to VPS
ssh ubuntu@your-vps-ip

# Check if key already exists
ls ~/.ssh/id_ed25519

# If it doesn't exist, create one:
ssh-keygen -t ed25519 -C "vps-deployment" -f ~/.ssh/id_ed25519

# When prompted for passphrase, press ENTER (no passphrase)
```

---

### Step 3: Add Public Key to authorized_keys

**⚠️ CRITICAL STEP - Don't skip this!**

This is the most common mistake. The public key MUST be in `authorized_keys`:

```bash
# Still on your VPS, run these commands:

# Display your public key
cat ~/.ssh/id_ed25519.pub

# Add it to authorized_keys
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys

# Set correct permissions
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh

# Verify it's there
cat ~/.ssh/authorized_keys
# You should see your public key (starts with ssh-ed25519)
```

---

### Step 4: Copy Your SSH Private Key

Now get the private key (this goes to GitHub):

```bash
# Display the PRIVATE key
cat ~/.ssh/id_ed25519
```

You'll see something like:
```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtz...
(many more lines)
-----END OPENSSH PRIVATE KEY-----
```

**Copy ALL of this text** (including BEGIN and END lines). You'll need it in the next step.

---

### Step 5: Add Secrets to GitHub

1. **Go to your GitHub repository**
   
   Navigate to: `https://github.com/YOUR_USERNAME/unified-odds-system`

2. **Click on "Settings"** (top menu)

3. **In the left sidebar, click "Secrets and variables" → "Actions"**

4. **Click "New repository secret"** and add these 4 secrets one by one:

   **Secret 1: VPS_HOST**
   - Name: `VPS_HOST`
   - Value: Your VPS IP address (e.g., `142.44.160.36`)
   - Click "Add secret"

   **Secret 2: VPS_USERNAME**
   - Name: `VPS_USERNAME`
   - Value: Your SSH username (usually `ubuntu` or `root`)
   - Click "Add secret"

   **Secret 3: VPS_PORT**
   - Name: `VPS_PORT`
   - Value: `22` (unless you use a different SSH port)
   - Click "Add secret"

   **Secret 4: VPS_SSH_KEY**
   - Name: `VPS_SSH_KEY`
   - Value: Paste the ENTIRE private key you copied in Step 4
     - Must include `-----BEGIN OPENSSH PRIVATE KEY-----`
     - Must include `-----END OPENSSH PRIVATE KEY-----`
     - No extra spaces before or after
   - Click "Add secret"

---

### Step 6: Run the Deployment Script

Back on your VPS, run the automated deployment script:

```bash
# Download the script
cd ~
wget https://raw.githubusercontent.com/YOUR_USERNAME/unified-odds-system/main/deploy_unified_odds_auto.sh

# Make it executable
chmod +x deploy_unified_odds_auto.sh

# Run it
./deploy_unified_odds_auto.sh
```

Follow the on-screen instructions. The script will:
- ✅ Install Chrome, xvfb, Python, and all dependencies
- ✅ Clone your GitHub repository
- ✅ Set up Python virtual environment
- ✅ Install Python packages
- ✅ Create systemd service for automatic startup
- ✅ Start your odds collection system

---

### Step 7: Test Automatic Deployment

Now test if automatic deployment works:

1. **Make a small change to your code locally:**
   ```bash
   # On your local machine
   cd "path/to/your/project"
   echo "# Test deployment" >> README.md
   ```

2. **Commit and push:**
   ```bash
   git add README.md
   git commit -m "Test automatic deployment"
   git push origin main
   ```

3. **Watch the deployment happen:**
   - Go to: `https://github.com/YOUR_USERNAME/unified-odds-system/actions`
   - You should see a workflow running
   - Click on it to see the deployment progress
   - If successful, you'll see a green checkmark ✅

4. **Verify on VPS:**
   ```bash
   ssh ubuntu@your-vps-ip
   cd ~/services/unified-odds
   git log -n 1
   # Should show your latest commit
   ```

---

## ✅ Success! You're Done!

From now on, every time you push code to GitHub:
1. GitHub Actions will automatically trigger
2. Connect to your VPS via SSH
3. Pull the latest code
4. Install/update dependencies
5. Restart the service

You can monitor all deployments at: `https://github.com/YOUR_USERNAME/unified-odds-system/actions`

---

## 🐛 Troubleshooting

### ❌ Error: "ssh: unable to authenticate"

**Problem:** GitHub Actions can't connect to your VPS.

**Solution:**
1. Make sure you completed Step 3 (add public key to authorized_keys)
2. On VPS, verify: `cat ~/.ssh/authorized_keys` shows your public key
3. Check GitHub secret VPS_SSH_KEY contains the full private key

**Fix it:**
```bash
# On VPS
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

---

### ❌ Error: "Permission denied (publickey)"

**Problem:** SSH key format issue in GitHub secret.

**Solution:**
1. Go to GitHub → Settings → Secrets → Actions
2. Click "Update" on VPS_SSH_KEY
3. Re-paste the private key ensuring:
   - Includes `-----BEGIN OPENSSH PRIVATE KEY-----`
   - Includes `-----END OPENSSH PRIVATE KEY-----`
   - No extra spaces before/after
   - All lines intact

---

### ❌ Deployment doesn't trigger

**Problem:** GitHub Actions workflow not running.

**Solution:**
1. Check `.github/workflows/deploy.yml` exists in your repository
2. Make sure you're pushing to `main` branch (not `master`)
3. Verify the workflow file is valid YAML

---

### ❌ Service fails to start on VPS

**Problem:** The systemd service won't start.

**Solution:**
```bash
# Check service status
sudo systemctl status unified-odds

# View detailed logs
sudo journalctl -u unified-odds -n 50

# Common fixes:
# 1. Missing config.json
cd ~/services/unified-odds
cp config.json.template config.json
nano config.json  # Add your email settings

# 2. Missing Chrome
sudo apt install google-chrome-stable

# 3. Check Python dependencies
source venv/bin/activate
pip install -r requirements.txt
```

---

### ❌ Can't find SSH private key

**Problem:** No `~/.ssh/id_ed25519` file on VPS.

**Solution:**
```bash
# Generate a new SSH key
ssh-keygen -t ed25519 -C "vps-deployment" -f ~/.ssh/id_ed25519

# Don't set a passphrase (press ENTER when asked)

# Then follow Steps 3-5 again
```

---

## 📚 Additional Resources

- **Detailed Guide:** See `GITHUB_DEPLOYMENT_GUIDE.md` for complete documentation
- **Automated Script:** See `AUTOMATED_DEPLOYMENT_GUIDE.md` for script details
- **Quick Reference:** See `QUICKSTART_GITHUB_DEPLOY.md` for summary

---

## 🎯 Quick Reference Commands

**Check deployment on VPS:**
```bash
ssh ubuntu@your-vps-ip "cd ~/services/unified-odds && git log -n 3"
```

**View service logs:**
```bash
ssh ubuntu@your-vps-ip "sudo journalctl -u unified-odds -f"
```

**Restart service manually:**
```bash
ssh ubuntu@your-vps-ip "sudo systemctl restart unified-odds"
```

**Check service status:**
```bash
ssh ubuntu@your-vps-ip "sudo systemctl status unified-odds"
```

---

## 💡 Pro Tips

1. **Always test locally first** before pushing to production
2. **Monitor the Actions tab** after each push to catch deployment issues early
3. **Set up email alerts** in config.json to get notified of service failures
4. **Keep your SSH key secure** - never commit it to the repository
5. **Use branches** for development, only merge to `main` when ready to deploy

---

## 🆘 Still Having Issues?

1. Double-check you completed ALL steps in order
2. The most common issue is Step 3 (forgetting to add public key to authorized_keys)
3. Review the error logs on GitHub Actions page
4. Check VPS logs with `sudo journalctl -u unified-odds -n 100`

Happy deploying! 🚀

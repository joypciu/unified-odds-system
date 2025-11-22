# Email Setup Guide for Unified Odds System

This guide will help you configure email alerts for the Unified Odds System. The system uses Gmail SMTP with app passwords for secure email notifications.

## Prerequisites

- A Gmail account (Google account)
- 2-step verification enabled on your Google account
- Python installed and configured

## Step 1: Enable 2-Step Verification

1. **Go to Google Account Settings**
   - Open your web browser and go to [myaccount.google.com](https://myaccount.google.com)
   - Sign in with your Gmail account if not already signed in

2. **Navigate to Security**
   - Click on "Security" in the left sidebar
   - Scroll down to "Signing in to Google"

3. **Enable 2-Step Verification**
   - Click on "2-Step Verification"
   - Click "Get started"
   - Follow the prompts to set up 2-step verification
   - Choose your preferred second verification method (phone, authenticator app, etc.)
   - Complete the setup process

**Important**: Do not skip this step. App passwords require 2-step verification to be enabled first.

## Step 2: Generate App Password

1. **Return to Security Settings**
   - Go back to the "Security" section of your Google Account
   - Under "Signing in to Google", click on "App passwords"
   - You may need to sign in again

2. **Create App Password**
   - Select "Mail" as the app
   - Select "Windows Computer" (or your operating system) as the device
   - Click "Generate"

3. **Copy the App Password**
   - Google will generate a 16-character password
   - **Copy this password immediately** - you won't be able to see it again
   - The password will look like: `abcd efgh ijkl mnop`

**Note**: Remove spaces when using the app password. The actual password is `abcdefghijklmnop`.

## Step 3: Configure System Settings

1. **Edit config.json**
   - Open the `config.json` file in your project directory
   - Update the email section:

```json
{
  "email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your-gmail-address@gmail.com",
    "sender_password": "abcdefghijklmnop",
    "admin_email": "admin@example.com",
    "alert_cooldown_minutes": 30,
    "enabled": true
  }
}
```

Replace:
- `your-gmail-address@gmail.com` with your actual Gmail address
- `abcdefghijklmnop` with your 16-character app password (no spaces)
- `admin@example.com` with the email address where you want to receive alerts

## Step 4: VPN Compatibility Issues

### **⚠️ IMPORTANT: Email Alerts Do Not Work with VPN**

If you're using a VPN (such as NordVPN), **email alerts will NOT work** due to VPN blocking SSL/TLS handshakes with Gmail's SMTP servers.

#### Symptoms of VPN Blocking SMTP:
```
Connecting to SMTP server (timeout: 30s)...
Connected! Starting TLS...
❌ Email connection timeout: _ssl.c:1015: The handshake operation timed out
```

#### **Solutions:**

**Option 1: Disable VPN Temporarily (Recommended for Testing)**
```bash
# Disconnect VPN, then test email
python run_unified_system.py --alert-test
```

**Option 2: Add Python to VPN Split Tunneling**

For NordVPN users:
1. Open NordVPN app → Settings → Split Tunneling
2. Enable Split Tunneling
3. Click "Add Application"
4. Browse to your Python executable (e.g., `C:\Users\YourName\Desktop\thesis\data\joy\python.exe`)
5. Save and reconnect VPN

**Result**: Python scripts will bypass VPN while other applications remain protected.

**Option 3: Disable Email Alerts in Config**

If you must keep VPN on at all times:
```json
{
  "email": {
    "enabled": false
  }
}
```
Alerts will still be logged to console but not emailed.

**Option 4: Try Different VPN Servers**

Some VPN servers may not block SMTP:
- Try connecting to different countries (US, UK, Canada)
- Try P2P-optimized servers (often have fewer port restrictions)
- Try obfuscated servers in NordVPN settings

### Testing VPN Connectivity

Before running the system, test if SMTP ports are accessible:

**Windows PowerShell:**
```powershell
Test-NetConnection -ComputerName smtp.gmail.com -Port 587
Test-NetConnection -ComputerName smtp.gmail.com -Port 465
```

**Expected Output (Port Accessible):**
```
TcpTestSucceeded : True
```

**Expected Output (Port Blocked by VPN):**
```
TcpTestSucceeded : False
```

## Step 5: Configure Firewall/Antivirus

### Windows Firewall

1. **Allow Python through Windows Firewall**
   - Open Windows Security (search for it in Start menu)
   - Click on "Firewall & network protection"
   - Click on "Allow an app through firewall"
   - Click "Change settings"
   - Click "Allow another app"
   - Browse to your Python installation (usually `C:\Python38\python.exe` or similar)
   - Select Python and click "Add"
   - Make sure both "Private" and "Public" are checked

2. **Alternative: Command Line**
   ```cmd
   netsh advfirewall firewall add rule name="Python SMTP" dir=out action=allow program="C:\Python38\python.exe" enable=yes
   ```

### Windows Defender Antivirus

1. **Add Python to Exclusions**
   - Open Windows Security
   - Click on "Virus & threat protection"
   - Under "Virus & threat protection settings", click "Manage settings"
   - Scroll down to "Exclusions" and click "Add or remove exclusions"
   - Click "Add an exclusion" → "Folder"
   - Add your Python installation directory (e.g., `C:\Python38\`)

2. **Allow Outbound Connections**
   - Go to "Firewall & network protection"
   - Click "Advanced settings"
   - Click "Outbound Rules" in the left panel
   - Look for any rules blocking Python or port 587
   - If found, right-click and disable them

### Third-Party Antivirus (e.g., Avast, Norton, McAfee)

1. **Add Python to Trusted Applications**
   - Open your antivirus software
   - Look for "Trusted Applications" or "Exclusions" settings
   - Add `python.exe` to the trusted list
   - Add your project directory to exclusions

2. **Disable Email Scanning**
   - Some antivirus software scans outgoing emails
   - Temporarily disable this feature or add an exception for SMTP traffic

### Linux Firewall (UFW)

```bash
# Allow outbound SMTP
sudo ufw allow out 587/tcp
sudo ufw allow out 465/tcp  # Alternative SSL port
```

### macOS Firewall

1. **System Preferences** → **Security & Privacy** → **Firewall**
2. **Turn off Firewall** temporarily for testing
3. Or add Python to allowed applications

## Step 6: Test Email Configuration

1. **Test the Configuration**
   ```bash
   python run_unified_system.py --alert-test
   ```

2. **Check the Output**
   - Look for "Email sent successfully!" message
   - Check your admin email for the test alert

3. **Common Test Messages**
   ```
   Email sent successfully!
   ```
   or
   ```
   Email not configured - logging alert instead
   To enable email alerts, set SENDER_PASSWORD environment variable
   ```

## Troubleshooting

### Authentication Failed

**Error**: `Email alert failed: (535, b'5.7.8 Authentication failed')`

**Solutions**:
1. Verify 2-step verification is enabled
2. Generate a new app password
3. Make sure you're using the app password, not your regular password
4. Remove spaces from the app password
5. Try signing out and back into Gmail

### Connection Timeout

**Error**: `Email alert failed: [Errno 110] Connection timed out` or `_ssl.c:1015: The handshake operation timed out`

**Solutions**:
1. **Check if VPN is enabled** - VPNs (especially NordVPN) block SMTP SSL/TLS handshakes
   - Disable VPN temporarily and test again
   - OR add Python to VPN split tunneling (see Step 4)
2. Check your internet connection
3. Verify firewall settings (see Step 5)
4. Try different SMTP ports: 587 (TLS) or 465 (SSL)
5. Check if your ISP blocks SMTP traffic

### Less Secure Apps

**Note**: Gmail no longer supports "less secure apps". You must use app passwords with 2-step verification enabled.

### Multiple Gmail Accounts

If you have multiple Gmail accounts:
1. Use the app password from the account you want to send from
2. Make sure the `sender_email` in config.json matches the account

### Corporate/Enterprise Gmail

For G Suite/Workspace accounts:
1. App passwords may not be available
2. Contact your IT administrator for SMTP settings
3. May need to use OAuth2 instead of app passwords

## Alternative Email Providers

If you prefer not to use Gmail, you can configure other SMTP providers:

### Outlook/Hotmail
```json
{
  "email": {
    "smtp_server": "smtp-mail.outlook.com",
    "smtp_port": 587,
    "sender_email": "your-email@outlook.com",
    "sender_password": "your-password",
    "admin_email": "admin@example.com"
  }
}
```

### Yahoo Mail
```json
{
  "email": {
    "smtp_server": "smtp.mail.yahoo.com",
    "smtp_port": 587,
    "sender_email": "your-email@yahoo.com",
    "sender_password": "your-app-password",
    "admin_email": "admin@example.com"
  }
}
```

**Note**: Other providers may require different setup procedures. Check their documentation for app passwords or SMTP settings.

## Security Best Practices

1. **Never commit app passwords to version control**
2. **Use environment variables for sensitive data**:
   ```bash
   export SENDER_PASSWORD="your-app-password"
   ```
3. **Rotate app passwords regularly**
4. **Monitor email usage** in your Google account
5. **Use strong, unique passwords** for your Google account

## Advanced Configuration

### Environment Variables

Instead of hardcoding in `config.json`, use environment variables:

```bash
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
export SENDER_EMAIL="your-email@gmail.com"
export SENDER_PASSWORD="your-app-password"
export ADMIN_EMAILS="admin1@example.com,admin2@example.com"
```

### Multiple Admin Emails

Send alerts to multiple recipients:

```json
{
  "email": {
    "admin_email": "admin1@example.com,admin2@example.com,admin3@example.com"
  }
}
```

### Alert Cooldown

Prevent spam by setting cooldown periods:

```json
{
  "email": {
    "alert_cooldown_minutes": 30
  }
}
```

This prevents the same alert from being sent more than once every 30 minutes.

## Support

If you continue to have issues:

1. Check the system logs for detailed error messages
2. Test with a simple Python SMTP script:

```python
import smtplib
from email.mime.text import MIMEText

# Test SMTP connection
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('your-email@gmail.com', 'your-app-password')
print("SMTP connection successful!")
server.quit()
```

3. Verify your Gmail account settings
4. Check firewall and antivirus logs
5. Try from a different network (some corporate networks block SMTP)

For additional help, check the main README.md troubleshooting section.
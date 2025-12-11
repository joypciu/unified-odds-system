# Security Configuration Guide

## 🔐 Overview

The unified odds system now uses **AES-256 encryption (via Fernet)** to protect sensitive configuration data, specifically your email credentials stored in `config.json`.

## 🎯 What's Protected

- **Email Address** (`sender_email`): Encrypted with `ENC:` prefix
- **Email Password** (`sender_password`): Encrypted with `ENC:` prefix
- **Other Settings**: Remain in plain text (no sensitive data)

## 🔑 Key Files

### `.config_key` (Secret - Never Commit!)
- Contains the encryption key
- Generated automatically on first encryption
- **CRITICAL**: Must be kept secure and backed up
- Automatically excluded from git via `.gitignore`
- Size: 44 bytes (Base64-encoded Fernet key)

### `config.json` (Can be committed)
- Contains encrypted sensitive data with `ENC:` prefix
- Safe to commit to version control
- Example:
  ```json
  {
    "email": {
      "sender_email": "ENC:Z0FBQUFBQnBO...",
      "sender_password": "ENC:Z0FBQUFBQnBO..."
    }
  }
  ```

## 🚀 Quick Start

### Initial Setup (First Time)

1. **Install cryptography package**:
   ```bash
   pip install cryptography
   ```

2. **Encrypt your config.json**:
   ```bash
   python encrypt_config.py
   ```

3. **Verify encryption**:
   - Open `config.json` and check that email fields show `ENC:...`
   - Verify `.config_key` file exists

4. **Backup the key**:
   ```bash
   # Copy .config_key to a secure location
   cp .config_key ~/secure_backup/unified-odds-config-key
   ```

### Using Encrypted Config

The system automatically decrypts config when loading:

```python
from secure_config import SecureConfig

# Load and decrypt automatically
secure_config = SecureConfig("config.json")
config = secure_config.load_config()

# Use config normally - decryption is automatic
email = config['email']['sender_email']  # Returns decrypted value
password = config['email']['sender_password']  # Returns decrypted value
```

## 🖥️ VPS Deployment

### Method 1: Copy Both Files

```bash
# On local machine
scp config.json ubuntu@142.44.160.36:~/unified-odds-system/
scp .config_key ubuntu@142.44.160.36:~/unified-odds-system/
```

### Method 2: Re-encrypt on VPS

```bash
# 1. Push unencrypted config (temporarily)
git add config.json
git commit -m "Update config"
git push

# 2. On VPS
cd ~/unified-odds-system
git pull
python encrypt_config.py

# 3. Locally, pull the encrypted version back
git pull
```

### Method 3: Environment Variables (Alternative)

If you prefer not to use encryption, the system falls back to environment variables:

```bash
export SENDER_EMAIL="your-email@gmail.com"
export SENDER_PASSWORD="your-app-password"
export ADMIN_EMAIL="admin@example.com"
```

## 🔄 How It Works

### Encryption Process

1. **Key Generation**: First run creates `.config_key` with Fernet encryption key
2. **Encryption**: Sensitive values are encrypted using AES-128 in CBC mode
3. **Storage**: Encrypted values stored as `ENC:` + Base64-encoded ciphertext
4. **Decryption**: Automatic on load - transparent to application code

### Security Features

- **AES-256 Encryption**: Military-grade encryption via Fernet (symmetric encryption)
- **Base64 Encoding**: Safe for JSON storage
- **Automatic Key Management**: Key generated and stored securely
- **Prefix Detection**: `ENC:` prefix indicates encrypted values
- **Backward Compatible**: Unencrypted values still work (for migration)

## 📋 Common Tasks

### Check if Config is Encrypted

```bash
# Windows PowerShell
Get-Content config.json | Select-String "ENC:"

# Linux/Mac
grep "ENC:" config.json
```

Expected output:
```
"sender_email": "ENC:Z0FBQUFBQnBO...",
"sender_password": "ENC:Z0FBQUFBQnBO...",
```

### Re-encrypt Config (Change Key)

```bash
# Backup old key
mv .config_key .config_key.old

# Decrypt with old key (edit secure_config.py temporarily to use .config_key.old)
# Or just edit config.json to put plain text values back

# Encrypt with new key
python encrypt_config.py
```

### View Decrypted Values (Debug)

```python
from secure_config import SecureConfig

sc = SecureConfig("config.json")
config = sc.load_config()

print("Email:", config['email']['sender_email'])
print("Password:", config['email']['sender_password'])
```

### Manual Encryption

```python
from secure_config import SecureConfig

sc = SecureConfig()
encrypted_email = sc.encrypt_value("your-email@gmail.com")
print(f"Encrypted: ENC:{encrypted_email}")
```

## ⚠️ Important Security Notes

### DO:
- ✅ Keep `.config_key` in a secure location
- ✅ Backup `.config_key` separately from code
- ✅ Use environment variables in CI/CD pipelines
- ✅ Commit encrypted `config.json` to git
- ✅ Transfer `.config_key` securely (SSH, secure drive)

### DON'T:
- ❌ **NEVER commit `.config_key` to git**
- ❌ Don't share `.config_key` via email/chat
- ❌ Don't store `.config_key` in cloud sync folders
- ❌ Don't use same key across multiple projects
- ❌ Don't commit unencrypted config.json

## 🔍 Troubleshooting

### Error: "could not decrypt - invalid key"

**Cause**: `.config_key` doesn't match the key used to encrypt config.json

**Solution**:
1. Restore correct `.config_key` from backup
2. Or re-encrypt config.json with current key:
   ```bash
   # Edit config.json to put plain text values
   python encrypt_config.py
   ```

### Error: "config.json not found"

**Cause**: Missing config file

**Solution**:
```bash
# Copy from template
cp config.json.template config.json
# Edit with your values
# Encrypt
python encrypt_config.py
```

### Decryption Returns Garbage

**Cause**: Wrong key or corrupted encryption

**Solution**:
1. Delete `.config_key`
2. Edit `config.json` to restore plain text values
3. Run `python encrypt_config.py` again

## 🛡️ Best Practices

1. **Local Development**:
   - Encrypt config before committing
   - Keep `.config_key` in secure location
   - Don't share key with team (each dev encrypts their own)

2. **VPS/Production**:
   - Transfer `.config_key` via SSH/SCP only
   - Set restrictive file permissions: `chmod 600 .config_key`
   - Consider using environment variables for extra security

3. **Team Collaboration**:
   - Share config.json.template (without sensitive data)
   - Each team member creates their own config.json
   - Each team member runs encrypt_config.py
   - Never share encryption keys

4. **Backup Strategy**:
   ```bash
   # Backup key to secure location
   cp .config_key ~/.secure/unified-odds-key-$(date +%Y%m%d)
   
   # Or use password manager to store key content
   cat .config_key | base64
   ```

## 📊 File Permissions

```bash
# Recommended permissions on Linux/VPS
chmod 600 .config_key          # Read/write owner only
chmod 644 config.json          # Read all, write owner
chmod 755 secure_config.py     # Executable
chmod 755 encrypt_config.py    # Executable
```

## 🎓 Technical Details

### Encryption Algorithm
- **Algorithm**: Fernet (symmetric encryption)
- **Cipher**: AES in CBC mode with 128-bit key
- **Authentication**: HMAC using SHA256
- **IV**: Random 128-bit initialization vector
- **Timestamp**: Included for TTL validation

### Key Format
```python
# .config_key contains:
# 32 bytes of URL-safe base64-encoded key
# Example: b'abcdefghijklmnopqrstuvwxyz012345=='
```

### Encrypted Value Format
```
ENC:<base64_encoded_encrypted_data>

Where encrypted_data = Fernet.encrypt(plaintext)
- Includes timestamp
- Includes random IV
- Authenticated with HMAC
```

## 📞 Support

If you need to reset encryption:
1. Delete `.config_key`
2. Edit `config.json` to plain text values
3. Run `python encrypt_config.py`

For VPS deployment help, see `DEPLOYMENT_COMPLETE_GUIDE.md`

"""
Encrypt existing config.json with sensitive email credentials
Run this once to encrypt your config, then the system will use encrypted values
"""

from secure_config import SecureConfig
import json
from pathlib import Path

def main():
    config_file = Path("config.json")
    
    if not config_file.exists():
        print("❌ config.json not found!")
        return
    
    print("🔐 Encrypting config.json...")
    print("-" * 50)
    
    # Read current config
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Check if already encrypted
    if 'email' in config:
        email_config = config['email']
        password = email_config.get('sender_password', '')
        if password.startswith('ENC:'):
            print("⚠️  Config is already encrypted!")
            print("\nCurrent encrypted values:")
            if 'sender_email' in email_config:
                print(f"  Email: {email_config['sender_email'][:20]}...")
            if 'sender_password' in email_config:
                print(f"  Password: {email_config['sender_password'][:20]}...")
            return
    
    # Display current values (for verification)
    print("Current unencrypted values:")
    if 'email' in config:
        email_config = config['email']
        sender_email = email_config.get('sender_email', '')
        sender_password = email_config.get('sender_password', '')
        
        if sender_email:
            print(f"  Email: {sender_email}")
        if sender_password:
            # Mask password
            masked = sender_password[:2] + '*' * (len(sender_password) - 4) + sender_password[-2:] if len(sender_password) > 4 else '***'
            print(f"  Password: {masked}")
    
    # Encrypt
    secure_config = SecureConfig(str(config_file))
    secure_config.save_config(config, encrypt_sensitive=True)
    
    print("\n" + "=" * 50)
    print("✅ Configuration encrypted successfully!")
    print("=" * 50)
    print("\n🔑 Encryption key saved to: .config_key")
    print("⚠️  IMPORTANT SECURITY NOTES:")
    print("   1. .config_key is automatically excluded from git")
    print("   2. NEVER commit .config_key to version control")
    print("   3. Keep .config_key secure - it's needed to decrypt config")
    print("   4. Backup .config_key in a secure location")
    print("   5. When deploying to VPS, copy .config_key separately")
    print("\n📋 Next steps:")
    print("   1. Verify config.json shows ENC:... for sensitive fields")
    print("   2. Test the system: python run_unified_system.py")
    print("   3. For VPS: Copy .config_key to VPS along with config.json")

if __name__ == "__main__":
    main()

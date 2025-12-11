"""
Secure Configuration Manager
Encrypts sensitive data in config.json using Fernet encryption
"""

import json
import os
from pathlib import Path
from cryptography.fernet import Fernet
import base64
import hashlib


class SecureConfig:
    """Manages encrypted configuration"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.key_file = Path(".config_key")
        self.cipher = None
        self._load_or_create_key()
    
    def _load_or_create_key(self):
        """Load existing key or create a new one"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate a new key
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            print("🔐 Generated new encryption key")
        
        self.cipher = Fernet(key)
    
    def encrypt_value(self, value: str) -> str:
        """Encrypt a string value"""
        if not value:
            return value
        encrypted = self.cipher.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt an encrypted string value"""
        if not encrypted_value:
            return encrypted_value
        try:
            decoded = base64.b64decode(encrypted_value.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except:
            # If decryption fails, assume it's not encrypted
            return encrypted_value
    
    def load_config(self) -> dict:
        """Load and decrypt configuration"""
        if not self.config_path.exists():
            return self._get_default_config()
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Decrypt sensitive fields
        if 'email' in config:
            email_config = config['email']
            if 'sender_password' in email_config and email_config['sender_password'].startswith('ENC:'):
                email_config['sender_password'] = self.decrypt_value(
                    email_config['sender_password'][4:]  # Remove 'ENC:' prefix
                )
            if 'sender_email' in email_config and email_config['sender_email'].startswith('ENC:'):
                email_config['sender_email'] = self.decrypt_value(
                    email_config['sender_email'][4:]
                )
        
        return config
    
    def save_config(self, config: dict, encrypt_sensitive: bool = True):
        """Save configuration with encrypted sensitive fields"""
        config_to_save = json.loads(json.dumps(config))  # Deep copy
        
        if encrypt_sensitive and 'email' in config_to_save:
            email_config = config_to_save['email']
            
            # Encrypt sender_password if not already encrypted
            if 'sender_password' in email_config:
                password = email_config['sender_password']
                if not password.startswith('ENC:'):
                    encrypted = self.encrypt_value(password)
                    email_config['sender_password'] = f"ENC:{encrypted}"
            
            # Encrypt sender_email if not already encrypted
            if 'sender_email' in email_config:
                email = email_config['sender_email']
                if not email.startswith('ENC:'):
                    encrypted = self.encrypt_value(email)
                    email_config['sender_email'] = f"ENC:{encrypted}"
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved encrypted configuration to {self.config_path}")
    
    def _get_default_config(self) -> dict:
        """Get default configuration"""
        return {
            "enabled_scrapers": {
                "1xbet": True,
                "fanduel": True,
                "bet365": False
            },
            "email": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "sender_email": "",
                "sender_password": "",
                "admin_email": "usmanjoycse@gmail.com",
                "alert_cooldown_minutes": 720,
                "enabled": True
            },
            "monitoring": {
                "check_interval_seconds": 300,
                "data_stale_threshold_minutes": 60,
                "failure_threshold": 1,
                "modules": [
                    "bet365_pregame",
                    "bet365_live",
                    "fanduel_pregame",
                    "fanduel_live",
                    "1xbet_pregame",
                    "1xbet_live"
                ]
            },
            "cache": {
                "auto_update": True,
                "update_interval_minutes": 5
            }
        }
    
    def encrypt_existing_config(self):
        """Encrypt an existing unencrypted config.json"""
        if not self.config_path.exists():
            print("❌ config.json not found")
            return
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Check if already encrypted
        if 'email' in config:
            email_config = config['email']
            password = email_config.get('sender_password', '')
            if password.startswith('ENC:'):
                print("⚠️  Configuration is already encrypted")
                return
        
        print("🔐 Encrypting sensitive data in config.json...")
        self.save_config(config, encrypt_sensitive=True)
        print("✅ Configuration encrypted successfully")
        print("⚠️  IMPORTANT: Keep .config_key file secure and DO NOT commit it to git")


def encrypt_config_cli():
    """Command-line interface to encrypt config"""
    import sys
    
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    else:
        config_file = "config.json"
    
    secure_config = SecureConfig(config_file)
    secure_config.encrypt_existing_config()
    
    print("\n📋 To use the encrypted config in your code:")
    print("   from secure_config import SecureConfig")
    print("   secure_config = SecureConfig()")
    print("   config = secure_config.load_config()")


if __name__ == "__main__":
    encrypt_config_cli()

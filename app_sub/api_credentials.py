# filename: app_sub/api_credentials.py
import os
import json
from cryptography.fernet import Fernet
from flask import Blueprint, render_template, request, jsonify

# Create Blueprint
api_credentials_bp = Blueprint('api_credentials', __name__)

# Get encryption key
def get_encryption_key():
    key_file = '.encryption.key'
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

# Setup encryption
cipher = Fernet(get_encryption_key())

# File to store credentials
CREDS_FILE = 'data/.api_credentials.json'

# Simple routes
@api_credentials_bp.route('/symbol-api')
def symbol_api():
    # Load and show credentials
    creds = []
    if os.path.exists(CREDS_FILE):
        with open(CREDS_FILE, 'r') as f:
            data = json.load(f)
            for exchange, info in data.items():
                # Decrypt and mask the API key
                api_key = cipher.decrypt(info['api_key'].encode()).decode()
                masked = f"{api_key[:8]}...{api_key[-4:]}"
                creds.append({
                    'exchange': exchange,
                    'masked_key': masked
                })
    
    return render_template('symbol_api_manager.html', credentials=creds)

@api_credentials_bp.route('/api/credentials/add', methods=['POST'])
def add_credentials():
    data = request.get_json()
    
    # Get the form data
    exchange = data['exchange']
    api_key = data['api_key']
    api_secret = data['api_secret']
    
    # Encrypt the credentials
    encrypted_key = cipher.encrypt(api_key.encode()).decode()
    encrypted_secret = cipher.encrypt(api_secret.encode()).decode()
    
    # Load existing or create new
    if os.path.exists(CREDS_FILE):
        with open(CREDS_FILE, 'r') as f:
            creds = json.load(f)
    else:
        creds = {}
        os.makedirs('data', exist_ok=True)
    
    # Save encrypted data
    creds[exchange] = {
        'api_key': encrypted_key,
        'api_secret': encrypted_secret
    }
    
    with open(CREDS_FILE, 'w') as f:
        json.dump(creds, f)
    
    return jsonify({'success': True})
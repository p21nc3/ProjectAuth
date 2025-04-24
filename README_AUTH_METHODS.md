# Authentication Methods Implementation

This document describes the authentication methods detection implemented in the SSO Monitor project.

## Overview

The system now detects three main types of authentication:

1. **Password-Based Authentication** - Traditional username/password login forms
2. **Passkey Authentication** - WebAuthn/FIDO based passwordless authentication
3. **Multi-Factor Authentication (MFA)** - Including TOTP, SMS, Email, and App-based 2FA

## Database Structure

Authentication methods are stored in two places:

1. **recognized_idps**: Each authentication method appears as a separate IDP entry:
   - `PASSWORD_BASED` - For password-based authentication
   - `PASSKEY` - For WebAuthn/passkey authentication
   - `MFA_GENERIC` - For multi-factor authentication

2. **auth_methods**: A separate field at the same level as recognized_idps, containing specific details about each method:
   ```json
   "auth_methods": {
     "password": {"detected": true, "validity": "HIGH"},
     "passkey": {"detected": false, "validity": "LOW"},
     "totp": {"detected": true, "validity": "HIGH"},
     "sms": {"detected": false, "validity": "LOW"},
     "email": {"detected": false, "validity": "LOW"},
     "app": {"detected": false, "validity": "LOW"}
   }
   ```

## Database Indexes

Indexes are created for both the `recognized_idps.idp_name` field and each individual `auth_methods.*detected` field:

```javascript
db.landscape_analysis_tres.createIndex({ "recognized_idps.idp_name": 1 });
db.landscape_analysis_tres.createIndex({ "auth_methods.password.detected": 1 });
// ...additional indexes for other auth methods
```

## Detection Flow

1. Individual detectors (password_detector.py, passkey_detector.py, mfa_detector.py) look for specific authentication methods.
2. When a method is detected, it updates:
   - The appropriate field in `auth_methods`
   - Adds an entry to `recognized_idps` with the corresponding IDP type
3. A final sync_auth_methods_to_idps function ensures that any methods detected in auth_methods are also represented in recognized_idps.

## Configuration

Authentication methods are configured in idp_rules.py with the following IDPs:

- `PASSWORD_BASED`: Traditional username/password authentication
- `PASSKEY`: WebAuthn/FIDO based authentication
- `MFA_GENERIC`: Multi-factor authentication methods

Each IDP has definitions for:
- Keywords for UI detection
- Login request rules for network traffic detection
- Form rules for input field detection
- SDK detection patterns

## Example Database Output

A website with password authentication and TOTP 2FA would produce:

```json
{
  "recognized_idps": [
    {
      "idp_name": "PASSWORD_BASED",
      "idp_integration": "PASSWORD",
      "detection_method": "PASSWORD_BASED",
      "login_page_candidate": "https://example.com/login",
      "validity": "HIGH"
    },
    {
      "idp_name": "MFA_GENERIC",
      "idp_integration": "MFA",
      "detection_method": "MFA",
      "login_page_candidate": "https://example.com/login",
      "validity": "HIGH"
    }
  ],
  "auth_methods": {
    "password": {"detected": true, "validity": "HIGH"},
    "passkey": {"detected": false, "validity": "LOW"},
    "totp": {"detected": true, "validity": "HIGH"},
    "sms": {"detected": false, "validity": "LOW"},
    "email": {"detected": false, "validity": "LOW"},
    "app": {"detected": false, "validity": "LOW"}
  }
}
``` 
# Enhanced Authentication Detection Methods

This document describes the new authentication detection methods added to the SSO-Monitor crawler.

## New Authentication Methods

The crawler now detects the following additional authentication methods:

1. **Passkey (WebAuthn)**
2. **Multi-Factor Authentication (MFA)**
3. **Traditional Username/Password**

## Detection Mechanisms

### 1. Passkey (WebAuthn) Detection

Passkey detection uses multiple approaches:

- **Navigator Credentials API Monitoring**: Detects calls to the WebAuthn API (`navigator.credentials.create/get` with `publicKey` parameter)
- **Keyword Detection**: Identifies UI elements with keywords like "passkey", "webauthn", "security key"
- **Pattern Matching**: Recognizes login flows that follow WebAuthn authentication patterns

The detected passkey authentication is stored in:
- `recognized_idps` with `idp_name: "PASSKEY"`
- `auth_methods.passkey.detected` set to `true`
- `metadata_available.webauthn_api` when the WebAuthn API is used

### 2. Multi-Factor Authentication (MFA) Detection

MFA detection focuses on finding:

- **OTP Input Fields**: Input fields for one-time codes (SMS, email, authenticator app)
- **Verification Code UI**: Fields specifically designed for verification codes
- **QR Code Images**: For authenticator app scanning
- **MFA Keywords**: Text mentioning "2FA", "MFA", "verification code", etc.

MFA detection is categorized into subtypes when possible:
- TOTP (Time-based One-Time Password)
- SMS verification
- Email verification
- Authenticator app verification

Results are stored in:
- `recognized_idps` with `idp_name: "MFA_GENERIC"`
- `auth_methods.totp/sms/email/app.detected` based on detected type

### 3. Username/Password Detection

Traditional login form detection includes:

- **Form Analysis**: Looking for forms with username and password fields
- **Input Field Patterns**: Detecting inputs with names/attributes related to usernames and passwords
- **Submit Button Detection**: Ensuring the form has a submit mechanism

Results are stored in:
- `recognized_idps` with `idp_name: "PASSWORD_BASED"`
- `auth_methods.password.detected` set to `true`

## Metadata Field

The new `metadata_available` field provides flattened authentication information:

```json
"metadata_available": {
  "idps": ["GOOGLE", "FACEBOOK", "PASSWORD_BASED"],
  "webauthn_api": true,
  "lastpass": false
}
```

This field makes it easier to query and report on authentication methods.

## Configuration

All detection rules are configurable in `worker/config/idp_rules.py` with the following structure:

- **PASSKEY**: WebAuthn and passkey detection rules
- **MFA_GENERIC**: 2FA/MFA detection rules
- **PASSWORD_BASED**: Username/password form detection rules

## Database Indexes

New MongoDB indexes have been added to support querying these authentication methods:

```javascript
db.landscape_analysis_tres.createIndex({"landscape_analysis_result.auth_methods.password.detected": 1});
// ... and similar indexes for other auth methods
```

## Usage

These new detection methods are automatically integrated into the existing crawler pipeline. No additional configuration is needed to enable them. 
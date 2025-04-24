# Authentication Detection Extension

This extension adds the capability to detect additional authentication methods beyond traditional Social Sign-On (SSO) buttons.

## New Authentication Types

### 1. Password-Based Authentication

Detects traditional username/password login forms using these methods:
- CSS input field detection for username/email and password fields
- Keyword matching for related login text
- Form structure analysis

### 2. Multi-Factor Authentication (MFA)

Detects various types of MFA including:
- OTP input fields
- QR code displays
- Email/SMS verification code fields
- Keyword matching for 2FA/MFA related text

### 3. Passkey/WebAuthn

Detects modern passwordless authentication using:
- WebAuthn API detection (navigator.credentials)
- Passkey button detection
- Fingerprint/biometric UI element detection

## Integration

These new authentication methods are fully integrated into the existing system:
- Added as IDPs in the same format as existing SSO providers (Google, Apple, etc.)
- Added to in-scope IDPs for automated scanning
- Included in the metadata_available flattened information
- Displayed in the WebUI

## Metadata Extensions

The following metadata fields have been added:
- `webauthn_api`: Indicates whether WebAuthn API usage was detected on the site
- `lastpass`: Indicates whether LastPass password manager integration was detected
- `idp_passkey`: Indicates Passkey authentication was detected
- `idp_mfa_generic`: Indicates MFA was detected
- `idp_username_password`: Indicates traditional password login was detected

## Implementation Details

1. New detectors:
   - `password_field.py`: Detects username/password form fields
   - `mfa_field.py`: Detects MFA-related elements
   - `passkey_button.py`: Detects passkey authentication elements

2. Updated configurations:
   - Added new IDP rules in `idp_rules.py`
   - Added detection methods to recognition strategy scope

## Usage

The new detectors run automatically as part of the standard landscape analysis process and require no special configuration. The results appear in the same format as existing SSO detection. 
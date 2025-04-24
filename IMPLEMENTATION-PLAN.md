# Enhanced Authentication Detection Implementation

## Recognition Strategy Architecture

### Passkey Detection
1. **Keyword Strategy**:
   - Scan for WebAuthn-related terms in button text/attributes
   ```python
   # sso_button.py
   locator = CSSLocator(IdpRules["PASSKEY"]["keywords"], ["passkey", "webauthn"])
   ```
2. **API Monitoring**:
   - Track navigator.credentials.create/get calls
   ```python
   # navigator_credentials.py
   if function_name in ["create", "get"] and "publicKey" in params:
       log_webauthn_attempt()
   ```

### 2FA/MFA Detection
1. **Multi-phase Recognition**:
   ```python
   # sso_button.py
   if previous_stage == "PASSWORD_BASED":
       mfa_elements = locator.locate(page, IdpRules["MFA_GENERIC"]["keywords"])
   ```
2. **Domain Pattern Matching**:
   ```python
   # idp_rules.py
   "passive_login_request_rule": {
       "domain": ".*(2fa|verify|sms|totp).*"
   }
   ```

### Username/Password Detection
1. **Form Field Analysis**:
   ```python
   # password_based_detector.py
   if field_count >= 2:  # username + password
       validity = "HIGH"
   ```

## Configuration Updates

### In-Scope IDPs (config/idp_config.yml)
```yaml
idp_scope: [
    "PASSKEY", 
    "MFA_GENERIC",
    "PASSWORD_BASED",
    # existing IDPs...
]
```

### Recognition Strategy Scope (config/recognition_strategy_config.yml)
```yaml
recognition_strategy_scope: [
    "PASSKEY-KEYWORD",
    "PASSKEY-API",
    "MFA-MULTIPHASE",
    "PASSWORD-FORM",
    # existing strategies...
]
```

## Web UI Changes

### New Detection Indicators
```javascript
// frontend/src/components/AuthMatrix.vue
const AUTH_LABELS = {
  PASSKEY: { color: '#38a169', icon: 'key' },
  MFA: { color: '#3182ce', icon: 'shield-check' },
  PASSWORD: { color: '#718096', icon: 'lock-closed' }
}
```

## Database Schema Updates

### New Collections/Tables
```sql
-- Add passkey metadata table
CREATE TABLE passkey_detections (
    detection_id UUID PRIMARY KEY,
    rp_id TEXT,
    user_verified BOOLEAN,
    created_at TIMESTAMPTZ
);

-- Add MFA tracking column
ALTER TABLE auth_attempts ADD COLUMN mfa_types TEXT[];
```

## Implementation Checklist

1. Update IDP configuration files with new rules
2. Modify recognition strategy handlers in sso_button.py
3. Extend navigator credentials monitoring
4. Add UI components for new detection types
5. Migrate database schema
6. Update API documentation with new detection types

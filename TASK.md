**Authentication Detection Implementation Plan**

**Objective:** Extend the existing crawler to detect additional authentication flows—Passkey (UI Button + WebAuthn), 2FA/MFA (TOTP/SMS/Email/QR-Code), and classic username/password—by updating detection rules, schema, UI, and analysis pipelines.


  1. **Passkey-Button Detection**
    (a) IDP Rule
      • Add a new entry for "PASSKEY" or incorporate passkey references in relevant IDPs with fields:
          "keywords" set to ["passkey", "webauthn",...] 
          "logos" set to "passkey/"
          "login_request_rule" capturing passkey-related domain/path or parameter patterns where possible
      • If passkey flows aren’t strictly domain-based, set broad domain/path patterns, possibly ".*", and rely primarily on the "keywords" field to detect passkey button text, sign in prompts, or references like "Sign in with a passkey".
      • Include sub-rules for different passkey SDKs.
      - Include `'PASSKEY'` in `recognition_strategy_scope`.
      - Ensure keyword/logo detection loops through new entry.

    (b) UI/SSO Button Detection in sso_button.py
      • Expand "recognition_strategy_scope" to include passkey scanning. The existing code checks IdpRules, so new passkey keywords/logos will be discovered (keyword_detection or logo_detection).
      • Make sure passkey references appear in the recognized_idps if these passkey buttons or text are clicked and matched during detection.

    (c) Potential Observations for WebAuthn
      • If needed, add logic to detect "navigator.credentials.create" or "navigator.credentials.get" calls if relevant, possibly in modules/detectors/navigator_credentials.py or a new module. This could complement the existing IDP detection approach.


  2. **2FA/MFA (Time-based OTP, App-based, QR based, SMS, Email)**

  (a) Extended IDP Rule Config or Additional Fields
    • For generic 2FA flows, we typically see "Enter your code" or "2-step verification" pages. We can create a new dictionary entry, e.g. "MFA_GENERIC", or we can store 2FA detection logic under a new "MFA" rule set in idp_rules.py. 
    • Provide broad domain/path patterns or keywords referencing 2fa, mfa, "one-time code," "TOTP,", "get qr code", or "Enter verification code."

  (b) Keyword Detection
    • In sso_button.py or a new detector, add 2FA-specific keywords for any pages that prompt for an extra code. That might require minimal domain constraints, focusing on text-based detection like "2FA code," "One-time code," or "verification code.",....

  (c) Multi-phase detection
    • If the crawler can detect that it has already seen a username/password submission, look for a subsequent prompt with 2FA code fields. This might require hooking the request flow or analyzing new pages after initial login submission. 
    • If an IDP rule references a second step domain (like domain that often handles 2FA), set it under an optional "passive_login_request_rule" or a new field in IdpRules.


  3. **Username/Password Detection**

  (a) Basic Form Fields
    • Possibly add a new IDP rule "PASSWORD_BASED" with "keywords" referencing "login", "password," or forms with name="username"/"password"/"email".
    • Alternatively, create a new logic path in sso_button.py or a new file (e.g., password_detector.py) if you want specialized detection. This would watch for typical login fields, then treat them like an "IDP" labeled "PASSWORD_BASED".

  (b) High & Low Validity
    • Mirror the existing pattern of High/Low validity for text detection, searching for placeholders like “Email,” “Username,” “Password,”.
    - Identify `<input>` tags whose `name|placeholder` matches `form_rule` patterns.
    - If both fields present, tag `PASSWORD_BASED` with high validity.

1. **Editor setup**: Open key files:
   - `worker/config/idp_rules.py`
   - `worker/modules/locators/` (CSS/XPath rules)
   - `worker/sso_button.py`
   - `worker/login_trace_analyzer.py`
   - `brain/static/schema/landscape_analysis.json`
   - `brain/templates/views/admin.html`
   - `bp_admin.py` (backend admin routes)

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

### New Detection Indicators
```javascript
// frontend/src/components/AuthMatrix.vue
const AUTH_LABELS = {
  PASSKEY: { color: '#38a169', icon: 'key' },
  MFA: { color: '#3182ce', icon: 'shield-check' },
  PASSWORD: { color: '#718096', icon: 'lock-closed' }
}
```

## Implementation Checklist

1. Update IDP configuration files with new rules
2. Modify recognition strategy handlers in sso_button.py
3. Extend navigator credentials monitoring
4. Add UI components for new detection types
5. Update database schema
6. Update API documentation with new detection types


## 2. Passkey (UI Button + WebAuthn) Detection


**C. Extend `sso_button.py`**:
- Include `'PASSKEY'` in `recognition_strategy_scope`.
- Ensure keyword/logo detection loops through new entry.

**D. (Optional) WebAuthn API Detector**:
- Create `worker/modules/detectors/navigator_credentials.py`:
  ```python
  def detect_webauthn(trace_log):
    if 'navigator.credentials.create' in trace_log or 'navigator.credentials.get' in trace_log:
      return 'PASSKEY'
    return None
  ```
- Invoke from login trace analyzer.

---

## 3. 2FA/MFA & SMS/Email/qr-code Code Detection

**A. IDP Rule** (`worker/config/idp_rules.py`):
```python
IdpRules['MFA_GENERIC'] = {
  'keywords': ['2fa','mfa','one-time code','verification code','sms','email code'],
  'logos':    None,
  'passive_login_request_rule': {'domain': '.*', 'path': '.*'},
  'mfa_step': {
    'selectors': ['.otp-input','#verificationCode',"input[name='code']"]
  }
}
```

**B. Keyword Detector** (`worker/sso_button.py`):
- After primary SSO detection, scan page text for any `MFA_GENERIC['keywords']`.
- Append to `recognized_idps` with `idp_name='MFA_GENERIC'`.

**C. Multi‑phase Flow** (`worker/login_trace_analyzer.py`):
- After detecting USERNAME_PASSWORD or SSO, follow redirect:
  ```python
  if last_detected in ('PASSWORD_BASED', 'PASSKEY'):
      crawl_next_page(); detect_keywords(MFA_GENERIC)
  ```

---

## 4. Username/Password Detection

**A. IDP Rule** (`worker/config/idp_rules.py`):
```python
IdpRules['PASSWORD_BASED'] = {
  'keywords': ['sign in','log in','username','password'],
  'logos':    'password/',
  'form_rule': {
    'fields': {
      'username': ['email','user','login'],
      'password': ['pass','pwd']
    }
  }
}
```

**B. Form Detector** (`worker/sso_button.py`):
- Identify `<input>` tags whose `name|placeholder` matches `form_rule` patterns.
- If both fields present, tag `PASSWORD_BASED` with high validity.

---

## 5. Schema Updates

**File:** `brain/static/schema/landscape_analysis.json`

1. **Extend `idp_scope` enum**:
   ```json
   "enum": [
     "APPLE","GOOGLE","FACEBOOK","MICROSOFT",
     "PASSKEY","PASSWORD_BASED","MFA_GENERIC"
   ]
   ```
2. **Add definitions** for new rule types:
   ```json
   "definitions": {
     "mfaStep": {
       "type": "object",
       "properties": {"selectors": {"type": "array", "items": {"type": "string"}}}
     },
     "formRule": {
       "type": "object",
       "properties": {"fields": {"type": "object"}}
     }
   }
   ```

---

## 6. Admin Interface Integration

**A. Backend Routes** (`bp_admin.py`):
```python
@bp_admin.route('/api/idp_rules', methods=['GET','PUT'])
def manage_idp_rules():
    # GET: return idp_rules.json
    # PUT: validate against JSON schema, write to worker/config/idp_rules.py
```

**B. UI Components** (`brain/templates/views/admin.html`):
```html
<h4>Authentication Rules</h4>
<pre id="idpRulesEditor"></pre>
<button onclick="saveIdpRules()">Save Rules</button>
<script>
  // load schema, init JSON editor on #idpRulesEditor
  // POST updated JSON to /api/idp_rules
</script>
```

**C. Hot‑Reload**:
- After saving, signal workers (via Redis pub/sub or touching a lock file) to reload `idp_rules.py` in memory.

---

## 7. Validation

   - Confirm `recognized_idps` includes new entries.

---

## 8. Build & Deploy

1. **Review Results** in database/API and dashboards.

---

## 9. Documentation & Review

- **Create** `README_2.md` with new detectors overview.

---

**End of Implementation Plan**
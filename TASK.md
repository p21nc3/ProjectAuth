**Authentication Detection Implementation Plan**

**Objective:** Extend the existing crawler to detect additional authentication flows—Passkey (WebAuthn), 2FA/MFA (TOTP/SMS/Email), QR‑code, and classic username/password—by updating detection rules, schema, UI, and analysis pipelines.

---

## 1. Prerequisites

1. **Checkout code**:
   ```bash
   git checkout -b feature/auth-detection
   ```
2. **Install dependencies** (Python/Node/Docker as per project).
3. **Editor setup**: Open key files:
   - `worker/config/idp_rules.py`
   - `worker/modules/locators/` (CSS/XPath rules)
   - `worker/sso_button.py`
   - `worker/login_trace_analyzer.py`
   - `brain/static/schema/landscape_analysis.json`
   - `brain/templates/views/admin.html`
   - `bp_admin.py` (backend admin routes)

---

## 2. Passkey (WebAuthn) Detection

**A. Define IDP Rule** (`worker/config/idp_rules.py`):
```python
IdpRules['PASSKEY'] = {
  'keywords': ['passkey', 'webauthn', 'security key'],
  'logos':    'passkey/',            # add logos under idp_patterns/passkey/
  'login_request_rule': {
    'domain': '.*', 'path': '.*',
    'params': [{'name': '^webauthn$', 'value': '.*'}]
  },
  'sdks': {
    'WEBAUTHN': {
      'login_request_rule': {'domain': '^webauthn\\..*', 'path': '^/authenticate'}
    }
  }
}
```

**B. Add Logo Assets**:
```bash
mkdir -p worker/config/idp_patterns/passkey/{16x16,100x100,250x250}
# Copy icon.png into each
```

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

## 3. 2FA/MFA & SMS/Email Code Detection

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
  if last_detected in ('USERNAME_PASSWORD', 'PASSKEY'):
      crawl_next_page(); detect_keywords(MFA_GENERIC)
  ```

---

## 4. Username/Password Detection

**A. IDP Rule** (`worker/config/idp_rules.py`):
```python
IdpRules['USERNAME_PASSWORD'] = {
  'keywords': ['sign in','log in','username','password'],
  'logos':    'basic-auth/',
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
- If both fields present, tag `USERNAME_PASSWORD` with high validity.

---

## 5. Schema Updates

**File:** `brain/static/schema/landscape_analysis.json`

1. **Extend `idp_scope` enum**:
   ```json
   "enum": [
     "APPLE","GOOGLE","FACEBOOK","MICROSOFT",
     "PASSKEY","USERNAME_PASSWORD","MFA_GENERIC"
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


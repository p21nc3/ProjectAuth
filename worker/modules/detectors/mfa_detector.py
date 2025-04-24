import logging
import time
from typing import List, Tuple
from playwright.sync_api import Page
from config.idp_rules import IdpRules
from modules.browser.browser import PlaywrightBrowser, PlaywrightHelper
from modules.helper.detection import DetectionHelper
from modules.helper.tmp import TmpHelper
from playwright.sync_api import sync_playwright, Error, TimeoutError

logger = logging.getLogger(__name__)

class MFADetector:
    """Detector for multi-factor authentication (MFA) elements like OTP fields, verification codes, etc."""
    
    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result
        
        self.browser_config = config["browser_config"]
        self.artifacts_config = config["artifacts_config"]
        self.idp_scope = config["idp_config"]["idp_scope"]
        self.recognition_mode = config["recognition_strategy_config"]["recognition_mode"]
        self.recognition_strategy_scope = config["recognition_strategy_config"]["recognition_strategy_scope"]
        
        self.login_page_candidates = result["login_page_candidates"]
        self.recognized_idps = result["recognized_idps"]
        
        # Get MFA selectors from IdpRules
        self.mfa_selectors = IdpRules.get("MFA_GENERIC", {}).get("mfa_step", {}).get("selectors", [])
        self.mfa_keywords = IdpRules.get("MFA_GENERIC", {}).get("keywords", [])
        
        # Initialize auth_methods if not present
        if "auth_methods" not in self.result:
            self.result["auth_methods"] = {}
        
        # Initialize MFA methods if not present
        mfa_types = ["totp", "sms", "email", "app"]
        for mfa_type in mfa_types:
            if mfa_type not in self.result["auth_methods"]:
                self.result["auth_methods"][mfa_type] = {"detected": False, "validity": "LOW"}

    def start(self):
        """Begin detection of MFA elements on login pages."""
        logger.info("Starting MFA detection")
        
        # Process each login page candidate
        for lpc in self.login_page_candidates:
            url = lpc.get("url")
            if not url:
                continue
                
            # Check if page is reachable and analyzable
            reachable = lpc.get("resolved", {}).get("reachable", False)
            valid = lpc.get("content_analyzable", {}).get("valid", False)
            if not reachable or not valid:
                logger.info(f"Login page candidate is not reachable or analyzable: {url}")
                continue
            
            # Check for MFA elements
            detected = self.detect_mfa_elements(url)
            if detected:
                # Add to recognized_idps if not already present
                if not any(idp.get("idp_name") == "MFA_GENERIC" for idp in self.recognized_idps):
                    self.recognized_idps.append({
                        "idp_name": "MFA_GENERIC",
                        "idp_integration": "GENERIC",
                        "recognition_strategy": "MFA_ELEMENTS",
                        "element_validity": "HIGH",
                        "login_page_url": url
                    })
                    
                # Update auth_methods if present - default to TOTP
                if "auth_methods" in self.result:
                    self.result["auth_methods"]["totp"]["detected"] = True
                    self.result["auth_methods"]["totp"]["validity"] = "HIGH"
                    
                # Only need to find one valid MFA form
                return
    
    def detect_mfa_elements(self, url: str) -> bool:
        """Check if the page contains MFA-related elements."""
        with TmpHelper.tmp_dir() as pdir, sync_playwright() as pw:
            context, page = PlaywrightBrowser.instance(pw, self.browser_config, pdir)
            
            try:
                # Navigate to page
                PlaywrightHelper.navigate(page, url, self.browser_config)
                
                # Check for MFA UI elements using selectors and keywords
                has_mfa = page.evaluate("""
                    (selectors, keywords) => {
                        // Check for specific input elements using selectors
                        for (const selector of selectors) {
                            if (document.querySelector(selector)) {
                                return { type: 'selector', value: selector };
                            }
                        }
                        
                        // Look for OTP input fields (multiple single-digit inputs)
                        const shortInputs = document.querySelectorAll('input[maxlength="1"], input[maxlength="2"]');
                        if (shortInputs.length >= 4 && shortInputs.length <= 8) {
                            return { type: 'otp_digits', count: shortInputs.length };
                        }
                        
                        // Check for SMS or email verification codes
                        const codeInputs = document.querySelectorAll('input[name*="code"], input[id*="code"], input[placeholder*="code"]');
                        if (codeInputs.length > 0) {
                            return { type: 'verification_code' };
                        }
                        
                        // Check visible text for MFA-related keywords
                        const bodyText = document.body.innerText.toLowerCase();
                        for (const keyword of keywords) {
                            if (bodyText.includes(keyword.toLowerCase())) {
                                return { type: 'keyword', value: keyword };
                            }
                        }
                        
                        // Check for QR code images
                        const qrImages = Array.from(document.querySelectorAll('img'))
                            .filter(img => 
                                img.alt && (img.alt.toLowerCase().includes('qr') || 
                                           img.alt.toLowerCase().includes('code')));
                        if (qrImages.length > 0) {
                            return { type: 'qr_code' };
                        }
                        
                        return false;
                    }
                """, self.mfa_selectors, self.mfa_keywords)
                
                # Close browser
                PlaywrightHelper.close_context(context)
                
                if has_mfa:
                    mfa_type = has_mfa.get('type', '')
                    logger.info(f"Detected MFA element ({mfa_type}) on {url}")
                    
                    # If we detected a specific type of MFA, update auth_methods
                    if "auth_methods" in self.result:
                        if mfa_type == 'keyword':
                            keyword = has_mfa.get('value', '').lower()
                            if 'sms' in keyword or 'text message' in keyword:
                                self.result["auth_methods"]["sms"]["detected"] = True
                                self.result["auth_methods"]["sms"]["validity"] = "HIGH"
                            elif 'email' in keyword:
                                self.result["auth_methods"]["email"]["detected"] = True
                                self.result["auth_methods"]["email"]["validity"] = "HIGH"
                            elif 'app' in keyword or 'authenticator' in keyword:
                                self.result["auth_methods"]["app"]["detected"] = True
                                self.result["auth_methods"]["app"]["validity"] = "HIGH"
                    
                return bool(has_mfa)
                
            except TimeoutError as e:
                logger.warning(f"Timeout in MFA detection on: {url}")
                logger.debug(e)
                return False
                
            except Error as e:
                logger.warning(f"Error in MFA detection on: {url}")
                logger.debug(e)
                return False
    
    def check_for_mfa_indicators(self, page: Page) -> bool:
        """Look for indicators of various MFA methods."""
        detected = False
        
        # Check for TOTP (Time-based One-Time Password)
        totp_detected = self.check_for_totp(page)
        if totp_detected:
            self.result["auth_methods"]["totp"]["detected"] = True
            self.result["auth_methods"]["totp"]["validity"] = "HIGH"
            detected = True
        
        # Check for SMS verification
        sms_detected = self.check_for_sms(page)
        if sms_detected:
            self.result["auth_methods"]["sms"]["detected"] = True
            self.result["auth_methods"]["sms"]["validity"] = "HIGH"
            detected = True
        
        # Check for Email verification
        email_detected = self.check_for_email(page)
        if email_detected:
            self.result["auth_methods"]["email"]["detected"] = True
            self.result["auth_methods"]["email"]["validity"] = "HIGH"
            detected = True
        
        # Check for App-based verification
        app_detected = self.check_for_app(page)
        if app_detected:
            self.result["auth_methods"]["app"]["detected"] = True
            self.result["auth_methods"]["app"]["validity"] = "HIGH"
            detected = True
        
        # Add to recognized_idps if any MFA method was detected
        if detected and not any(idp.get("idp_name") == "MFA_GENERIC" for idp in self.recognized_idps):
            self.recognized_idps.append({
                "idp_name": "MFA_GENERIC",
                "idp_integration": "MFA",
                "detection_method": "MFA",
                "login_page_candidate": page.url,
                "validity": "HIGH"
            })
        
        return detected
    
    def check_for_totp(self, page: Page) -> bool:
        """Check for TOTP indicators."""
        try:
            # Look for elements with keywords related to TOTP
            keywords = ["verification code", "authenticator", "TOTP", "one-time code", "6-digit code", "authentication code"]
            
            # Check for relevant text content
            pattern = "|".join(keywords)
            # Escape any special regex characters in pattern
            escaped_pattern = pattern.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            has_totp_text = page.evaluate(f"""
                () => {{
                    const pattern = new RegExp("{escaped_pattern}", "i");
                    const textElements = Array.from(document.querySelectorAll('label, span, p, h1, h2, h3, h4, h5, h6, div'));
                    
                    for (const elem of textElements) {{
                        if (pattern.test(elem.textContent)) {{
                            return true;
                        }}
                    }}
                    
                    return false;
                }}
            """)
            
            # Check for typical TOTP input fields (usually 6 digits, split into multiple fields)
            has_totp_fields = page.evaluate("""
                () => {
                    // Look for OTP input fields (usually 4-8 separate short inputs)
                    const shortInputs = Array.from(document.querySelectorAll('input[type="text"], input[type="number"], input[type="tel"]'))
                        .filter(input => {
                            const maxLength = input.getAttribute('maxlength');
                            return maxLength && parseInt(maxLength) <= 2;
                        });
                    
                    // If we have multiple short inputs (typically for code entry)
                    if (shortInputs.length >= 4 && shortInputs.length <= 8) {
                        return true;
                    }
                    
                    // Look for a single input field for verification code
                    const codeInputs = Array.from(document.querySelectorAll('input[type="text"], input[type="number"], input[type="tel"]'))
                        .filter(input => {
                            const maxLength = input.getAttribute('maxlength');
                            return maxLength && parseInt(maxLength) >= 4 && parseInt(maxLength) <= 10;
                        });
                        
                    // If the input has a name or id suggesting a verification code
                    for (const input of codeInputs) {
                        const inputId = (input.id || '').toLowerCase();
                        const inputName = (input.name || '').toLowerCase();
                        const inputPlaceholder = (input.placeholder || '').toLowerCase();
                        
                        if (inputId.includes('code') || inputId.includes('otp') || inputId.includes('totp') ||
                            inputName.includes('code') || inputName.includes('otp') || inputName.includes('totp') ||
                            inputPlaceholder.includes('code') || inputPlaceholder.includes('otp')) {
                            return true;
                        }
                    }
                    
                    return false;
                }
            """)
            
            if has_totp_text or has_totp_fields:
                logger.info("TOTP authentication detected")
                return True
                
            return False
        except Exception as e:
            logger.warning(f"Error while checking for TOTP: {e}")
            return False
    
    def check_for_sms(self, page: Page) -> bool:
        """Check for SMS verification indicators."""
        try:
            # Look for elements with keywords related to SMS verification
            keywords = ["text message", "SMS code", "phone verification", "mobile number", "sent to your phone", 
                       "mobile verification", "phone number verification"]
            
            # Check for relevant text content
            pattern = "|".join(keywords)
            # Escape any special regex characters in pattern
            escaped_pattern = pattern.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            has_sms_text = page.evaluate(f"""
                () => {{
                    const pattern = new RegExp("{escaped_pattern}", "i");
                    const textElements = Array.from(document.querySelectorAll('label, span, p, h1, h2, h3, h4, h5, h6, div'));
                    
                    for (const elem of textElements) {{
                        if (pattern.test(elem.textContent)) {{
                            return true;
                        }}
                    }}
                    
                    return false;
                }}
            """)
            
            # Check for phone input followed by verification code input
            has_phone_verification = page.evaluate("""
                () => {
                    // Look for phone input fields
                    const phoneInputs = Array.from(document.querySelectorAll('input[type="tel"], input[name*="phone"], input[id*="phone"]'));
                    if (phoneInputs.length === 0) return false;
                    
                    // Look for verification code inputs that might be used after phone number entry
                    const codeInputs = Array.from(document.querySelectorAll('input[type="text"], input[type="number"], input[type="tel"]'))
                        .filter(input => {
                            const maxLength = input.getAttribute('maxlength');
                            return maxLength && parseInt(maxLength) >= 4 && parseInt(maxLength) <= 10;
                        });
                    
                    return codeInputs.length > 0;
                }
            """)
            
            if has_sms_text or has_phone_verification:
                logger.info("SMS verification detected")
                return True
                
            return False
        except Exception as e:
            logger.warning(f"Error while checking for SMS verification: {e}")
            return False
    
    def check_for_email(self, page: Page) -> bool:
        """Check for email verification indicators."""
        try:
            # Look for elements with keywords related to email verification
            keywords = ["email code", "check your email", "verification link", "sent to your email", 
                       "email verification", "verify your email"]
            
            # Check for relevant text content
            pattern = "|".join(keywords)
            # Escape any special regex characters in pattern
            escaped_pattern = pattern.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            has_email_text = page.evaluate(f"""
                () => {{
                    const pattern = new RegExp("{escaped_pattern}", "i");
                    const textElements = Array.from(document.querySelectorAll('label, span, p, h1, h2, h3, h4, h5, h6, div'));
                    
                    for (const elem of textElements) {{
                        if (pattern.test(elem.textContent)) {{
                            return true;
                        }}
                    }}
                    
                    return false;
                }}
            """)
            
            # Check for email input followed by verification code input
            has_email_verification = page.evaluate("""
                () => {
                    // Look for email input fields
                    const emailInputs = Array.from(document.querySelectorAll('input[type="email"], input[name*="email"], input[id*="email"]'));
                    if (emailInputs.length === 0) return false;
                    
                    // Look for verification code inputs that might be used after email entry
                    const codeInputs = Array.from(document.querySelectorAll('input[type="text"], input[type="number"]'))
                        .filter(input => {
                            const maxLength = input.getAttribute('maxlength');
                            return maxLength && parseInt(maxLength) >= 4 && parseInt(maxLength) <= 10;
                        });
                    
                    return codeInputs.length > 0;
                }
            """)
            
            if has_email_text or has_email_verification:
                logger.info("Email verification detected")
                return True
                
            return False
        except Exception as e:
            logger.warning(f"Error while checking for email verification: {e}")
            return False
    
    def check_for_app(self, page: Page) -> bool:
        """Check for app-based verification indicators."""
        try:
            # Look for elements with keywords related to authentication apps
            keywords = ["approve in app", "authentication app", "google authenticator", "microsoft authenticator", 
                       "authy", "duo", "scan qr code", "approve the request", "push notification"]
            
            # Check for relevant text content
            pattern = "|".join(keywords)
            # Escape any special regex characters in pattern
            escaped_pattern = pattern.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            has_app_text = page.evaluate(f"""
                () => {{
                    const pattern = new RegExp("{escaped_pattern}", "i");
                    const textElements = Array.from(document.querySelectorAll('label, span, p, h1, h2, h3, h4, h5, h6, div'));
                    
                    for (const elem of textElements) {{
                        if (pattern.test(elem.textContent)) {{
                            return true;
                        }}
                    }}
                    
                    return false;
                }}
            """)
            
            # Check for QR codes that are typically used for app-based MFA
            has_qr_code = page.evaluate("""
                () => {
                    // Look for QR code images
                    const images = Array.from(document.querySelectorAll('img'));
                    for (const img of images) {
                        const alt = (img.alt || '').toLowerCase();
                        const src = (img.src || '').toLowerCase();
                        
                        if (alt.includes('qr') || alt.includes('scan') || 
                            src.includes('qrcode') || src.includes('authenticator')) {
                            return true;
                        }
                    }
                    
                    // Look for canvas elements that might contain QR codes
                    const canvases = document.querySelectorAll('canvas');
                    return canvases.length > 0;
                }
            """)
            
            if has_app_text or has_qr_code:
                logger.info("App-based authentication detected")
                return True
                
            return False
        except Exception as e:
            logger.warning(f"Error while checking for app-based verification: {e}")
            return False 
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

class PasskeyDetector:
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
        
        if "auth_methods" not in self.result:
            self.result["auth_methods"] = {}
        if "passkey" not in self.result["auth_methods"]:
            self.result["auth_methods"]["passkey"] = {"detected": False, "validity": "LOW"}

    def start(self):
        logger.info("Starting passkey detection")
        
        # targets: login page candidates
        lpcs_with_idps = {}
        
        # update login page candidates based on recognition mode
        DetectionHelper.get_lpcs_with_idps(
            lpcs_with_idps, self.login_page_candidates, self.recognized_idps,
            self.recognition_mode, self.idp_scope, False
        )
        
        for lpc in lpcs_with_idps:
            logger.info(f"Checking for passkey authentication on: {lpc}")
            
            # check if login page candidate is reachable and analyzable
            lpc_details = DetectionHelper.get_lpc_from_url(lpc, self.login_page_candidates)
            reachable = lpc_details.get("resolved", {}).get("reachable", False)
            valid = lpc_details.get("content_analyzable", {}).get("valid", False)
            
            if not reachable or not valid:
                logger.info(f"Login page candidate is not reachable or analyzable: {lpc}")
                continue
            
            detected = self.detect_passkey_elements(lpc)
            if detected:
                # Update auth_methods
                self.result["auth_methods"]["passkey"]["detected"] = True
                self.result["auth_methods"]["passkey"]["validity"] = "HIGH"
                
                # Add to recognized_idps explicitly
                if not any(idp.get("idp_name") == "PASSKEY" for idp in self.recognized_idps):
                    self.recognized_idps.append({
                        "idp_name": "PASSKEY",
                        "idp_integration": "WEBAUTHN",
                        "detection_method": "PASSKEY_BUTTON",
                        "login_page_candidate": lpc,
                        "validity": "HIGH"
                    })
                return
                
    def detect_passkey_elements(self, url: str) -> bool:
        """Detect passkey elements on the page."""
        with TmpHelper.tmp_dir() as pdir, sync_playwright() as pw:
            context, page = PlaywrightBrowser.instance(pw, self.browser_config, pdir)
            
            try:
                # Navigate to page
                PlaywrightHelper.navigate(page, url, self.browser_config)
                
                # Check for WebAuthn API usage
                webauthn_detected = self.detect_webauthn_api(page)
                
                # Check for passkey-related UI elements
                passkey_ui_detected = self.detect_passkey_ui_elements(page)
                
                # Close browser
                PlaywrightHelper.close_context(context)
                
                return webauthn_detected or passkey_ui_detected
                
            except TimeoutError as e:
                logger.warning(f"Timeout in passkey detection on: {url}")
                logger.debug(e)
                return False
            
            except Error as e:
                logger.warning(f"Error in passkey detection on: {url}")
                logger.debug(e)
                return False
    
    def detect_webauthn_api(self, page: Page) -> bool:
        """Monitor for WebAuthn API calls."""
        try:
            # Check if navigator.credentials API is used
            has_webauthn_api = page.evaluate("""
                () => {
                    return (
                        typeof window.PublicKeyCredential !== 'undefined' &&
                        typeof navigator.credentials !== 'undefined' &&
                        typeof navigator.credentials.create === 'function' &&
                        typeof navigator.credentials.get === 'function'
                    );
                }
            """)
            
            if has_webauthn_api:
                logger.info("WebAuthn API detected on page")
                return True
                
            return False
        except Exception as e:
            logger.warning(f"Error while detecting WebAuthn API: {e}")
            return False
    
    def detect_passkey_ui_elements(self, page: Page) -> bool:
        """Look for UI elements indicating passkey support."""
        try:
            # Check for passkey-related text or buttons
            passkey_keywords = IdpRules["PASSKEY"]["keywords"]
            
            # Convert keywords to regex pattern
            pattern = "|".join(passkey_keywords)
            
            # Search for these keywords in button text, labels, etc.
            has_passkey_elements = page.evaluate(f"""
                () => {{
                    const pattern = new RegExp("({pattern})", "i");
                    
                    // Check button texts
                    const buttons = Array.from(document.querySelectorAll('button, a.btn, [role="button"], input[type="button"], input[type="submit"]'));
                    for (const button of buttons) {{
                        if (pattern.test(button.textContent) || pattern.test(button.value)) {{
                            return true;
                        }}
                    }}
                    
                    // Check for labels and spans that might indicate passkey support
                    const textElements = Array.from(document.querySelectorAll('label, span, p, h1, h2, h3, h4, h5, h6, div'));
                    for (const elem of textElements) {{
                        if (pattern.test(elem.textContent)) {{
                            return true;
                        }}
                    }}
                    
                    // Check for images with passkey-related alt text
                    const images = Array.from(document.querySelectorAll('img'));
                    for (const img of images) {{
                        if (pattern.test(img.alt)) {{
                            return true;
                        }}
                    }}
                    
                    return false;
                }}
            """)
            
            if has_passkey_elements:
                logger.info("Passkey UI elements detected on page")
                return True
                
            return False
        except Exception as e:
            logger.warning(f"Error while detecting passkey UI elements: {e}")
            return False 
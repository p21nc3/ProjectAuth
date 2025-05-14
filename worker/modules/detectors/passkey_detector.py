import logging
import time
from typing import Tuple, List
from playwright.sync_api import Page
from modules.browser.browser import PlaywrightHelper
from modules.helper.detection import DetectionHelper
from config.idp_rules import IdpRules

logger = logging.getLogger(__name__)

class PasskeyDetector:
    """
    Detector for Passkey buttons, text references, and elements
    """

    def __init__(self, result: dict, page: Page):
        self.result = result
        self.page = page
        self.url = None
        self.passkey_keywords = IdpRules["PASSKEY BUTTON"]["keywords"]

    def detect_passkey_button(self, url: str) -> Tuple[bool, dict]:
        """
        Detects passkey buttons or links on the current page
        """
        logger.info(f"Checking for passkey buttons on: {url}")
        self.url = url
        
        # Check if this URL already has a passkey detection to avoid duplicates
        for idp in self.result.get("recognized_idps", []):
            if (idp.get("idp_name") == "PASSKEY BUTTON" and 
                idp.get("login_page_url") == url and 
                idp.get("detection_method") in ["PASSKEY-BUTTON", "PASSKEY-KEYWORD"]):
                logger.info(f"Passkey already detected for {url}, skipping")
                return False, None
        
        # Look for buttons with passkey text
        passkey_found, passkey_type = self._detect_passkey_ui_elements()
        if passkey_found:
            logger.info(f"PASSKEY BUTTON detected with type: {passkey_type}")
            passkey_info = {
                "idp_name": "PASSKEY BUTTON",
                "idp_sdk": passkey_type,
                "idp_integration": "CUSTOM",
                "idp_frame": "SAME_WINDOW",
                "login_page_url": self.url,
                "element_validity": "HIGH",
                "detection_method": "PASSKEY-BUTTON",
                "passkey_type": passkey_type
            }
            return True, passkey_info

        # Look for passkey text mentions
        passkey_text_found, passkey_text_type = self._detect_passkey_text()
        if passkey_text_found:
            logger.info(f"Passkey text detected with type: {passkey_text_type}")
            passkey_info = {
                "idp_name": "PASSKEY KEYWORD",
                "idp_sdk": passkey_text_type,
                "idp_integration": "CUSTOM",
                "idp_frame": "SAME_WINDOW",
                "login_page_url": self.url,
                "element_validity": "MEDIUM",
                "detection_method": "PASSKEY-KEYWORD",
                "passkey_type": passkey_text_type
            }
            return True, passkey_info
        
        # Look for hidden passkey elements
        hidden_found, hidden_type = self._detect_hidden_passkey_elements()
        if hidden_found:
            logger.info(f"Hidden passkey element detected with type: {hidden_type}")
            passkey_info = {
                "idp_name": "PASSKEY BUTTON",
                "idp_sdk": hidden_type,
                "idp_integration": "CUSTOM",
                "idp_frame": "SAME_WINDOW",
                "login_page_url": self.url,
                "element_validity": "MEDIUM",
                "detection_method": "PASSKEY-HIDDEN",
                "passkey_type": hidden_type
            }
            return True, passkey_info
            
        return False, None

    def _detect_passkey_ui_elements(self) -> Tuple[bool, str]:
        """
        Detect UI elements like buttons or links related to passkeys
        """
        # Button selectors for passkey
        button_selectors = []
        for keyword in self.passkey_keywords:
            # Create selectors for buttons, links and divs with passkey text
            button_selectors.extend([
                f'button:has-text("{keyword}")',
                f'a:has-text("{keyword}")',
                f'div[role="button"]:has-text("{keyword}")',
                f'[aria-label*="{keyword}" i]',
                f'[title*="{keyword}" i]',
                f'label:has-text("{keyword}")',
                f'span:has-text("{keyword}")',
                f'p:has-text("{keyword}")'
            ])
        
        # Additional selectors for common passkey UI patterns
        button_selectors.extend([
            'img[alt*="passkey" i]',
            'img[alt*="face id" i]',
            'img[alt*="touch id" i]',
            'img[alt*="fingerprint" i]',
            'img[alt*="biometric" i]',
            'img[alt*="security key" i]',
            '[data-testid*="passkey" i]',
            '[data-test*="passkey" i]',
            '[data-testid*="biometric" i]',
            '[data-testid*="faceId" i]',
            '[data-testid*="touchId" i]',
            '[data-testid*="fingerprint" i]',
            '[class*="passkey" i]',
            '[class*="biometric" i]',
            '[class*="faceId" i]',
            '[class*="touchId" i]',
            '[class*="fingerprint" i]',
            '[id*="passkey" i]',
            '[id*="biometric" i]',
            '[id*="faceId" i]',
            '[id*="touchId" i]',
            '[id*="fingerprint" i]',
            # Icons that might indicate passkeys
            'svg[aria-label*="face" i]',
            'svg[aria-label*="touch" i]',
            'svg[aria-label*="fingerprint" i]',
            'svg[aria-label*="security key" i]',
            'svg[aria-label*="passkey" i]',
            'svg[aria-label*="biometric" i]'
        ])
        
        found_elements = []
        
        for selector in button_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                if elements:
                    logger.debug(f"Found {len(elements)} passkey UI elements with selector: {selector}")
                    found_elements.extend(elements)
                    
                    # Check if this is a specific platform passkey
                    if "face id" in selector.lower() or "touch id" in selector.lower():
                        return True, "APPLE"
                    elif "fingerprint" in selector.lower():
                        return True, "ANDROID"
                    else:
                        return True, "WEBAUTHN"
            except Exception as e:
                logger.debug(f"Error finding passkey UI element with selector {selector}: {e}")
        
        # If we've found UI elements but didn't return yet, try to determine the passkey type
        if found_elements:
            # Look at the elements and try to determine what type of passkey
            for element in found_elements:
                try:
                    element_text = element.inner_text().lower()
                    element_html = element.outer_html().lower()
                    
                    # Check for Apple-specific indicators
                    if any(term in element_text or term in element_html for term in ["face id", "touch id", "apple"]):
                        return True, "WEBAUTHN"
                    
                    # Check for Android-specific indicators
                    if any(term in element_text or term in element_html for term in ["fingerprint", "android"]):
                        return True, "WEBAUTHN"
                    
                    # Otherwise consider it a generic WebAuthn passkey
                    return True, "WEBAUTHN"
                except Exception as e:
                    logger.debug(f"Error analyzing passkey element: {e}")
            
            # Default if we can't determine specifics
            return True, "WEBAUTHN"
                
        return False, ""

    def _detect_passkey_text(self) -> Tuple[bool, str]:
        """
        Detect text on the page indicating passkey support
        """
        try:
            page_text = self.page.content().lower()
            
            # Look for script references to passkey/webauthn APIs
            script_indicators = [
                "publickey", 
                "navigator.credentials.create", 
                "navigator.credentials.get",
                "PublicKeyCredential"
            ]
            
            for indicator in script_indicators:
                if indicator in page_text:
                    logger.debug(f"Found passkey API reference in page: {indicator}")
                    return True, "WEBAUTHN"
            
            # Check for passkey-related text in the page content
            apple_indicators = ["face id", "touch id", "apple passkey"]
            android_indicators = ["fingerprint", "android passkey"]
            general_indicators = ["passkey", "passwordless"]
            
            # Check for specific buttons or links that suggest passkey functionality
            passkey_buttons = [
                "use passkey", 
                "use a passkey", 
                "sign in with passkey", 
                "sign in with a passkey",
                "log in with passkey",
                "log in with a passkey",
                "sign in with fingerprint",
                "continue with passkey", 
                "use face id",
                "use touch id", 
                "use fingerprint", 
                "use biometrics",
                "biometric login", 
                "biometric sign in"
            ]
            
            # Look for passkey buttons first
            for button_text in passkey_buttons:
                # More specific search - look for this text in buttons or links specifically
                try:
                    button_elements = self.page.query_selector_all(f'button, a, [role="button"]')
                    for button in button_elements:
                        button_inner_text = button.inner_text().lower()
                        if button_text in button_inner_text:
                            logger.debug(f"Found PASSKEY BUTTON with text: {button_inner_text}")
                            if any(apple_term in button_inner_text for apple_term in ["face id", "touch id"]):
                                return True, "WEBAUTHN"
                            elif "fingerprint" in button_inner_text:
                                return True, "WEBAUTHN"
                            else:
                                return True, "WEBAUTHN"
                except Exception as e:
                    logger.debug(f"Error searching for passkey buttons: {e}")
            
            # Check for Apple-specific indicators
            for indicator in apple_indicators:
                if indicator in page_text:
                    return True, "WEBAUTHN"
                    
            # Check for Android-specific indicators
            for indicator in android_indicators:
                if indicator in page_text:
                    return True, "WEBAUTHN"
                    
            # Check for general passkey indicators
            for indicator in general_indicators:
                if indicator in page_text:
                    return True, "WEBAUTHN"
                    
        except Exception as e:
            logger.debug(f"Error detecting passkey text: {e}")
            
        return False, ""

    def _detect_hidden_passkey_elements(self) -> Tuple[bool, str]:
        """
        Detect hidden elements related to passkeys that may not be visible on the page
        """
        try:
            # Build selectors for hidden elements that might contain passkey-related content
            hidden_selectors = []
            
            # Add selectors for elements with passkey-related attributes but might be hidden
            for keyword in self.passkey_keywords:
                hidden_selectors.extend([
                    # Selectors for hidden but labeled elements
                    f'[style*="display: none"]:has-text("{keyword}")',
                    f'[style*="visibility: hidden"]:has-text("{keyword}")',
                    f'[hidden]:has-text("{keyword}")',
                    f'[aria-hidden="true"]:has-text("{keyword}")',
                    f'.hidden:has-text("{keyword}")',
                    f'.d-none:has-text("{keyword}")',
                    f'.invisible:has-text("{keyword}")',
                    # Data attributes often used for dynamic content
                    f'[data-*="{keyword}" i]',
                    # Elements with various class/ID naming patterns
                    f'[class*="{keyword}" i]',
                    f'[id*="{keyword}" i]',
                    # Look in script tags for passkey references
                    f'script:contains("{keyword}")'
                ])
            
            # Add specific selectors for common hidden passkey element patterns
            hidden_selectors.extend([
                # Elements with WebAuthn/passkey related classes or IDs that might be hidden
                '[id*="webauthn"][style*="display: none"]',
                '[id*="passkey"][style*="display: none"]',
                '[class*="webauthn"][style*="display: none"]',
                '[class*="passkey"][style*="display: none"]',
                '[id*="webauthn"][hidden]',
                '[id*="passkey"][hidden]',
                '[class*="webauthn"][hidden]',
                '[class*="passkey"][hidden]',
                '[id*="webauthn"][aria-hidden="true"]',
                '[id*="passkey"][aria-hidden="true"]',
                '[class*="webauthn"][aria-hidden="true"]',
                '[class*="passkey"][aria-hidden="true"]',
                # Hidden template elements that might contain passkey UI
                'template:has-text("passkey")',
                'template:has-text("webauthn")',
                'template:has-text("fingerprint")',
                'template:has-text("face id")',
                'template:has-text("touch id")',
                # WebAuthn API calls in script tags
                'script:contains("navigator.credentials")',
                'script:contains("PublicKeyCredential")',
                'script:contains("authenticator")'
            ])
            
            # Check for hidden passkey elements
            for selector in hidden_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    if elements:
                        logger.debug(f"Found {len(elements)} hidden passkey elements with selector: {selector}")
                        
                        # Check if this is a specific platform passkey
                        if "face id" in selector.lower() or "touch id" in selector.lower():
                            return True, "WEBAUTHN"
                        elif "fingerprint" in selector.lower():
                            return True, "WEBAUTHN"
                        else:
                            return True, "WEBAUTHN"
                except Exception as e:
                    logger.debug(f"Error finding hidden passkey element with selector {selector}: {e}")
            
            # Run a JavaScript evaluation to find hidden elements with passkey text
            # This can find elements that might be dynamically inserted or styled to be invisible
            try:
                passkey_keywords_js = '|'.join(self.passkey_keywords).lower()
                hidden_elements_check = self.page.evaluate(f'''() => {{
                    // Get all elements in the DOM
                    const allElements = document.querySelectorAll('*');
                    
                    // Keywords to look for
                    const keywords = /{passkey_keywords_js}/i;
                    
                    // Check each element
                    for (const elem of allElements) {{
                        // Skip elements that are normally visible
                        const style = window.getComputedStyle(elem);
                        const isHidden = style.display === 'none' || 
                                       style.visibility === 'hidden' || 
                                       elem.hasAttribute('hidden') || 
                                       elem.getAttribute('aria-hidden') === 'true';
                        
                        if (isHidden) {{
                            // Check if it contains passkey-related text
                            const text = elem.innerText || elem.textContent || '';
                            if (keywords.test(text.toLowerCase())) {{
                                return true;
                            }}
                            
                            // Check attributes that might contain passkey keywords
                            const attrs = ['id', 'class', 'name', 'data-testid', 'aria-label', 'title'];
                            for (const attr of attrs) {{
                                const value = elem.getAttribute(attr);
                                if (value && keywords.test(value.toLowerCase())) {{
                                    return true;
                                }}
                            }}
                        }}
                    }}
                    
                    return false;
                }}''')
                
                if hidden_elements_check:
                    logger.debug("Found hidden passkey elements via JavaScript evaluation")
                    return True, "WEBAUTHN"
                
            except Exception as e:
                logger.debug(f"Error in JavaScript evaluation for hidden passkey elements: {e}")
                
            return False, ""
        except Exception as e:
            logger.debug(f"Error detecting hidden passkey elements: {e}")
            return False, ""

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
        self.passkey_keywords = IdpRules["PASSKEY"]["keywords"]

    def detect_passkey_button(self, url: str) -> Tuple[bool, dict]:
        """
        Detects passkey buttons or links on the current page
        """
        logger.info(f"Checking for passkey buttons on: {url}")
        self.url = url
        
        # Look for buttons with passkey text
        passkey_found, passkey_type = self._detect_passkey_ui_elements()
        if passkey_found:
            logger.info(f"Passkey button detected with type: {passkey_type}")
            passkey_info = {
                "idp_name": "PASSKEY",
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
                "idp_name": "PASSKEY",
                "idp_sdk": passkey_text_type,
                "idp_integration": "CUSTOM",
                "idp_frame": "SAME_WINDOW",
                "login_page_url": self.url,
                "element_validity": "MEDIUM",
                "detection_method": "PASSKEY-KEYWORD",
                "passkey_type": passkey_text_type
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
                f'[aria-label*="{keyword}" i]'
            ])
        
        # Additional selectors for common passkey UI patterns
        button_selectors.extend([
            'img[alt*="passkey" i]',
            'img[alt*="face id" i]',
            'img[alt*="touch id" i]',
            'img[alt*="fingerprint" i]',
            '[data-testid*="passkey" i]',
            '[data-test*="passkey" i]'
        ])
        
        for selector in button_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                if elements:
                    logger.debug(f"Found {len(elements)} passkey UI elements with selector: {selector}")
                    # Check if this is a specific platform passkey
                    if "face id" in selector.lower() or "touch id" in selector.lower():
                        return True, "APPLE"
                    elif "fingerprint" in selector.lower():
                        return True, "ANDROID"
                    else:
                        return True, "WEBAUTHN"
            except Exception as e:
                logger.debug(f"Error finding passkey UI element with selector {selector}: {e}")
                
        return False, ""

    def _detect_passkey_text(self) -> Tuple[bool, str]:
        """
        Detect text on the page indicating passkey support
        """
        try:
            page_text = self.page.content().lower()
            
            # Check for passkey-related text in the page content
            apple_indicators = ["face id", "touch id", "apple passkey"]
            android_indicators = ["fingerprint", "android passkey"]
            general_indicators = ["passkey", "passwordless", "no password", "security key", "webauthn"]
            
            for indicator in apple_indicators:
                if indicator in page_text:
                    return True, "APPLE"
                    
            for indicator in android_indicators:
                if indicator in page_text:
                    return True, "ANDROID"
                    
            for indicator in general_indicators:
                if indicator in page_text:
                    return True, "WEBAUTHN"
                    
        except Exception as e:
            logger.debug(f"Error detecting passkey text: {e}")
            
        return False, "" 
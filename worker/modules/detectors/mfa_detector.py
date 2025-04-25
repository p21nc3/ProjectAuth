import logging
import time
from typing import Tuple, List
from playwright.sync_api import Page
from modules.browser.browser import PlaywrightHelper
from modules.helper.detection import DetectionHelper
from config.idp_rules import IdpRules

logger = logging.getLogger(__name__)

class MFADetector:
    """
    Detector for MFA/2FA authentication methods including TOTP, SMS, Email, QR codes
    """

    def __init__(self, result: dict, page: Page):
        self.result = result
        self.page = page
        self.url = None
        self.mfa_keywords = IdpRules["MFA_GENERIC"]["keywords"]

    def detect_mfa(self, url: str) -> Tuple[bool, dict]:
        """
        Detects MFA/2FA flows on the current page
        """
        logger.info(f"Checking for MFA/2FA on: {url}")
        self.url = url
        
        # First try to detect OTP input fields
        otp_input_found, otp_type = self._detect_otp_inputs()
        if otp_input_found:
            logger.info(f"MFA detected with OTP input fields of type: {otp_type}")
            mfa_info = {
                "idp_name": "MFA_GENERIC",
                "idp_sdk": otp_type,
                "idp_integration": "CUSTOM",
                "idp_frame": "SAME_WINDOW",
                "login_page_url": self.url,
                "element_validity": "HIGH",
                "detection_method": "MFA-FIELD",
                "mfa_type": otp_type
            }
            return True, mfa_info

        # Then try to detect MFA keywords on the page
        mfa_text_found, mfa_text_type = self._detect_mfa_text()
        if mfa_text_found:
            logger.info(f"MFA detected with text indicators of type: {mfa_text_type}")
            mfa_info = {
                "idp_name": "MFA_GENERIC",
                "idp_sdk": mfa_text_type,
                "idp_integration": "CUSTOM",
                "idp_frame": "SAME_WINDOW",
                "login_page_url": self.url,
                "element_validity": "MEDIUM",
                "detection_method": "MFA-KEYWORD",
                "mfa_type": mfa_text_type
            }
            return True, mfa_info

        # Finally check for QR code images
        qr_found = self._detect_qr_code()
        if qr_found:
            logger.info(f"MFA detected with QR code")
            mfa_info = {
                "idp_name": "MFA_GENERIC",
                "idp_sdk": "QR",
                "idp_integration": "CUSTOM",
                "idp_frame": "SAME_WINDOW",
                "login_page_url": self.url,
                "element_validity": "MEDIUM",
                "detection_method": "MFA-QR",
                "mfa_type": "QR"
            }
            return True, mfa_info
            
        return False, None

    def _detect_otp_inputs(self) -> Tuple[bool, str]:
        """
        Detect OTP input fields that suggest MFA/2FA
        """
        # Look for common OTP input patterns
        otp_selectors = [
            'input[autocomplete="one-time-code"]',
            'input[name="otp"]',
            'input[name="verificationCode"]',
            'input[name="code"]',
            'input[placeholder*="verification code" i]',
            'input[placeholder*="code" i][maxlength="6"]',
            'input[aria-label*="verification code" i]',
        ]
        
        # Common patterns for segmented OTP inputs (e.g., 6 separate boxes for a 6-digit code)
        segmented_otp_selectors = [
            'input[maxlength="1"]',
            'div[class*="otp"] input[maxlength="1"]',
            'div[class*="verification"] input[maxlength="1"]'
        ]
        
        # Check for standard OTP inputs
        for selector in otp_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                if elements:
                    logger.debug(f"Found {len(elements)} OTP input elements with selector: {selector}")
                    # Determine the type of MFA
                    return True, self._determine_mfa_type()
            except Exception as e:
                logger.debug(f"Error finding OTP input with selector {selector}: {e}")
        
        # Check for segmented OTP inputs
        for selector in segmented_otp_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                # Typically segmented inputs have 4-8 boxes
                if elements and len(elements) >= 4:
                    logger.debug(f"Found {len(elements)} segmented OTP input elements with selector: {selector}")
                    return True, self._determine_mfa_type()
            except Exception as e:
                logger.debug(f"Error finding segmented OTP input with selector {selector}: {e}")
                
        return False, ""

    def _detect_mfa_text(self) -> Tuple[bool, str]:
        """
        Detect text on the page indicating MFA/2FA
        """
        # Get the page text
        try:
            page_text = self.page.content().lower()
            
            # Check for specific MFA indicators in the text
            totp_indicators = ["authenticator app", "google authenticator", "microsoft authenticator", "authy", "totp"]
            sms_indicators = ["text message", "sms", "sent to your phone", "phone number"]
            email_indicators = ["email code", "sent to your email", "check your inbox"]
            
            for indicator in totp_indicators:
                if indicator in page_text:
                    return True, "TOTP"
                    
            for indicator in sms_indicators:
                if indicator in page_text:
                    return True, "SMS"
                    
            for indicator in email_indicators:
                if indicator in page_text:
                    return True, "EMAIL"
            
            # General MFA indicators if specific type not found
            general_indicators = self.mfa_keywords
            for indicator in general_indicators:
                if indicator in page_text:
                    return True, "CUSTOM"
                    
        except Exception as e:
            logger.debug(f"Error detecting MFA text: {e}")
            
        return False, ""

    def _detect_qr_code(self) -> bool:
        """
        Detect QR code images on the page
        """
        qr_selectors = [
            'img[alt*="qr" i]',
            'img[src*="qr" i]',
            'img[class*="qr" i]',
            'canvas[id*="qr" i]',
            'div[class*="qr" i]'
        ]
        
        for selector in qr_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                if elements:
                    logger.debug(f"Found {len(elements)} potential QR code elements with selector: {selector}")
                    return True
            except Exception as e:
                logger.debug(f"Error finding QR code with selector {selector}: {e}")
                
        return False

    def _determine_mfa_type(self) -> str:
        """
        Determine the type of MFA based on page context
        """
        try:
            page_text = self.page.content().lower()
            
            if any(keyword in page_text for keyword in ["authenticator", "totp", "google authenticator", "microsoft authenticator", "authy"]):
                return "TOTP"
            elif any(keyword in page_text for keyword in ["sms", "text message", "phone"]):
                return "SMS"
            elif any(keyword in page_text for keyword in ["email", "inbox"]):
                return "EMAIL"
            elif any(keyword in page_text for keyword in ["qr", "scan"]):
                return "QR"
            else:
                return "CUSTOM"
        except Exception as e:
            logger.debug(f"Error determining MFA type: {e}")
            return "CUSTOM" 
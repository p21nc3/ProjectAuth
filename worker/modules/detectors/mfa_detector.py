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
        
        # Check if this URL already has an MFA detection to avoid duplicates
        for idp in self.result.get("recognized_idps", []):
            if (idp.get("idp_name") == "MFA_GENERIC" and 
                idp.get("login_page_url") == url):
                logger.info(f"MFA already detected for {url}, skipping")
                return False, None
        
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
        # Check page context first to ensure we're looking at verification, not passkeys
        try:
            page_text = self.page.content().lower()
            mfa_context_present = any(phrase in page_text for phrase in [
                "verification code", 
                "security code", 
                "one-time code",
                "2fa code",
                "enter the code",
                "enter code sent"
            ])
            
            # If no clear MFA verification context, be more cautious
            if not mfa_context_present:
                # Check for specific text that clearly indicates we're in an MFA flow
                # and not another security mechanism
                mfa_headers = [
                    'h1, h2, h3, h4, h5, h6, [role="heading"]'
                ]
                
                mfa_header_found = False
                for selector in mfa_headers:
                    elements = self.page.query_selector_all(selector)
                    for element in elements:
                        header_text = element.inner_text().lower()
                        if any(phrase in header_text for phrase in [
                            "two-factor", 
                            "2-factor", 
                            "verification", 
                            "verify your identity",
                            "additional security",
                            "security step"
                        ]):
                            mfa_header_found = True
                            break
                    if mfa_header_found:
                        break
                
                # If we don't have a clear MFA context or header, be extra cautious with detection
                if not mfa_header_found:
                    logger.debug("No clear MFA context found, being more cautious with detection")
        except Exception as e:
            logger.debug(f"Error checking page context: {e}")
            mfa_context_present = True  # Default to less cautious if we can't check

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
                    
                    # Additional validation for non-specific selectors to reduce false positives
                    if selector in ['input[name="code"]', 'input[placeholder*="code" i][maxlength="6"]'] and not mfa_context_present:
                        # For general selectors, validate the element is actually for OTP
                        # by checking surrounding labels/text
                        valid_elements = []
                        for element in elements:
                            # Try to get label or surrounding text
                            try:
                                # Check nearby text for MFA context
                                element_rect = element.bounding_box()
                                surrounding_elements = self.page.query_selector_all(
                                    'label, div, p, span'
                                )
                                for surr_el in surrounding_elements:
                                    surr_rect = surr_el.bounding_box()
                                    # Check if element is close to our input (within 100px)
                                    if (surr_rect and element_rect and 
                                        abs(surr_rect['x'] - element_rect['x']) < 150 and
                                        abs(surr_rect['y'] - element_rect['y']) < 100):
                                        surr_text = surr_el.inner_text().lower()
                                        if any(term in surr_text for term in [
                                            "verification", "code", "two-factor",
                                            "2fa", "security", "authentication"
                                        ]):
                                            valid_elements.append(element)
                                            break
                            except Exception as e:
                                logger.debug(f"Error checking element context: {e}")
                        
                        if valid_elements:
                            logger.debug(f"Found {len(valid_elements)} validated OTP elements")
                            return True, self._determine_mfa_type()
                    else:
                        # For specific OTP selectors, we can be more confident
                        return True, self._determine_mfa_type()
            except Exception as e:
                logger.debug(f"Error finding OTP input with selector {selector}: {e}")
        
        # Check for segmented OTP inputs only if we have MFA context
        # These can be false positives for other input types
        if mfa_context_present:
            for selector in segmented_otp_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    # Typically segmented inputs have 4-8 boxes
                    if elements and len(elements) >= 4:
                        logger.debug(f"Found {len(elements)} segmented OTP input elements with selector: {selector}")
                        
                        # Additional check - verify these inputs are arranged horizontally
                        # and have similar y-positions (indicating a code input row)
                        if len(elements) >= 4:
                            try:
                                y_positions = []
                                for element in elements:
                                    box = element.bounding_box()
                                    if box:
                                        y_positions.append(box['y'])
                                
                                # If y positions are within 10px of each other, they're likely in a row
                                if y_positions and max(y_positions) - min(y_positions) < 10:
                                    return True, self._determine_mfa_type()
                            except Exception as e:
                                logger.debug(f"Error checking segmented input arrangement: {e}")
                        else:
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
            
            # More specific SMS indicators tied to verification/MFA context
            sms_indicators = [
                "verification code via sms", 
                "verification code by text", 
                "send code to your phone",
                "code sent to your phone",
                "text message with a code",
                "sms verification code",
                "sms code",
                "verification code by sms",
                "security code via text",
                "one-time code via sms"
            ]
            
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
            
            # Only use general MFA indicators if they're clearly related to verification
            # and not potentially part of passkey descriptions
            mfa_specific_indicators = [
                "enter verification code",
                "enter the code sent",
                "verification code input", 
                "enter one-time code",
                "enter security code",
                "2-step verification code",
                "two factor code",
                "2fa code"
            ]
            
            for indicator in mfa_specific_indicators:
                if indicator in page_text:
                    return True, "CUSTOM"
            
            # For general MFA keywords, check more carefully to avoid false positives
            # Only detect if they're used in a clear verification context
            for indicator in self.mfa_keywords:
                # Skip very general terms that might appear in passkey contexts
                if indicator in ["2fa", "mfa", "two-factor", "multi-factor"]:
                    # These need to be in a verification context
                    verification_context = any(ctx in page_text for ctx in [
                        "enter code", "input code", "verification step", 
                        "additional step", "second step"
                    ])
                    if indicator in page_text and verification_context:
                        return True, "CUSTOM"
                # For more specific indicators, we can trust them more
                elif indicator in page_text:
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
            # More specific SMS detection that requires clear MFA context
            elif any(phrase in page_text for phrase in [
                "verification code via sms", 
                "verification code by text", 
                "send code to your phone",
                "code sent to your phone",
                "text message with a code",
                "sms verification code",
                "sms code",
                "security code via text"
            ]):
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
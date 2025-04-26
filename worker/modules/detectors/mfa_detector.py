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
        # Add negative indicators - contexts where OTP-like inputs are likely not MFA
        self.negative_indicators = [
            "password",
            "sign up",
            "register",
            "create account",
            "passkey",
            "reset password",
            "zip code",
            "postal code",
            "credit card",
            "pin",
            "ssn",
            "social security"
        ]

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
                
        # Check for negative indicators first - if present, be extra cautious
        page_text = self.page.content().lower()
        has_negative_indicators = any(indicator in page_text for indicator in self.negative_indicators)
        
        # If negative indicators are present, we need at least two strong signals to confirm MFA
        required_signals = 2 if has_negative_indicators else 1
        signals_found = 0
        mfa_type = None
        detection_method = None
        
        # First check if we're in a clear MFA context
        strong_mfa_context = self._has_strong_mfa_context()
        if strong_mfa_context:
            signals_found += 1
            
        # Try to detect OTP input fields with high confidence
        otp_input_found, otp_confidence, otp_type = self._detect_otp_inputs()
        if otp_input_found:
            if otp_confidence == "HIGH" or (otp_confidence == "MEDIUM" and strong_mfa_context):
                signals_found += 1
                mfa_type = otp_type
                detection_method = "MFA-FIELD"

        # If we haven't found enough signals, try to detect MFA keywords on the page
        if signals_found < required_signals:
            mfa_text_found, mfa_confidence, mfa_text_type = self._detect_mfa_text()
            if mfa_text_found:
                if mfa_confidence == "HIGH" or (mfa_confidence == "MEDIUM" and strong_mfa_context):
                    signals_found += 1
                    if not mfa_type:  # Only set if not already set by OTP detection
                        mfa_type = mfa_text_type
                        detection_method = "MFA-KEYWORD"

        # Finally check for QR code images only if we have supporting context
        if signals_found < required_signals and strong_mfa_context:
            qr_found = self._detect_qr_code()
            if qr_found:
                signals_found += 1
                if not mfa_type:  # Only set if not already set
                    mfa_type = "QR"
                    detection_method = "MFA-QR"
        
        # Only report MFA if we found enough signals
        if signals_found >= required_signals:
            logger.info(f"MFA detected with {signals_found} signals, type: {mfa_type}")
            element_validity = "HIGH" if signals_found > 1 else "MEDIUM"
            
            mfa_info = {
                "idp_name": "MFA_GENERIC",
                "idp_sdk": mfa_type or "CUSTOM",
                "idp_integration": "CUSTOM",
                "idp_frame": "SAME_WINDOW",
                "login_page_url": self.url,
                "element_validity": element_validity,
                "detection_method": detection_method or "MFA-CONTEXT",
                "mfa_type": mfa_type or "CUSTOM"
            }
            return True, mfa_info
            
        return False, None

    def _has_strong_mfa_context(self) -> bool:
        """
        Check if the page has clear indicators of being in an MFA flow
        """
        try:
            page_text = self.page.content().lower()
            
            # Strong MFA context phrases that are very unlikely in non-MFA flows
            strong_indicators = [
                "two-factor authentication",
                "2-factor authentication", 
                "multi-factor authentication",
                "two-step verification",
                "2-step verification",
                "additional security step",
                "verify your identity",
                "authentication code"
            ]
            
            # Check page text for strong indicators
            for indicator in strong_indicators:
                if indicator in page_text:
                    logger.debug(f"Found strong MFA indicator: {indicator}")
                    return True
                    
            # Check headings specifically
            mfa_headers = [
                'h1, h2, h3, h4, h5, h6, [role="heading"]'
            ]
            
            for selector in mfa_headers:
                elements = self.page.query_selector_all(selector)
                for element in elements:
                    header_text = element.inner_text().lower()
                    if any(phrase in header_text for phrase in [
                        "two-factor", 
                        "2-factor",
                        "verification code", 
                        "verify your identity",
                        "security verification",
                        "additional security"
                    ]):
                        logger.debug(f"Found MFA heading: {header_text}")
                        return True
            
            # Check for presence of explanatory text about verification codes
            verification_context = any(ctx in page_text for ctx in [
                "we sent a code to your",
                "enter the code we sent",
                "verification code sent",
                "check your phone for a code",
                "check your email for a code",
                "use your authenticator app"
            ])
            
            if verification_context:
                logger.debug("Found verification context explaining code delivery")
                return True
                
            return False
            
        except Exception as e:
            logger.debug(f"Error checking MFA context: {e}")
            return False

    def _detect_otp_inputs(self) -> Tuple[bool, str, str]:
        """
        Detect OTP input fields that suggest MFA/2FA
        Returns: (found, confidence, type)
        """
        # Check page context first to ensure we're looking at verification, not passkeys
        try:
            page_text = self.page.content().lower()
            
            # Check for negative indicators that suggest non-MFA contexts
            for indicator in self.negative_indicators:
                if indicator in page_text:
                    logger.debug(f"Found negative indicator: {indicator}")
                    # Don't return early, but we'll require stronger evidence
            
            # High-confidence OTP selectors (very specific to MFA flows)
            high_confidence_selectors = [
                'input[autocomplete="one-time-code"]',
                'input[name="otp"]',
                'input[name="verificationCode"]',
                'input[aria-label*="verification code" i]',
                'input[placeholder*="verification code" i]',
            ]
            
            # Medium-confidence OTP selectors (need additional validation)
            medium_confidence_selectors = [
                'input[name="code"]',
                'input[placeholder*="code" i][maxlength="6"]',
                'input[placeholder*="code" i][maxlength="8"]',
                'input[placeholder*="code" i][maxlength="4"]',
            ]
            
            # Common patterns for segmented OTP inputs
            segmented_otp_selectors = [
                'div[class*="otp"] input[maxlength="1"]',
                'div[class*="verification"] input[maxlength="1"]',
                'div[class*="authCode"] input[maxlength="1"]'
            ]
            
            # Check high-confidence selectors first
            for selector in high_confidence_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    if elements:
                        logger.debug(f"Found high-confidence OTP input with selector: {selector}")
                        return True, "HIGH", self._determine_mfa_type()
                except Exception as e:
                    logger.debug(f"Error finding OTP input with selector {selector}: {e}")
            
            # Check medium-confidence selectors
            for selector in medium_confidence_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    if elements:
                        logger.debug(f"Found medium-confidence OTP input with selector: {selector}")
                        
                        # Validate the element is actually for OTP by checking surrounding text
                        valid_elements = []
                        for element in elements:
                            try:
                                # Get element's bounding box
                                element_rect = element.bounding_box()
                                if not element_rect:
                                    continue
                                
                                # Find nearby text elements for context
                                surrounding_elements = self.page.query_selector_all(
                                    'label, div, p, span, h1, h2, h3, h4, h5, h6'
                                )
                                
                                for surr_el in surrounding_elements:
                                    surr_rect = surr_el.bounding_box()
                                    # Check if element is close to our input (within 150px)
                                    if (surr_rect and 
                                        abs(surr_rect['x'] - element_rect['x']) < 200 and
                                        abs(surr_rect['y'] - element_rect['y']) < 150):
                                        
                                        surr_text = surr_el.inner_text().lower()
                                        
                                        # Check for clear MFA context
                                        if any(term in surr_text for term in [
                                            "verification code", "security code", 
                                            "authentication code", "one-time code",
                                            "two-factor", "2fa", "sent to your",
                                            "check your email", "check your phone"
                                        ]):
                                            valid_elements.append(element)
                                            break
                                            
                                        # Check for negative indicators that suggest this isn't MFA
                                        if any(term in surr_text for term in self.negative_indicators):
                                            # If negative indicator is present, skip this element
                                            break
                            except Exception as e:
                                logger.debug(f"Error checking element context: {e}")
                        
                        if valid_elements:
                            logger.debug(f"Found {len(valid_elements)} validated OTP elements")
                            return True, "MEDIUM", self._determine_mfa_type()
                except Exception as e:
                    logger.debug(f"Error finding OTP input with selector {selector}: {e}")
            
            # Only check for segmented inputs if we have some verification context
            verification_context = self._has_strong_mfa_context()
            if verification_context:
                # First check specific segmented OTP selectors
                for selector in segmented_otp_selectors:
                    try:
                        elements = self.page.query_selector_all(selector)
                        if elements and len(elements) >= 4:
                            logger.debug(f"Found {len(elements)} segmented OTP input elements")
                            return True, "MEDIUM", self._determine_mfa_type()
                    except Exception as e:
                        logger.debug(f"Error finding segmented OTP input with selector {selector}: {e}")
                
                # Then check generic segmented inputs, but only if we have strong MFA context
                generic_segmented = 'input[maxlength="1"]'
                try:
                    elements = self.page.query_selector_all(generic_segmented)
                    # Need at least 4 single-digit inputs to be a likely OTP
                    if elements and len(elements) >= 4:
                        # Verify these inputs are arranged horizontally and have similar y-positions
                        try:
                            y_positions = []
                            x_positions = []
                            for element in elements:
                                box = element.bounding_box()
                                if box:
                                    y_positions.append(box['y'])
                                    x_positions.append(box['x'])
                            
                            # Sort x positions to check for sequential layout
                            x_positions.sort()
                            
                            # If y positions are within 10px of each other, they're likely in a row
                            if (y_positions and 
                                max(y_positions) - min(y_positions) < 10 and
                                len(x_positions) >= 4):
                                
                                # Check that x positions are sequential (spaced properly)
                                is_sequential = True
                                for i in range(1, len(x_positions)):
                                    # The gaps between elements should be relatively consistent
                                    if x_positions[i] - x_positions[i-1] > 100:
                                        is_sequential = False
                                        break
                                
                                if is_sequential:
                                    logger.debug("Found horizontally arranged segmented OTP inputs")
                                    return True, "MEDIUM", self._determine_mfa_type()
                        except Exception as e:
                            logger.debug(f"Error checking segmented input arrangement: {e}")
                except Exception as e:
                    logger.debug(f"Error finding generic segmented OTP inputs: {e}")
        except Exception as e:
            logger.debug(f"Error in OTP detection: {e}")
            
        return False, "", ""

    def _detect_mfa_text(self) -> Tuple[bool, str, str]:
        """
        Detect text on the page indicating MFA/2FA
        Returns: (found, confidence, type)
        """
        try:
            page_text = self.page.content().lower()
            
            # Check for negative indicators first
            for indicator in self.negative_indicators:
                if indicator in page_text:
                    logger.debug(f"Found negative indicator in text detection: {indicator}")
                    # Don't return early, but we'll require stronger evidence
            
            # High-confidence MFA text indicators 
            high_confidence_indicators = {
                "TOTP": [
                    "authenticator app code",
                    "google authenticator code",
                    "microsoft authenticator code",
                    "authy code",
                    "totp code",
                    "use your authenticator app",
                    "open your authenticator app"
                ],
                "SMS": [
                    "verification code via sms", 
                    "verification code by text", 
                    "code sent to your phone",
                    "text message with a code",
                    "sms verification code",
                    "code sent to phone number",
                    "we've sent a text to"
                ],
                "EMAIL": [
                    "verification code via email",
                    "code sent to your email",
                    "check your inbox for a code",
                    "we've sent a code to your email",
                    "email verification code"
                ]
            }
            
            # Medium-confidence MFA text indicators (need additional context)
            medium_confidence_indicators = {
                "TOTP": [
                    "authenticator", 
                    "google authenticator", 
                    "microsoft authenticator", 
                    "authy", 
                    "totp"
                ],
                "SMS": [
                    "sms code",
                    "text message code",
                    "via text message"
                ],
                "EMAIL": [
                    "email code", 
                    "sent to your email", 
                    "check your inbox"
                ]
            }
            
            # Check high-confidence indicators first
            for mfa_type, indicators in high_confidence_indicators.items():
                for indicator in indicators:
                    if indicator in page_text:
                        logger.debug(f"Found high-confidence {mfa_type} indicator: {indicator}")
                        return True, "HIGH", mfa_type
            
            # Check medium-confidence indicators only if we have verification context
            verification_context = any(ctx in page_text for ctx in [
                "enter the code",
                "verification code",
                "security code",
                "one-time code",
                "2fa code",
                "two-factor",
                "verify your identity"
            ])
            
            if verification_context:
                for mfa_type, indicators in medium_confidence_indicators.items():
                    for indicator in indicators:
                        if indicator in page_text:
                            logger.debug(f"Found medium-confidence {mfa_type} indicator with verification context: {indicator}")
                            return True, "MEDIUM", mfa_type
            
            # Check for the presence of specific MFA UI patterns in text
            if verification_context:
                mfa_ui_patterns = [
                    "enter verification code",
                    "enter the code sent",
                    "verification code input", 
                    "enter one-time code",
                    "enter security code",
                    "2-step verification code",
                    "two factor code",
                    "2fa code"
                ]
                
                for pattern in mfa_ui_patterns:
                    if pattern in page_text:
                        logger.debug(f"Found MFA UI pattern: {pattern}")
                        return True, "MEDIUM", "CUSTOM"
        except Exception as e:
            logger.debug(f"Error detecting MFA text: {e}")
            
        return False, "", ""

    def _detect_qr_code(self) -> bool:
        """
        Detect QR code images on the page, but only if in MFA context
        """
        try:
            # First check if we have authenticator app context
            page_text = self.page.content().lower()
            authenticator_context = any(term in page_text for term in [
                "scan qr code",
                "scan this code", 
                "authenticator app",
                "google authenticator", 
                "microsoft authenticator"
            ])
            
            if not authenticator_context:
                logger.debug("No authenticator app context for QR code")
                return False
            
            # QR code selectors
            qr_selectors = [
                'img[alt*="qr" i]',
                'img[src*="qr" i]',
                'img[class*="qr" i]',
                'canvas[id*="qr" i]',
                'div[class*="qr" i] img',
                'div[class*="qrcode" i]'
            ]
            
            for selector in qr_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    if elements:
                        # Additional validation - QR codes should be square-ish
                        for element in elements:
                            box = element.bounding_box()
                            if box:
                                width = box['width']
                                height = box['height']
                                # QR codes should be roughly square
                                if width > 50 and height > 50:
                                    # Check aspect ratio (square-ish with 30% tolerance)
                                    aspect_ratio = width / height
                                    if 0.7 <= aspect_ratio <= 1.3:
                                        logger.debug(f"Found QR code with selector: {selector}")
                                        return True
                except Exception as e:
                    logger.debug(f"Error finding QR code with selector {selector}: {e}")
                
        except Exception as e:
            logger.debug(f"Error in QR code detection: {e}")
            
        return False

    def _determine_mfa_type(self) -> str:
        """
        Determine the type of MFA based on page context
        """
        try:
            page_text = self.page.content().lower()
            
            # Look for explicit mentions of authenticator apps
            if any(keyword in page_text for keyword in [
                "authenticator app", 
                "google authenticator", 
                "microsoft authenticator", 
                "authy", 
                "totp"
            ]):
                return "TOTP"
                
            # Look for SMS verification context
            elif any(phrase in page_text for phrase in [
                "verification code via sms", 
                "verification code by text", 
                "sent to your phone",
                "text message with a code",
                "sms verification code",
                "security code via text",
                "we sent a text to",
                "mobile number",
                "phone number ending in"
            ]):
                return "SMS"
                
            # Look for email verification context
            elif any(phrase in page_text for phrase in [
                "sent to your email",
                "check your inbox",
                "check your email for a code",
                "verification code via email",
                "email address ending in"
            ]):
                return "EMAIL"
                
            # Look for QR code context
            elif any(keyword in page_text for keyword in ["scan qr code", "scan this code", "scan with authenticator"]):
                return "QR"
                
            else:
                return "CUSTOM"
                
        except Exception as e:
            logger.debug(f"Error determining MFA type: {e}")
            return "CUSTOM" 
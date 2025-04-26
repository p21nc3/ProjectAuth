import logging
import time
from typing import Tuple, List, Dict, Any, Optional
from playwright.sync_api import Page, ElementHandle
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
        # Confidence thresholds for detection
        self.HIGH_CONFIDENCE = 80
        self.MEDIUM_CONFIDENCE = 50
        self.LOW_CONFIDENCE = 30

    def detect_passkey_button(self, url: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Detects passkey buttons or links on the current page with improved accuracy
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
        
        # Combined detection approach with confidence scoring
        confidence, passkey_type, detection_method = self._evaluate_passkey_presence()
        
        if confidence >= self.MEDIUM_CONFIDENCE:
            logger.info(f"PASSKEY detected with confidence {confidence}%, type: {passkey_type}")
            
            element_validity = "HIGH" if confidence >= self.HIGH_CONFIDENCE else "MEDIUM"
            
            passkey_info = {
                "idp_name": "PASSKEY BUTTON",
                "idp_sdk": passkey_type,
                "idp_integration": "CUSTOM",
                "idp_frame": "SAME_WINDOW",
                "login_page_url": self.url,
                "element_validity": element_validity,
                "detection_method": detection_method,
                "passkey_type": passkey_type,
                "confidence": confidence
            }
            return True, passkey_info
            
        return False, None

    def _evaluate_passkey_presence(self) -> Tuple[int, str, str]:
        """
        Evaluates multiple signals to determine passkey presence with confidence score
        Returns: (confidence_score, passkey_type, detection_method)
        """
        # Check for strong UI indicators first
        ui_confidence, ui_type = self._detect_passkey_ui_elements()
        
        # Check for API usage and strong textual evidence
        api_confidence, api_type = self._detect_passkey_api_usage()
        
        # Check for passkey text mentions (weakest signal)
        text_confidence, text_type = self._detect_passkey_text()
        
        # Combined confidence calculation with weighting
        # UI elements are strongest indicators, followed by API usage, then text
        total_confidence = max(
            ui_confidence,
            api_confidence * 0.8,  # API usage is a strong signal but may be in included libraries
            text_confidence * 0.6   # Text is the weakest signal
        )
        
        # Determine the most likely passkey type based on highest confidence signals
        passkey_type = "WEBAUTHN"  # Default
        if ui_confidence > api_confidence and ui_confidence > text_confidence:
            passkey_type = ui_type
        elif api_confidence > text_confidence:
            passkey_type = api_type
        else:
            passkey_type = text_type
            
        # Determine detection method
        if ui_confidence >= self.MEDIUM_CONFIDENCE:
            detection_method = "PASSKEY-BUTTON"
        elif api_confidence >= self.MEDIUM_CONFIDENCE:
            detection_method = "PASSKEY-API"
        else:
            detection_method = "PASSKEY-KEYWORD"
            
        return int(total_confidence), passkey_type, detection_method

    def _detect_passkey_ui_elements(self) -> Tuple[int, str]:
        """
        Detect UI elements like buttons or links related to passkeys
        Returns confidence score and passkey type
        """
        # Direct passkey button selectors (high confidence)
        high_confidence_selectors = []
        
        # Create specific selectors for interactive elements with clear passkey intent
        for keyword in self.passkey_keywords:
            high_confidence_selectors.extend([
                f'button:has-text("{keyword}"):visible',
                f'a:has-text("{keyword}"):visible',
                f'div[role="button"]:has-text("{keyword}"):visible',
                f'[aria-label="{keyword}"]:visible',
                f'[title="{keyword}"]:visible'
            ])
        
        # Very specific passkey button text patterns (highest confidence)
        explicit_passkey_buttons = [
            'button:has-text("Sign in with a passkey"):visible',
            'button:has-text("log in with a passkey"):visible',
            'button:has-text("Use passkey"):visible',
            'button:has-text("Use a passkey"):visible',
            'button:has-text("Continue with passkey"):visible',
            'a:has-text("Sign in with passkey"):visible',
            'a:has-text("Use passkey"):visible',
            'a:has-text("Use a passkey"):visible',
            'a:has-text("Continue with passkey"):visible',
            '[role="button"]:has-text("Sign in with passkey"):visible',
            '[role="button"]:has-text("Use passkey"):visible',
            '[role="button"]:has-text("Use a passkey"):visible',
            '[role="button"]:has-text("Continue with passkey"):visible'
        ]
        
        # Add platform-specific high confidence selectors
        apple_selectors = [
            'button:has-text("Sign in with Face ID"):visible',
            'button:has-text("Use Face ID"):visible',
            'button:has-text("Continue with Face ID"):visible',
            'button:has-text("Sign in with Touch ID"):visible',
            'button:has-text("Use Touch ID"):visible',
            'button:has-text("Continue with Touch ID"):visible',
            'a:has-text("Sign in with Face ID"):visible',
            'a:has-text("Use Face ID"):visible',
            'a:has-text("Continue with Face ID"):visible',
            'a:has-text("Sign in with Touch ID"):visible',
            'a:has-text("Use Touch ID"):visible',
            'a:has-text("Continue with Touch ID"):visible'
        ]
        
        android_selectors = [
            'button:has-text("Sign in with fingerprint"):visible',
            'button:has-text("Use fingerprint"):visible',
            'button:has-text("Continue with fingerprint"):visible',
            'a:has-text("Sign in with fingerprint"):visible',
            'a:has-text("Use fingerprint"):visible',
            'a:has-text("Continue with fingerprint"):visible'
        ]
        
        # Medium confidence selectors
        medium_confidence_selectors = [
            '[data-testid*="passkey" i]:visible',
            '[data-test*="passkey" i]:visible',
            '[id="passkey-button"]:visible',
            '[id="passkeyButton"]:visible',
            '[id="passkey_button"]:visible',
            '[id="passkey-signin"]:visible',
            '[id="passkeySignin"]:visible',
            '[id="passkey_signin"]:visible',
            'label:has-text("Use passkey"):visible',
            'label:has-text("Use a passkey"):visible'
        ]
        
        # Low confidence selectors (more prone to false positives)
        low_confidence_selectors = [
            '[class*="passkey" i]:visible',
            '[id*="passkey" i]:visible',
            'span:has-text("passkey"):visible',
            'p:has-text("passkey"):visible'
        ]
        
        # Initialize confidence score and passkey type
        confidence = 0
        passkey_type = "WEBAUTHN"
        
        # Helper function to check elements against selectors
        def check_selectors(selectors, base_confidence):
            nonlocal confidence, passkey_type
            for selector in selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    if elements:
                        # Check if elements are actually visible in viewport
                        visible_elements = [el for el in elements if self._is_element_visible(el)]
                        if visible_elements:
                            logger.debug(f"Found {len(visible_elements)} passkey UI elements with selector: {selector}")
                            
                            # Check selector text for platform hints
                            selector_lower = selector.lower()
                            if "face id" in selector_lower or "touch id" in selector_lower:
                                passkey_type = "APPLE"
                                # Check if this is a clearly visible button with apple terminology
                                if "button" in selector_lower and len(visible_elements) > 0:
                                    confidence = max(confidence, base_confidence + 20)
                                else:
                                    confidence = max(confidence, base_confidence)
                            elif "fingerprint" in selector_lower:
                                passkey_type = "ANDROID"
                                if "button" in selector_lower and len(visible_elements) > 0:
                                    confidence = max(confidence, base_confidence + 20)
                                else:
                                    confidence = max(confidence, base_confidence)
                            else:
                                confidence = max(confidence, base_confidence)
                                
                except Exception as e:
                    logger.debug(f"Error finding passkey UI element with selector {selector}: {e}")
        
        # Check selectors in order of confidence
        check_selectors(explicit_passkey_buttons, 95)  # Explicit passkey buttons are highest confidence
        check_selectors(apple_selectors, 90)  # Platform-specific selectors are very high confidence
        check_selectors(android_selectors, 90)
        check_selectors(high_confidence_selectors, 80)  # High confidence selectors
        check_selectors(medium_confidence_selectors, 60)  # Medium confidence selectors
        check_selectors(low_confidence_selectors, 40)  # Low confidence selectors
        
        return confidence, passkey_type
    
    def _is_element_visible(self, element: ElementHandle) -> bool:
        """Check if an element is visible and of reasonable size"""
        try:
            if not element.is_visible():
                return False
            
            # Get bounding box
            bbox = element.bounding_box()
            if not bbox:
                return False
                
            # Check if element has reasonable size (not too small)
            if bbox['width'] < 5 or bbox['height'] < 5:
                return False
                
            return True
        except Exception as e:
            logger.debug(f"Error checking element visibility: {e}")
            return False

    def _detect_passkey_api_usage(self) -> Tuple[int, str]:
        """
        Detect WebAuthn/passkey API usage in page scripts
        Returns confidence score and passkey type
        """
        try:
            # Look for script content containing WebAuthn API calls
            api_indicators = {
                # Strong indicators (direct API usage)
                "navigator.credentials.create({publicKey": 90,
                "navigator.credentials.get({publicKey": 90,
                "window.PublicKeyCredential": 85,
                "PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable": 90,
                
                # Medium indicators
                "publicKey: {": 70,
                "PublicKeyCredential": 65,
                "WebAuthnAPI": 75,
                
                # Specific libraries
                "SimpleWebAuthn": 80,
                "@simplewebauthn/browser": 85,
                "webauthn-json": 80
            }
            
            # Get all script content on the page
            scripts = self.page.evaluate("""
                Array.from(document.querySelectorAll('script')).map(s => s.textContent || '').join(' ');
            """)
            
            # Check for API usage
            confidence = 0
            for indicator, score in api_indicators.items():
                if indicator in scripts:
                    logger.debug(f"Found passkey API usage: {indicator}")
                    confidence = max(confidence, score)
            
            return confidence, "WEBAUTHN"
            
        except Exception as e:
            logger.debug(f"Error detecting passkey API usage: {e}")
            return 0, "WEBAUTHN"

    def _detect_passkey_text(self) -> Tuple[int, str]:
        """
        Detect text on the page indicating passkey support
        Returns confidence score and passkey type
        """
        try:
            # Get visible text content from the page (more reliable than page.content())
            page_text = self.page.evaluate("""
                Array.from(document.querySelectorAll('body *'))
                    .filter(el => el.offsetParent !== null) // Only visible elements
                    .map(el => el.textContent || '')
                    .join(' ')
                    .toLowerCase();
            """)
            
            # Define confidence levels for different text indicators
            high_confidence_phrases = {
                "sign in with passkey": "WEBAUTHN",
                "log in with passkey": "WEBAUTHN",
                "continue with passkey": "WEBAUTHN",
                "use passkey to sign in": "WEBAUTHN",
                "use passkey to log in": "WEBAUTHN",
                "sign in with face id": "APPLE",
                "log in with face id": "APPLE",
                "continue with face id": "APPLE",
                "sign in with touch id": "APPLE",
                "log in with touch id": "APPLE",
                "continue with touch id": "APPLE",
                "sign in with fingerprint": "ANDROID",
                "log in with fingerprint": "ANDROID",
                "continue with fingerprint": "ANDROID"
            }
            
            medium_confidence_phrases = {
                "use passkey": "WEBAUTHN",
                "use a passkey": "WEBAUTHN",
                "use security key": "WEBAUTHN",
                "use face id": "APPLE",
                "use touch id": "APPLE",
                "use fingerprint": "ANDROID"
            }
            
            low_confidence_phrases = {
                "passkey": "WEBAUTHN",
                "webauthn": "WEBAUTHN",
                "face id": "APPLE",
                "touch id": "APPLE",
                "fingerprint authentication": "ANDROID"
            }
            
            # Words that might cause false positives when appearing alone
            false_positive_context = [
                "password",
                "reset",
                "forgot",
                "recover",
                "change",
                "enter",
                "create",
                "setup"
            ]
            
            # Check for high confidence phrases first
            confidence = 0
            passkey_type = "WEBAUTHN"
            
            for phrase, ptype in high_confidence_phrases.items():
                if phrase in page_text:
                    # Check if it's in a false positive context
                    is_false_positive = False
                    for fp_context in false_positive_context:
                        if f"{phrase} {fp_context}" in page_text or f"{fp_context} {phrase}" in page_text:
                            is_false_positive = True
                            break
                    
                    if not is_false_positive:
                        logger.debug(f"Found high confidence passkey phrase: {phrase}")
                        confidence = max(confidence, 75)
                        passkey_type = ptype
            
            # Check medium confidence phrases if no high confidence match
            if confidence < 75:
                for phrase, ptype in medium_confidence_phrases.items():
                    if phrase in page_text:
                        # Check if it's in a false positive context
                        is_false_positive = False
                        for fp_context in false_positive_context:
                            if f"{phrase} {fp_context}" in page_text or f"{fp_context} {phrase}" in page_text:
                                is_false_positive = True
                                break
                        
                        if not is_false_positive:
                            logger.debug(f"Found medium confidence passkey phrase: {phrase}")
                            confidence = max(confidence, 60)
                            passkey_type = ptype
            
            # Check low confidence phrases only if no better match
            if confidence < 60:
                for phrase, ptype in low_confidence_phrases.items():
                    if phrase in page_text:
                        # Check for surrounding context to filter false positives
                        is_false_positive = False
                        for fp_context in false_positive_context:
                            if f"{phrase} {fp_context}" in page_text or f"{fp_context} {phrase}" in page_text:
                                is_false_positive = True
                                break
                        
                        if not is_false_positive:
                            logger.debug(f"Found low confidence passkey phrase: {phrase}")
                            confidence = max(confidence, 40)
                            passkey_type = ptype
                            
            return confidence, passkey_type
                    
        except Exception as e:
            logger.debug(f"Error detecting passkey text: {e}")
            
        return 0, "WEBAUTHN"
import logging
from typing import List, Dict, Tuple
from playwright.sync_api import Page
from modules.helper.detection import DetectionHelper
from modules.helper.image import ImageHelper
from config.idp_rules import IdpRules
from modules.locators.css import CSSLocator

logger = logging.getLogger(__name__)


class PasskeyButtonDetector:
    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result
        self.store_sso_button_detection_screenshot = config["artifacts_config"]["store_sso_button_detection_screenshot"]
        self.keywords = config.get("keyword_recognition_config", {}).get("keywords", ["no-keyword-matching"])
    
    def start(self, lpc_url: str, page: Page):
        logger.info(f"Starting passkey button detection on: {lpc_url}")
        
        # Use multiple detection methods
        # 1. Check for passkey button using keywords
        passkey_buttons = self.detect_passkey_buttons(page)
        
        # 2. Check if the page has WebAuthn API calls (interface with navigator_credentials)
        has_webauthn_api = self.check_webauthn_api_calls(page)
        
        # 3. Check passkey element pattern (fingerprint/face recognition icons)
        passkey_elements = self.detect_passkey_elements(page)
        
        if passkey_buttons or has_webauthn_api or passkey_elements:
            logger.info(f"Found passkey indicators on: {lpc_url}")
            
            # Use the first passkey button/element if available
            if passkey_buttons:
                button = passkey_buttons[0]
                element_x = button["x"]
                element_y = button["y"]
                element_width = button["width"]
                element_height = button["height"]
                detection_type = "button"
                detection_text = button.get("inner_text", "")
            elif passkey_elements:
                element = passkey_elements[0]
                element_x = element["x"]
                element_y = element["y"]
                element_width = element["width"]
                element_height = element["height"]
                detection_type = "element"
                detection_text = element.get("alt", "") or element.get("title", "")
            else:
                # Default values if only API calls were detected
                viewport_size = page.viewport_size
                element_x = viewport_size["width"] / 2
                element_y = viewport_size["height"] / 2
                element_width = 100
                element_height = 30
                detection_type = "api_only"
                detection_text = "WebAuthn API detected"
            
            page_screenshot = page.screenshot()
            if passkey_buttons or passkey_elements:
                page_screenshot = ImageHelper.base64comppng_draw_rectangle(
                    page_screenshot,
                    element_x, element_y,
                    element_width, element_height
                )
            
            element_tree, element_tree_markup = DetectionHelper.get_coordinate_metadata(
                page, 
                element_x + element_width / 2, 
                element_y + element_height / 2
            )
            
            # Add to recognized IDPs
            self.result["recognized_idps"].append({
                "idp_name": "PASSKEY",
                "idp_integration": "WEBAUTHN",
                "login_page_url": lpc_url,
                "element_coordinates_x": element_x,
                "element_coordinates_y": element_y,
                "element_width": element_width,
                "element_height": element_height,
                "element_tree": element_tree,
                "element_tree_markup": element_tree_markup,
                "recognition_strategy": "PASSKEY_BUTTON",
                "passkey_detection_type": detection_type,
                "passkey_detection_text": detection_text,
                "has_webauthn_api": has_webauthn_api,
                "passkey_button_screenshot": page_screenshot if self.store_sso_button_detection_screenshot else None
            })
            return True
        return False
    
    def detect_passkey_buttons(self, page: Page) -> List[Dict]:
        keywords = IdpRules["PASSKEY"]["keywords"]
        locator = CSSLocator(keywords, self.keywords)
        
        # Find high validity matches first
        high_validity_elements = locator.locate(page, high_validity=True)
        if high_validity_elements:
            return high_validity_elements
        
        # If no high validity matches, try low validity
        low_validity_elements = locator.locate(page, high_validity=False)
        return low_validity_elements
    
    def check_webauthn_api_calls(self, page: Page) -> bool:
        # This links with the functionality in navigator_credentials.py
        # We're just checking if WebAuthn API methods are available and not blocked
        try:
            has_webauthn = page.evaluate("""() => {
                return !!(
                    navigator.credentials && 
                    (navigator.credentials.create || navigator.credentials.get) && 
                    (window.PublicKeyCredential !== undefined)
                );
            }""")
            return has_webauthn
        except Exception as e:
            logger.warning(f"Error checking WebAuthn API: {e}")
            return False
    
    def detect_passkey_elements(self, page: Page) -> List[Dict]:
        # Look for common passkey-related elements like fingerprint/biometric icons
        selectors = [
            "img[alt*='passkey' i]",
            "img[alt*='fingerprint' i]",
            "img[alt*='biometric' i]",
            "img[alt*='face' i][alt*='id' i]",
            "img[alt*='touch' i][alt*='id' i]",
            "img[src*='passkey' i]",
            "img[src*='fingerprint' i]",
            "img[src*='biometric' i]",
            "img[src*='face-id' i]",
            "img[src*='touch-id' i]",
            "svg[title*='passkey' i]",
            "svg[title*='fingerprint' i]",
            "i[class*='fingerprint' i]",
            "i[class*='passkey' i]"
        ]
        
        elements = []
        for selector in selectors:
            try:
                matches = page.query_selector_all(selector)
                for match in matches:
                    if match.is_visible():
                        # Get detailed element info
                        element_info = page.evaluate("""args => {
                            const selector = args[0];
                            const element = document.querySelector(selector);
                            if (!element) return null;
                            const rect = element.getBoundingClientRect();
                            return {
                                tag: element.tagName.toLowerCase(),
                                alt: element.alt || '',
                                title: element.title || '',
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height,
                                outer_html: element.outerHTML
                            };
                        }""", [selector])
                        
                        if element_info and element_info not in elements:
                            elements.append(element_info)
            except Exception as e:
                logger.warning(f"Error finding passkey elements with selector {selector}: {e}")
        
        return elements 
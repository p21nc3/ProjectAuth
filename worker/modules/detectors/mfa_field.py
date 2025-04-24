import logging
from typing import List, Dict
from playwright.sync_api import Page
from modules.helper.detection import DetectionHelper
from modules.helper.image import ImageHelper
from config.idp_rules import IdpRules

logger = logging.getLogger(__name__)


class MFAFieldDetector:
    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result
        self.store_sso_button_detection_screenshot = config["artifacts_config"]["store_sso_button_detection_screenshot"]
    
    def start(self, lpc_url: str, page: Page):
        logger.info(f"Starting MFA field detection on: {lpc_url}")
        
        # Check for MFA-related elements using the selectors from the IdpRules
        mfa_fields = self.locate_mfa_elements(page)
        
        # Check for MFA keywords in page content
        mfa_keywords_present = self.check_mfa_keywords(page)
        
        # Check for QR code images
        qr_codes = self.locate_qr_codes(page)
        
        if mfa_fields or mfa_keywords_present or qr_codes:
            logger.info(f"Found MFA indicators on: {lpc_url}")
            
            # Use the first MFA field if available, or a generic position
            if mfa_fields:
                field = mfa_fields[0]
                element_x = field["x"]
                element_y = field["y"]
                element_width = field["width"]
                element_height = field["height"]
                element_type = field["type"]
            elif qr_codes:
                field = qr_codes[0]
                element_x = field["x"]
                element_y = field["y"]
                element_width = field["width"]
                element_height = field["height"]
                element_type = "qr_code"
            else:
                # Default values if only keywords were found
                viewport_size = page.viewport_size
                element_x = viewport_size["width"] / 2
                element_y = viewport_size["height"] / 2
                element_width = 100
                element_height = 30
                element_type = "keyword_only"
            
            page_screenshot = page.screenshot()
            if mfa_fields or qr_codes:
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
                "idp_name": "MFA_GENERIC",
                "idp_integration": "CUSTOM",
                "login_page_url": lpc_url,
                "element_coordinates_x": element_x,
                "element_coordinates_y": element_y,
                "element_width": element_width,
                "element_height": element_height,
                "element_tree": element_tree,
                "element_tree_markup": element_tree_markup,
                "recognition_strategy": "MFA_FIELD",
                "mfa_field_type": element_type,
                "mfa_detection_method": "fields" if mfa_fields else ("qr_code" if qr_codes else "keywords"),
                "mfa_field_screenshot": page_screenshot if self.store_sso_button_detection_screenshot else None
            })
            return True
        return False
    
    def locate_mfa_elements(self, page: Page) -> List[Dict]:
        selectors = IdpRules["MFA_GENERIC"]["mfa_step"]["selectors"]
        
        fields = []
        for selector in selectors:
            try:
                elements = page.query_selector_all(selector)
                for element in elements:
                    if element.is_visible():
                        # Get detailed element info
                        element_info = page.evaluate("""selector => {
                            const element = document.querySelector(selector);
                            if (!element) return null;
                            const rect = element.getBoundingClientRect();
                            return {
                                type: "input_field",
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height,
                                outer_html: element.outerHTML
                            };
                        }""", selector)
                        
                        if element_info and element_info not in fields:
                            fields.append(element_info)
            except Exception as e:
                logger.warning(f"Error finding MFA fields with selector {selector}: {e}")
        
        return fields
    
    def check_mfa_keywords(self, page: Page) -> bool:
        keywords = IdpRules["MFA_GENERIC"]["keywords"]
        
        try:
            # Check if any of the keywords are present in the page text
            page_text = page.evaluate("""() => {
                return document.body.textContent;
            }""")
            
            for keyword in keywords:
                if keyword.lower() in page_text.lower():
                    logger.info(f"Found MFA keyword: {keyword}")
                    return True
        except Exception as e:
            logger.warning(f"Error checking MFA keywords: {e}")
        
        return False
    
    def locate_qr_codes(self, page: Page) -> List[Dict]:
        qr_selectors = [
            "img[alt*='qr' i]", 
            "img[alt*='code' i]",
            "img[src*='qr' i]",
            "img[src*='code' i]",
            "canvas[id*='qr' i]",
            "div[class*='qr' i]"
        ]
        
        qr_codes = []
        for selector in qr_selectors:
            try:
                elements = page.query_selector_all(selector)
                for element in elements:
                    if element.is_visible():
                        # Get detailed element info
                        element_info = page.evaluate("""selector => {
                            const element = document.querySelector(selector);
                            if (!element) return null;
                            const rect = element.getBoundingClientRect();
                            return {
                                type: "qr_code",
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height,
                                outer_html: element.outerHTML
                            };
                        }""", selector)
                        
                        if element_info and element_info not in qr_codes:
                            qr_codes.append(element_info)
            except Exception as e:
                logger.warning(f"Error finding QR codes with selector {selector}: {e}")
        
        return qr_codes 
import logging
from typing import Tuple, Dict, List
from playwright.sync_api import Page
from modules.helper.detection import DetectionHelper
from modules.helper.image import ImageHelper
from config.idp_rules import IdpRules

logger = logging.getLogger(__name__)


class PasswordFieldDetector:
    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result
        self.store_sso_button_detection_screenshot = config["artifacts_config"]["store_sso_button_detection_screenshot"]
    
    def start(self, lpc_url: str, page: Page):
        logger.info(f"Starting password field detection on: {lpc_url}")
        
        username_fields = self.locate_input_fields(page, "username")
        password_fields = self.locate_input_fields(page, "password")
        
        if username_fields and password_fields:
            logger.info(f"Found username and password fields on: {lpc_url}")
            
            # Getting the first password field for screenshot and detection
            password_field = password_fields[0]
            username_field = username_fields[0]
            
            page_screenshot = ImageHelper.base64comppng_draw_rectangle(
                page.screenshot(),
                password_field["x"], password_field["y"],
                password_field["width"], password_field["height"]
            )
            
            element_tree, element_tree_markup = DetectionHelper.get_coordinate_metadata(
                page, 
                password_field["x"] + password_field["width"] / 2, 
                password_field["y"] + password_field["height"] / 2
            )
            
            # Add to recognized IDPs
            self.result["recognized_idps"].append({
                "idp_name": "USERNAME_PASSWORD",
                "idp_integration": "CUSTOM",
                "login_page_url": lpc_url,
                "element_coordinates_x": password_field["x"],
                "element_coordinates_y": password_field["y"],
                "element_width": password_field["width"],
                "element_height": password_field["height"],
                "element_tree": element_tree,
                "element_tree_markup": element_tree_markup,
                "recognition_strategy": "PASSWORD_FIELD",
                "password_field_username": username_field["name"],
                "password_field_password": password_field["name"],
                "password_field_screenshot": page_screenshot if self.store_sso_button_detection_screenshot else None
            })
            return True
        return False
    
    def locate_input_fields(self, page: Page, field_type: str) -> List[Dict]:
        field_patterns = IdpRules["USERNAME_PASSWORD"]["form_rule"]["fields"][field_type]
        
        # Create selectors for the field type
        selectors = []
        for pattern in field_patterns:
            selectors.append(f"input[type='{pattern}']")
            selectors.append(f"input[name='{pattern}']")
            selectors.append(f"input[id='{pattern}']")
            selectors.append(f"input[placeholder*='{pattern}' i]")
        
        fields = []
        for selector in selectors:
            try:
                elements = page.query_selector_all(selector)
                for element in elements:
                    if element.is_visible():
                        # Use page.eval_on_selector to get detailed element info
                        element_info = page.evaluate("""selector => {
                            const element = document.querySelector(selector);
                            if (!element) return null;
                            const rect = element.getBoundingClientRect();
                            return {
                                name: element.name || element.id,
                                type: element.type,
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
                logger.warning(f"Error finding {field_type} fields: {e}")
        
        return fields 
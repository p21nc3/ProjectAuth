import logging
import time
from typing import Tuple, List
from playwright.sync_api import Page
from modules.browser.browser import PlaywrightHelper
from modules.helper.detection import DetectionHelper

logger = logging.getLogger(__name__)

class PasswordDetector:
    """
    Detector for password-based authentication forms containing username/email and password fields
    """

    def __init__(self, result: dict, page: Page):
        self.result = result
        self.page = page
        self.url = None

    def detect_password_form(self, url: str) -> Tuple[bool, dict]:
        """
        Detects username/password form fields on the current page
        """
        logger.info(f"Checking for password form fields on: {url}")
        self.url = url
        
        # Check if this URL already has a password form detection to avoid duplicates
        for idp in self.result.get("recognized_idps", []):
            if (idp.get("idp_name") == "PASSWORD_BASED" and 
                idp.get("login_page_url") == url):
                logger.info(f"Password form already detected for {url}, skipping")
                return False, None
        
        # Look for username/email field
        username_selectors = [
            'input[type="text"][name="username"]',
            'input[type="text"][name="email"]',
            'input[type="email"]',
            'input[type="text"][placeholder*="username" i]',
            'input[type="text"][placeholder*="email" i]',
            'input[aria-label*="username" i]',
            'input[aria-label*="email" i]'
        ]
        
        # Look for password field
        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[placeholder*="password" i]',
            'input[aria-label*="password" i]'
        ]
        
        # Check if username field exists
        username_elements = []
        for selector in username_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                username_elements.extend(elements)
            except Exception as e:
                logger.debug(f"Error finding username field with selector {selector}: {e}")
        
        # Check if password field exists
        password_elements = []
        for selector in password_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                password_elements.extend(elements)
            except Exception as e:
                logger.debug(f"Error finding password field with selector {selector}: {e}")
        
        # If both username and password fields exist, consider it a password form
        if username_elements and password_elements:
            logger.info(f"Password form detected with {len(username_elements)} username fields and {len(password_elements)} password fields")
            
            # Get the submit button if available
            submit_button = None
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Sign in")',
                'button:has-text("Log in")',
                'button:has-text("Login")'
            ]
            
            for selector in submit_selectors:
                try:
                    button = self.page.query_selector(selector)
                    if button:
                        submit_button = button
                        break
                except Exception as e:
                    logger.debug(f"Error finding submit button with selector {selector}: {e}")

            # Create detection info
            password_info = {
                "idp_name": "PASSWORD_BASED",
                "idp_sdk": "CUSTOM",
                "idp_integration": "CUSTOM",
                "idp_frame": "SAME_WINDOW",
                "login_page_url": self.url,
                "element_validity": "HIGH" if (len(username_elements) == 1 and len(password_elements) == 1) else "MEDIUM",
                "detection_method": "PASSWORD-FORM"
            }
            
            if submit_button:
                password_info["submit_button_found"] = True
            
            return True, password_info
        
        return False, None 
import logging
import time
from typing import List, Tuple
from playwright.sync_api import Page
from modules.browser.browser import PlaywrightBrowser, PlaywrightHelper
from modules.helper.detection import DetectionHelper
from modules.helper.tmp import TmpHelper
from playwright.sync_api import sync_playwright, Error, TimeoutError

logger = logging.getLogger(__name__)

class PasswordDetector:
    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result
        
        self.browser_config = config["browser_config"]
        self.artifacts_config = config["artifacts_config"]
        self.idp_scope = config["idp_config"]["idp_scope"]
        self.recognition_mode = config["recognition_strategy_config"]["recognition_mode"]
        self.recognition_strategy_scope = config["recognition_strategy_config"]["recognition_strategy_scope"]
        
        self.login_page_candidates = result["login_page_candidates"]
        self.recognized_idps = result["recognized_idps"]
        
        # Initialize auth_methods if not present
        if "auth_methods" not in self.result:
            self.result["auth_methods"] = {}
        
        # Initialize password method if not present
        if "password" not in self.result["auth_methods"]:
            self.result["auth_methods"]["password"] = {"detected": False, "validity": "LOW"}

    def start(self):
        logger.info("Starting password-based authentication detection")
        
        # targets: login page candidates
        lpcs_with_idps = {}
        
        # update login page candidates based on recognition mode
        DetectionHelper.get_lpcs_with_idps(
            lpcs_with_idps, self.login_page_candidates, self.recognized_idps,
            self.recognition_mode, self.idp_scope, False
        )
        
        for lpc in lpcs_with_idps:
            logger.info(f"Checking for password-based authentication on: {lpc}")
            
            # check if login page candidate is reachable and analyzable
            lpc_details = DetectionHelper.get_lpc_from_url(lpc, self.login_page_candidates)
            reachable = lpc_details.get("resolved", {}).get("reachable", False)
            valid = lpc_details.get("content_analyzable", {}).get("valid", False)
            
            if not reachable or not valid:
                logger.info(f"Login page candidate is not reachable or analyzable: {lpc}")
                continue
            
            self.detect_password_form(lpc)
    
    def detect_password_form(self, url: str):
        """Detect password form elements on the page."""
        with TmpHelper.tmp_dir() as pdir, sync_playwright() as pw:
            context, page = PlaywrightBrowser.instance(pw, self.browser_config, pdir)
            
            try:
                # Navigate to page
                PlaywrightHelper.navigate(page, url, self.browser_config)
                
                # Look for password field
                password_detected = self.check_for_password_field(page)
                
                if password_detected:
                    logger.info(f"Password-based authentication detected on: {url}")
                    self.result["auth_methods"]["password"]["detected"] = True
                    self.result["auth_methods"]["password"]["validity"] = "HIGH"
                    
                    # Add to recognized IDPs
                    if not any(idp.get("idp_name") == "USERNAME_PASSWORD" for idp in self.recognized_idps):
                        self.recognized_idps.append({
                            "idp_name": "USERNAME_PASSWORD",
                            "idp_integration": "PASSWORD",
                            "detection_method": "USERNAME_PASSWORD",
                            "login_page_candidate": url,
                            "validity": "HIGH"
                        })
                
                # Close browser
                PlaywrightHelper.close_context(context)
                
            except TimeoutError as e:
                logger.warning(f"Timeout in password detection on: {url}")
                logger.debug(e)
            
            except Error as e:
                logger.warning(f"Error in password detection on: {url}")
                logger.debug(e)
    
    def check_for_password_field(self, page: Page) -> bool:
        """Check for password input field."""
        try:
            # Look for password and username/email fields in a form
            has_password_form = page.evaluate("""
                () => {
                    // Check for password field
                    const passwordField = document.querySelector('input[type="password"]');
                    if (!passwordField) return false;
                    
                    // Find form containing password field or look at nearby elements
                    const form = passwordField.closest('form');
                    if (form) {
                        // Look for text/email input in the same form
                        const usernameField = form.querySelector('input[type="text"], input[type="email"], input[type="tel"], input:not([type])');
                        if (usernameField) return true;
                        
                        // Look for input with name/id containing username/email/phone indicators
                        const credentialKeywords = [
                            'user', 'username', 'email', 'login', 'account', 'mail', 'id', 
                            'phone', 'mobile', 'cell', 'telephone', 'number', 'contact', 
                            'userid', 'loginid', 'accountid'
                        ];
                        for (const keyword of credentialKeywords) {
                            const namedField = form.querySelector(`input[name*="${keyword}"], input[id*="${keyword}"]`);
                            if (namedField) return true;
                        }
                        
                        // Look for placeholders containing credential hints
                        const inputs = form.querySelectorAll('input:not([type="password"])');
                        for (const input of inputs) {
                            const placeholder = (input.placeholder || '').toLowerCase();
                            if (placeholder.includes('email') || 
                                placeholder.includes('username') || 
                                placeholder.includes('phone') || 
                                placeholder.includes('mobile') || 
                                placeholder.includes('login') ||
                                placeholder.includes('account')) {
                                return true;
                            }
                        }
                    }
                    
                    // If no form found or no username in form, check for username field near password field
                    const inputs = Array.from(document.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"], input:not([type])'));
                    for (const input of inputs) {
                        const rect1 = passwordField.getBoundingClientRect();
                        const rect2 = input.getBoundingClientRect();
                        
                        // Check if input is above the password field and relatively close to it
                        const isNearby = Math.abs(rect1.left - rect2.left) < 100 && 
                                       rect2.top < rect1.top && 
                                       rect1.top - rect2.bottom < 150;
                                       
                        if (isNearby) return true;
                    }
                    
                    // Check for login/credential labels near inputs
                    const labels = document.querySelectorAll('label');
                    for (const label of labels) {
                        const labelText = (label.textContent || '').toLowerCase();
                        if (labelText.includes('email') || 
                            labelText.includes('login') || 
                            labelText.includes('username') || 
                            labelText.includes('phone') || 
                            labelText.includes('mobile') || 
                            labelText.includes('user id')) {
                            return true;  
                        }
                    }
                    
                    // Check if there's a submit button nearby the password field
                    const submitButton = document.querySelector('button[type="submit"], input[type="submit"]');
                    if (submitButton) {
                        const passwordRect = passwordField.getBoundingClientRect();
                        const buttonRect = submitButton.getBoundingClientRect();
                        
                        // Check if the button is close to the password field
                        const isButtonNearby = Math.abs(passwordRect.left - buttonRect.left) < 150 && 
                                             buttonRect.top - passwordRect.bottom < 150;
                                             
                        if (isButtonNearby) return true;
                    }
                    
                    // Look for login/sign in text in a button near the password field
                    const buttons = Array.from(document.querySelectorAll('button, input[type="button"], a.btn, [role="button"]'));
                    for (const button of buttons) {
                        const buttonText = (button.textContent || '').toLowerCase();
                        if (buttonText.includes('login') || 
                            buttonText.includes('sign in') || 
                            buttonText.includes('log in') || 
                            buttonText.includes('submit') ||
                            buttonText.includes('continue') ||
                            buttonText.includes('next')) {
                            
                            const passwordRect = passwordField.getBoundingClientRect();
                            const buttonRect = button.getBoundingClientRect();
                            
                            // Check if the button is close to the password field
                            const isButtonNearby = Math.abs(passwordRect.left - buttonRect.left) < 150 && 
                                                buttonRect.top - passwordRect.bottom < 150;
                                                
                            if (isButtonNearby) return true;
                        }
                    }
                    
                    // If we have a password field but couldn't definitively find associated elements,
                    // still return true as it's likely a login form
                    return true;
                }
            """)
            
            if has_password_form:
                logger.info("Password-based authentication form detected")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error while checking for password field: {e}")
            return False 
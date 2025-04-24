import logging
import re
from playwright.sync_api import Page, sync_playwright, Error, TimeoutError
from modules.browser.browser import PlaywrightBrowser, PlaywrightHelper
from modules.helper.tmp import TmpHelper
from config.idp_rules import IdpRules

logger = logging.getLogger(__name__)

class PasswordFormDetector:
    """Detector for traditional username/password login forms."""
    
    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result
        
        self.browser_config = config["browser_config"]
        self.login_page_candidates = result["login_page_candidates"]
        self.recognized_idps = result["recognized_idps"]
        
        # Get form rules from IdpRules
        self.form_rules = IdpRules.get("PASSWORD_BASED", {}).get("form_rule", {})
        
    def start(self):
        """Begin detection of password login forms on login pages."""
        logger.info("Starting password form detection")
        
        # Process each login page candidate
        for lpc in self.login_page_candidates:
            url = lpc.get("url")
            if not url:
                continue
                
            # Check if page is reachable and analyzable
            reachable = lpc.get("resolved", {}).get("reachable", False)
            valid = lpc.get("content_analyzable", {}).get("valid", False)
            if not reachable or not valid:
                logger.info(f"Login page candidate is not reachable or analyzable: {url}")
                continue
            
            # Check for password form
            detected = self.detect_password_form(url)
            if detected:
                # Add to recognized_idps if not already present
                if not any(idp.get("idp_name") == "PASSWORD_BASED" for idp in self.recognized_idps):
                    self.recognized_idps.append({
                        "idp_name": "PASSWORD_BASED",
                        "idp_integration": "BASIC",
                        "recognition_strategy": "PASSWORD_FORM",
                        "element_validity": "HIGH",
                        "login_page_url": url
                    })
                    
                # Update auth_methods if present
                if "auth_methods" in self.result:
                    self.result["auth_methods"]["password"]["detected"] = True
                    self.result["auth_methods"]["password"]["validity"] = "HIGH"
                    
                # Only need to find one valid form
                return
                    
    def detect_password_form(self, url: str) -> bool:
        """Check if the page contains a username/password form."""
        with TmpHelper.tmp_dir() as pdir, sync_playwright() as pw:
            context, page = PlaywrightBrowser.instance(pw, self.browser_config, pdir)
            
            try:
                # Navigate to page
                PlaywrightHelper.navigate(page, url, self.browser_config)
                
                # Look for username/password input fields
                username_fields = self.form_rules.get("fields", {}).get("username", [])
                password_fields = self.form_rules.get("fields", {}).get("password", [])
                
                has_form = page.evaluate("""
                    (usernameFields, passwordFields) => {
                        // Function to check if an input matches any of the patterns
                        const matchesPattern = (input, patterns) => {
                            const name = input.name ? input.name.toLowerCase() : '';
                            const id = input.id ? input.id.toLowerCase() : '';
                            const placeholder = input.placeholder ? input.placeholder.toLowerCase() : '';
                            const type = input.type ? input.type.toLowerCase() : '';
                            
                            return patterns.some(pattern => {
                                const regex = new RegExp(pattern, 'i');
                                return regex.test(name) || regex.test(id) || regex.test(placeholder);
                            });
                        };
                        
                        // Find all input elements
                        const inputs = Array.from(document.querySelectorAll('input'));
                        
                        // Look for username field
                        const hasUsername = inputs.some(input => {
                            return (input.type === 'text' || input.type === 'email') && 
                                   matchesPattern(input, usernameFields);
                        });
                        
                        // Look for password field
                        const hasPassword = inputs.some(input => {
                            return input.type === 'password' || 
                                   matchesPattern(input, passwordFields);
                        });
                        
                        // Check if both username and password fields are present
                        if (hasUsername && hasPassword) {
                            // Look for a submit button or form
                            const forms = document.querySelectorAll('form');
                            const hasForm = forms.length > 0;
                            
                            const submitButtons = document.querySelectorAll('button[type="submit"], input[type="submit"]');
                            const hasSubmit = submitButtons.length > 0;
                            
                            return hasForm || hasSubmit;
                        }
                        
                        return false;
                    }
                """, username_fields, password_fields)
                
                # Close browser
                PlaywrightHelper.close_context(context)
                
                if has_form:
                    logger.info(f"Detected username/password form on {url}")
                return has_form
                
            except TimeoutError as e:
                logger.warning(f"Timeout in password form detection on: {url}")
                logger.debug(e)
                return False
                
            except Error as e:
                logger.warning(f"Error in password form detection on: {url}")
                logger.debug(e)
                return False 
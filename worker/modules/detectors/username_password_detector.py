import logging
import time
from typing import Tuple, List
from playwright.sync_api import Page
from modules.helper.detection import DetectionHelper
from modules.browser.browser import PlaywrightHelper


logger = logging.getLogger(__name__)


class UsernamePasswordDetector:
    """Detector for traditional username/password login forms."""

    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result
        
        self.browser_config = config["browser_config"]
        self.artifacts_config = config["artifacts_config"]
        self.store_username_password_screenshot = config["artifacts_config"].get("store_username_password_screenshot", False)


    def start(self):
        """Start username/password form detection."""
        logger.info("Starting username/password form detection")
        
        # Get login page candidates from result
        login_page_candidates = self.result.get("login_page_candidates", [])
        
        # Process each login page candidate
        for lpc in login_page_candidates:
            lpc_url = lpc.get("login_page_candidate")
            
            # Check if login page candidate is reachable and analyzable
            reachable = lpc.get("resolved", {}).get("reachable", False)
            valid = lpc.get("content_analyzable", {}).get("valid", False)
            
            if not (reachable and valid):
                continue
                
            logger.info(f"Starting username/password form detection on: {lpc_url}")
            
            try:
                # Detect login forms on the page
                self.detect_login_forms(lpc_url)
                
            except Exception as e:
                logger.error(f"Error in username/password form detection: {e}")


    def detect_login_forms(self, url: str):
        """Detect login forms on the page."""
        # Create a function to evaluate in the browser context
        # This function looks for common input patterns that indicate login forms
        script = """() => {
            const forms = Array.from(document.forms);
            const results = [];
            
            // Check for forms with password fields
            const passwordForms = forms.filter(form => 
                Array.from(form.elements).some(el => 
                    el.type === 'password'
                )
            );
            
            for (const form of passwordForms) {
                const formElements = Array.from(form.elements);
                const pwField = formElements.find(el => el.type === 'password');
                
                // Find possible username fields (usually comes before password)
                const usernameFields = formElements.filter(el => 
                    (el.type === 'text' || el.type === 'email' || el.type === 'tel') && 
                    (el.name?.toLowerCase().includes('user') || 
                     el.name?.toLowerCase().includes('email') || 
                     el.name?.toLowerCase().includes('login') ||
                     el.id?.toLowerCase().includes('user') || 
                     el.id?.toLowerCase().includes('email') || 
                     el.id?.toLowerCase().includes('login') ||
                     el.placeholder?.toLowerCase().includes('user') ||
                     el.placeholder?.toLowerCase().includes('email') ||
                     el.placeholder?.toLowerCase().includes('username'))
                );
                
                // Get position and dimensions for highlighting
                const formRect = form.getBoundingClientRect();
                const pwRect = pwField.getBoundingClientRect();
                
                let formInfo = {
                    action: form.action,
                    method: form.method,
                    id: form.id,
                    className: form.className,
                    x: formRect.x,
                    y: formRect.y,
                    width: formRect.width,
                    height: formRect.height,
                    hasUsername: usernameFields.length > 0,
                    usernameType: usernameFields.length > 0 ? usernameFields[0].type : null,
                    usernameName: usernameFields.length > 0 ? usernameFields[0].name : null,
                    usernameId: usernameFields.length > 0 ? usernameFields[0].id : null,
                    passwordName: pwField.name,
                    passwordId: pwField.id,
                    submitButton: null,
                    submitButtonText: null
                };
                
                // Find submit button
                const submitButton = formElements.find(el => 
                    el.type === 'submit' || 
                    (el.tagName === 'BUTTON' && 
                     (el.type === 'submit' || !el.type || el.type === 'button'))
                );
                
                if (submitButton) {
                    formInfo.submitButton = true;
                    formInfo.submitButtonText = submitButton.textContent?.trim() || submitButton.value;
                }
                
                results.push(formInfo);
            }
            
            // Also check for standalone password fields
            if (results.length === 0) {
                const passwordFields = Array.from(document.querySelectorAll('input[type="password"]'));
                
                for (const pwField of passwordFields) {
                    const pwRect = pwField.getBoundingClientRect();
                    
                    // Look for nearby username field
                    const usernameField = Array.from(document.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"]'))
                        .find(input => {
                            const inputRect = input.getBoundingClientRect();
                            // Assume username is near/above password
                            return Math.abs(inputRect.x - pwRect.x) < 100 && 
                                   inputRect.y <= pwRect.y && 
                                   inputRect.y > pwRect.y - 150;
                        });
                    
                    let formInfo = {
                        action: pwField.form?.action || null,
                        method: pwField.form?.method || null,
                        id: pwField.form?.id || null,
                        className: pwField.form?.className || null,
                        x: pwRect.x - 20, // Add some padding
                        y: usernameField ? Math.min(usernameField.getBoundingClientRect().y, pwRect.y) - 20 : pwRect.y - 20,
                        width: pwRect.width + 40,
                        height: (usernameField ? 
                                Math.max(usernameField.getBoundingClientRect().y + usernameField.getBoundingClientRect().height, pwRect.y + pwRect.height) : 
                                pwRect.y + pwRect.height) - 
                                (usernameField ? usernameField.getBoundingClientRect().y : pwRect.y) + 40,
                        hasUsername: !!usernameField,
                        usernameType: usernameField?.type || null,
                        usernameName: usernameField?.name || null,
                        usernameId: usernameField?.id || null,
                        passwordName: pwField.name,
                        passwordId: pwField.id,
                        submitButton: null,
                        submitButtonText: null
                    };
                    
                    // Look for nearby submit button
                    const submitButton = Array.from(document.querySelectorAll('button[type="submit"], input[type="submit"], button'))
                        .find(btn => {
                            const btnRect = btn.getBoundingClientRect();
                            // Assume submit is near/below password
                            return Math.abs(btnRect.x - pwRect.x) < 150 && 
                                   btnRect.y >= pwRect.y && 
                                   btnRect.y < pwRect.y + 150;
                        });
                    
                    if (submitButton) {
                        formInfo.submitButton = true;
                        formInfo.submitButtonText = submitButton.textContent?.trim() || submitButton.value;
                    }
                    
                    results.push(formInfo);
                }
            }
            
            return results;
        }"""
        
        # Get a page to run the script
        with PlaywrightHelper.get_browser_for_page(url, self.browser_config) as page:
            # Take screenshot if needed for visualization
            screenshot = PlaywrightHelper.take_screenshot(page) if self.store_username_password_screenshot else None
            
            # Execute the script to find login forms
            forms = page.evaluate(script)
            
            if forms:
                logger.info(f"Found {len(forms)} potential login form(s) on {url}")
                
                # Process each detected form
                for form in forms:
                    # Determine form validity based on features
                    validity = self._get_form_validity(form)
                    
                    # Create form entry for result
                    form_entry = {
                        "idp_name": "USERNAME_PASSWORD",
                        "login_page_url": url,
                        "recognition_strategy": "FORM_DETECTION",
                        "element_validity": validity,
                        "element_coordinates_x": form.get("x"),
                        "element_coordinates_y": form.get("y"),
                        "element_width": form.get("width"),
                        "element_height": form.get("height"),
                        "form_action": form.get("action"),
                        "form_method": form.get("method"),
                        "has_username_field": form.get("hasUsername"),
                        "has_submit_button": form.get("submitButton"),
                        "submit_button_text": form.get("submitButtonText"),
                    }
                    
                    # Add screenshot with highlighted form area if enabled
                    if screenshot and self.store_username_password_screenshot:
                        from modules.helper.image import ImageHelper
                        form_entry["username_password_screenshot"] = ImageHelper.base64comppng_draw_rectangle(
                            screenshot, form.get("x"), form.get("y"), form.get("width"), form.get("height")
                        )
                    
                    # Add form to analysis results
                    self.result["analysis_results"]["username_password_forms"].append({
                        "form_location": form_entry["login_page_url"],
                        "input_count": 2 if form_entry["has_username_field"] else 1
                    })
                    
                    if "USERNAME_PASSWORD" not in self.result["analysis_results"]["detected_methods"]:
                        self.result["analysis_results"]["detected_methods"].append("USERNAME_PASSWORD")


    def _get_form_validity(self, form: dict) -> str:
        """Determine the validity of a detected login form."""
        # Higher validity if form has both username and password fields plus submit button
        if (form.get("hasUsername") and 
            form.get("submitButton") and 
            form.get("submitButtonText") and 
            any(text in form.get("submitButtonText", "").lower() 
                for text in ["login", "sign in", "log in", "submit", "continue"])):
            return "HIGH"
        
        # Medium validity if form has username and password fields
        elif form.get("hasUsername"):
            return "MEDIUM"
        
        # Low validity if form only has password field
        else:
            return "LOW"

import logging
import re
from typing import List, Tuple
from playwright.sync_api import Page
from modules.browser.browser import PlaywrightHelper
from modules.helper.image import ImageHelper
from modules.helper.detection import DetectionHelper


logger = logging.getLogger(__name__)


class MFADetector:
    """Detector for Multi-Factor Authentication (MFA/2FA) prompts and inputs."""

    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result
        
        self.browser_config = config["browser_config"]
        self.artifacts_config = config["artifacts_config"]
        self.store_mfa_screenshot = config["artifacts_config"].get("store_mfa_screenshot", False)
        

    def start(self):
        """Start MFA detection on login pages."""
        logger.info("Starting MFA/2FA detection")
        
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
                
            logger.info(f"Starting MFA/2FA detection on: {lpc_url}")
            
            try:
                # Detect MFA elements on the page
                self.detect_mfa_elements(lpc_url)
                
            except Exception as e:
                logger.error(f"Error in MFA/2FA detection: {e}")


    def detect_mfa_elements(self, url: str):
        """Detect MFA related elements on the page."""
        # Create a function to evaluate in the browser context to find MFA elements
        script = """() => {
            const results = [];
            
            // Common MFA-related text patterns
            const mfaPatterns = [
                /two[\\s-]*factor|2fa|multi[\\s-]*factor|mfa|verification[\\s-]*code|one[\\s-]*time[\\s-]*code|authentication[\\s-]*code|security[\\s-]*code|one[\\s-]*time[\\s-]*password|totp|authenticator[\\s-]*app|sms[\\s-]*code|email[\\s-]*code|backup[\\s-]*code|security[\\s-]*key|verification/i
            ];
            
            // Check for headers, labels, and text that indicate MFA
            const textElements = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6, p, label, div, span')];
            
            for (const el of textElements) {
                // Skip hidden elements
                if (el.offsetParent === null) continue;
                
                const textContent = el.textContent.trim();
                
                if (textContent && mfaPatterns.some(pattern => pattern.test(textContent))) {
                    const rect = el.getBoundingClientRect();
                    
                    // Find nearby input fields for verification codes
                    const nearbyInputs = Array.from(document.querySelectorAll('input'))
                        .filter(input => {
                            const inputRect = input.getBoundingClientRect();
                            // Check if input is below or near the text
                            return (inputRect.y >= rect.y && 
                                    inputRect.y < rect.y + 200 && 
                                    Math.abs(inputRect.x - rect.x) < 300);
                        });
                    
                    // Get types and attributes of nearby inputs
                    const inputDetails = nearbyInputs.map(input => ({
                        type: input.type,
                        name: input.name,
                        id: input.id,
                        placeholder: input.placeholder,
                        maxLength: input.maxLength,
                        pattern: input.pattern
                    }));
                    
                    results.push({
                        text: textContent,
                        x: rect.x,
                        y: rect.y,
                        width: rect.width,
                        height: rect.height,
                        element: el.tagName.toLowerCase(),
                        hasInputs: nearbyInputs.length > 0,
                        inputCount: nearbyInputs.length,
                        inputDetails: inputDetails
                    });
                }
            }
            
            // Check for specific input patterns that suggest verification codes
            // e.g., short inputs with max length of 4-8 characters, or multiple small inputs in a row
            if (results.length === 0) {
                // Look for verification code inputs without clear text labels
                const potentialCodeInputs = Array.from(document.querySelectorAll('input'))
                    .filter(input => {
                        // Small text inputs that are likely for verification codes
                        return (input.type === 'text' || input.type === 'tel' || input.type === 'number') && 
                               (
                                   // Has a maxlength attribute of 4-8 characters
                                   (input.maxLength >= 4 && input.maxLength <= 8) ||
                                   // Or has a pattern attribute for digits
                                   input.pattern?.includes('\\d') ||
                                   // Or has a name or id suggesting it's a verification input
                                   /code|verification|otp|totp|2fa|mfa/i.test(input.name || input.id || input.placeholder || '')
                               );
                    });
                
                if (potentialCodeInputs.length > 0) {
                    // Group inputs that are horizontally aligned (common for separated digit inputs)
                    const codeGroups = [];
                    let currentGroup = [];
                    
                    // Sort by Y position to find rows
                    potentialCodeInputs.sort((a, b) => 
                        a.getBoundingClientRect().y - b.getBoundingClientRect().y
                    );
                    
                    let lastY = -1;
                    for (const input of potentialCodeInputs) {
                        const rect = input.getBoundingClientRect();
                        
                        // If this input is on a new line or is the first input
                        if (lastY === -1 || Math.abs(rect.y - lastY) > 10) {
                            if (currentGroup.length > 0) {
                                codeGroups.push([...currentGroup]);
                                currentGroup = [];
                            }
                        }
                        
                        currentGroup.push(input);
                        lastY = rect.y;
                    }
                    
                    if (currentGroup.length > 0) {
                        codeGroups.push([...currentGroup]);
                    }
                    
                    // Process the groups
                    for (const group of codeGroups) {
                        // Most verification code inputs have multiple boxes or a single input with maxlength
                        if (group.length >= 4 || (group.length === 1 && group[0].maxLength >= 4)) {
                            // Get bounding rectangle that encompasses all inputs in the group
                            const rects = group.map(i => i.getBoundingClientRect());
                            const groupRect = {
                                x: Math.min(...rects.map(r => r.x)),
                                y: Math.min(...rects.map(r => r.y)),
                                right: Math.max(...rects.map(r => r.right)),
                                bottom: Math.max(...rects.map(r => r.bottom))
                            };
                            
                            const width = groupRect.right - groupRect.x;
                            const height = groupRect.bottom - groupRect.y;
                            
                            // Get nearby text that might explain the code input
                            const nearbyText = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6, p, label, div, span'))
                                .filter(el => {
                                    if (el.offsetParent === null) return false; // Skip hidden elements
                                    
                                    const textRect = el.getBoundingClientRect();
                                    // Look for text above the inputs within reasonable distance
                                    return textRect.y < groupRect.y && 
                                           textRect.y > groupRect.y - 150 &&
                                           Math.abs(textRect.x - groupRect.x) < width + 100;
                                })
                                .map(el => el.textContent.trim())
                                .join(' ');
                            
                            results.push({
                                text: nearbyText || 'Verification Code Input',
                                x: groupRect.x,
                                y: groupRect.y,
                                width: width,
                                height: height,
                                element: 'input-group',
                                hasInputs: true,
                                inputCount: group.length,
                                inputDetails: group.map(input => ({
                                    type: input.type,
                                    name: input.name,
                                    id: input.id,
                                    placeholder: input.placeholder,
                                    maxLength: input.maxLength,
                                    pattern: input.pattern
                                }))
                            });
                        }
                    }
                }
            }
            
            return results;
        }"""
        
        # Get a page to run the script
        with PlaywrightHelper.get_browser_for_page(url, self.browser_config) as page:
            # Take screenshot for visualization if enabled
            screenshot = PlaywrightHelper.take_screenshot(page) if self.store_mfa_screenshot else None
            
            # Execute the script to find MFA elements
            mfa_elements = page.evaluate(script)
            
            if mfa_elements:
                logger.info(f"Found {len(mfa_elements)} potential MFA/2FA element(s) on {url}")
                
                # Process detected MFA elements
                for mfa_element in mfa_elements:
                    # Determine if this is likely a 2FA/MFA prompt
                    mfa_type, validity = self._classify_mfa_element(mfa_element)
                    
                    if mfa_type:
                        logger.info(f"Detected {mfa_type} with {validity} validity")
                        
                        # Create MFA entry
                        mfa_entry = {
                            "idp_name": "MFA_GENERIC",
                            "login_page_url": url,
                            "recognition_strategy": "MFA_DETECTION",
                            "element_validity": validity,
                            "element_coordinates_x": mfa_element.get("x"),
                            "element_coordinates_y": mfa_element.get("y"),
                            "element_width": mfa_element.get("width"),
                            "element_height": mfa_element.get("height"),
                            "mfa_type": mfa_type,
                            "mfa_text": mfa_element.get("text"),
                            "has_code_inputs": mfa_element.get("hasInputs", False),
                            "input_count": mfa_element.get("inputCount", 0)
                        }
                        
                        # Add screenshot with highlighted MFA area if enabled
                        if screenshot and self.store_mfa_screenshot:
                            mfa_entry["mfa_screenshot"] = ImageHelper.base64comppng_draw_rectangle(
                                screenshot, 
                                mfa_element.get("x"), 
                                mfa_element.get("y"), 
                                mfa_element.get("width"), 
                                mfa_element.get("height")
                            )
                        
                        # Add MFA entry to analysis results
                        self.result["analysis_results"]["mfa_implementations"].append({
                            "mfa_type": mfa_type,
                            "implementation": mfa_entry["mfa_text"]
                        })
                        
                        if "MFA" not in self.result["analysis_results"]["detected_methods"]:
                            self.result["analysis_results"]["detected_methods"].append("MFA")


    def _classify_mfa_element(self, element: dict) -> Tuple[str, str]:
        """
        Classify the type of MFA and determine validity.
        
        Returns:
            Tuple[str, str]: MFA type and validity (HIGH, MEDIUM, LOW)
        """
        text = element.get("text", "").lower()
        has_inputs = element.get("hasInputs", False)
        input_details = element.get("inputDetails", [])
        
        # Default MFA type and validity
        mfa_type = "GENERIC_MFA"
        validity = "LOW"
        
        # Check for specific types of MFA
        if re.search(r'authenticator|totp', text):
            mfa_type = "AUTHENTICATOR_APP"
            validity = "MEDIUM"
        elif re.search(r'sms|phone|text message', text):
            mfa_type = "SMS_CODE"
            validity = "MEDIUM"
        elif re.search(r'email', text):
            mfa_type = "EMAIL_CODE"
            validity = "MEDIUM"
        elif re.search(r'backup', text):
            mfa_type = "BACKUP_CODE"
            validity = "MEDIUM"
        elif re.search(r'security key|passkey|webauthn|yubikey', text):
            mfa_type = "SECURITY_KEY"
            validity = "MEDIUM"
        
        # Enhance validity based on input presence and characteristics
        if has_inputs:
            # Look for telltale signs of verification code inputs
            digit_inputs = any(
                detail.get("type") == "tel" or 
                detail.get("pattern", "").find("\\d") >= 0 or
                (detail.get("maxLength", 0) > 0 and detail.get("maxLength") <= 8)
                for detail in input_details
            )
            
            if digit_inputs:
                validity = "HIGH"
            elif len(input_details) > 0:
                validity = "MEDIUM"
            
            # Very clear MFA language with appropriate inputs
            if (re.search(r'verification code|2fa code|security code|one-time code', text) and 
                (digit_inputs or element.get("inputCount", 0) >= 4)):
                validity = "HIGH"
        
        return mfa_type, validity

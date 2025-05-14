import logging
import time
from typing import Tuple, List, Dict, Any
from playwright.sync_api import Page, Response
from modules.browser.browser import PlaywrightHelper
from modules.helper.detection import DetectionHelper
from config.idp_rules import IdpRules

logger = logging.getLogger(__name__)

class PasskeyDetector:
    """
    Detector for Passkey buttons, text references, and elements with a comprehensive
    multi-layered detection strategy
    """

    def __init__(self, result: dict, page: Page):
        self.result = result
        self.page = page
        self.url = None
        self.passkey_keywords = IdpRules["PASSKEY BUTTON"]["keywords"]
        self.script_contents = []  # Store script contents for JS detection

    def detect_passkey_button(self, url: str) -> Tuple[bool, dict]:
        """
        Detects passkey buttons or links on the current page using a comprehensive
        multi-layered detection approach
        """
        logger.info(f"Checking for passkey buttons on: {url}")
        self.url = url
        
        # Check if this URL already has a passkey detection to avoid duplicates
        for idp in self.result.get("recognized_idps", []):
            if (idp.get("idp_name") in ["PASSKEY BUTTON", "PASSKEY UI", "PASSKEY JS"] and 
                idp.get("login_page_url") == url and 
                idp.get("detection_method") in ["PASSKEY-BUTTON", "PASSKEY-KEYWORD", "PASSKEY-HIDDEN", 
                                             "PASSKEY-UI", "PASSKEY-JS"]):
                logger.info(f"Passkey already detected for {url}, skipping")
                return False, None
        
        # Check if WebAuthn API is available (sanity check)
        webauthn_available = self._check_webauthn_availability()
        if not webauthn_available:
            logger.info("WebAuthn API not available, skipping passkey detection")
            return False, None
        
        # Enhanced UI detection
        ui_found, ui_details = self._detect_passkey_ui()
        if ui_found:
            logger.info(f"PASSKEY UI detected with type: {ui_details['type']}")
            passkey_info = {
                "idp_name": "PASSKEY UI",
                "idp_sdk": ui_details["type"],
                "idp_integration": "CUSTOM",
                "idp_frame": "SAME_WINDOW",
                "login_page_url": self.url,
                "element_validity": "HIGH",
                "detection_method": "PASSKEY-UI",
                "passkey_type": ui_details["type"],
                "detection_details": ui_details
            }
            return True, passkey_info

        # Enhanced JS detection
        js_found, js_details = self._detect_passkey_js()
        if js_found:
            logger.info(f"PASSKEY JS detected with type: {js_details['type']}")
            # Use confidence level from detection to set element validity
            validity = "HIGH" if js_details.get("confidence") == "HIGH" else "MEDIUM"
            passkey_info = {
                "idp_name": "PASSKEY JS",
                "idp_sdk": js_details["type"],
                "idp_integration": "CUSTOM",
                "idp_frame": "SAME_WINDOW",
                "login_page_url": self.url,
                "element_validity": validity,
                "detection_method": "PASSKEY-JS",
                "passkey_type": js_details["type"],
                "detection_details": js_details
            }
            return True, passkey_info
            
        return False, None

    def _check_webauthn_availability(self) -> bool:
        """
        Check if WebAuthn API is available in the browser
        """
        try:
            webauthn_available = self.page.evaluate('''
                () => typeof window.PublicKeyCredential !== 'undefined'
            ''')
            logger.debug(f"WebAuthn API availability: {webauthn_available}")
            return webauthn_available
        except Exception as e:
            logger.debug(f"Error checking WebAuthn API availability: {e}")
            return False

    def _detect_passkey_ui(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Comprehensive detection of passkey UI elements using multiple techniques
        """
        try:
            result = self.page.evaluate('''
            () => {
                const results = {
                    found: false,
                    type: "",
                    evidence: {},
                    details: {}
                };
                
                // 1. Check WebAuthn API availability
                const hasWebAuthn = typeof window.PublicKeyCredential !== 'undefined';
                results.details.hasWebAuthn = hasWebAuthn;
                
                if (!hasWebAuthn) {
                    return results;
                }
                
                // 2. Standard Web-Component / Custom-Element scan
                const wcEls = document.querySelectorAll(
                    'webauthn-authenticator, public-key-credential-login, [is="passkey-login-button"]'
                );
                results.details.webComponents = Array.from(wcEls).map(el => el.tagName);
                
                // 3. "Autocomplete" & ARIA attribute scan
                const autoEls = document.querySelectorAll('input[autocomplete="webauthn"], input[type="publickey"]');
                const ariaEls = Array.from(
                    document.querySelectorAll('button[aria-label], div[role="button"][aria-label]')
                ).filter(el => /passkey|security key|webauthn/i.test(el.getAttribute('aria-label')));
                
                results.details.autocompleteElements = Array.from(autoEls).map(el => ({
                    tag: el.tagName,
                    type: el.type,
                    autocomplete: el.getAttribute('autocomplete')
                }));
                
                results.details.ariaElements = ariaEls.map(el => ({
                    tag: el.tagName,
                    role: el.getAttribute('role'),
                    ariaLabel: el.getAttribute('aria-label')
                }));
                
                // 4. Visible-text button/link scan
                const textEls = Array.from(document.querySelectorAll('button, a, div[role="button"]'))
                    .filter(el => /passkey|face id|touch id|security key|webauthn|fingerprint/i.test(el.innerText));
                
                results.details.textElements = textEls.map(el => ({
                    tag: el.tagName,
                    role: el.getAttribute('role'),
                    text: el.innerText.trim()
                }));
                
                // 5. Icon-based detection
                const iconEls = document.querySelectorAll(
                    'svg[aria-label*="fingerprint" i], svg[aria-label*="face" i], ' +
                    'svg[aria-label*="security key" i], svg[aria-label*="passkey" i], ' +
                    'img[alt*="fingerprint" i], img[alt*="face id" i], ' +
                    'img[alt*="touch id" i], img[alt*="security key" i], ' +
                    'img[alt*="passkey" i]'
                );
                
                results.details.iconElements = Array.from(iconEls).map(el => ({
                    tag: el.tagName,
                    ariaLabel: el.getAttribute('aria-label'),
                    alt: el.getAttribute('alt')
                }));
                
                // Additional checks for input fields and form elements with passkey hints
                const inputFields = document.querySelectorAll('input[type="password"], input[placeholder*="passkey" i]');
                const formElements = document.querySelectorAll('form');
                
                // Look for forms with potential passkey indicators
                const passKeyForms = Array.from(formElements).filter(form => {
                    const formHTML = form.innerHTML.toLowerCase();
                    return /passkey|webauthn|security key|face id|touch id|fingerprint/i.test(formHTML);
                });
                
                results.details.potentialPasskeyInputs = inputFields.length;
                results.details.potentialPasskeyForms = passKeyForms.length;
                
                // 6. Overall detection result
                // At least one UI signal needed for positive detection
                const hasUISignal = results.details.webComponents.length > 0 || 
                                   results.details.autocompleteElements.length > 0 ||
                                   results.details.ariaElements.length > 0 ||
                                   results.details.textElements.length > 0 || 
                                   results.details.iconElements.length > 0 ||
                                   passKeyForms.length > 0;
                
                if (hasWebAuthn && hasUISignal) {
                    results.found = true;
                    
                    // Determine passkey type based on detected UI elements
                    if (results.details.textElements.some(el => /face id|touch id/i.test(el.text)) ||
                        results.details.iconElements.some(el => /face id|touch id/i.test(el.alt || el.ariaLabel || ''))) {
                        results.type = "WEBAUTHN";
                        results.details.platform = "APPLE";
                    } else if (results.details.textElements.some(el => /fingerprint/i.test(el.text)) ||
                              results.details.iconElements.some(el => /fingerprint/i.test(el.alt || el.ariaLabel || ''))) {
                        results.type = "WEBAUTHN";
                        results.details.platform = "ANDROID";
                    } else {
                        results.type = "WEBAUTHN";
                        results.details.platform = "GENERIC";
                    }
                    
                    // Gather evidence for the detection
                    results.evidence = {
                        hasWebComponents: results.details.webComponents.length > 0,
                        hasAutocompleteElements: results.details.autocompleteElements.length > 0,
                        hasAriaElements: results.details.ariaElements.length > 0,
                        hasTextElements: results.details.textElements.length > 0,
                        hasIconElements: results.details.iconElements.length > 0,
                        hasPasskeyForms: passKeyForms.length > 0
                    };
                    
                    // Assign confidence level to help determine validity
                    if (results.details.webComponents.length > 0 || results.details.autocompleteElements.length > 0) {
                        results.confidence = "HIGH"; // Most reliable signals
                    } else if (results.details.ariaElements.length > 0 || passKeyForms.length > 0) {
                        results.confidence = "MEDIUM"; // Good signals
                    } else {
                        results.confidence = "LOW"; // Least reliable signals
                    }
                }
                
                return results;
            }
            ''')
            
            logger.debug(f"Passkey UI detection result: {result}")
            return result.get("found", False), result
            
        except Exception as e:
            logger.debug(f"Error in enhanced passkey UI detection: {e}")
            return False, {"error": str(e)}

    def _detect_passkey_js(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Comprehensive detection of passkey JS implementation
        """
        try:
            # First collect all script contents
            self._collect_script_contents()
            
            # Then perform the detection
            result = self.page.evaluate('''
            () => {
                const results = {
                    found: false,
                    type: "",
                    evidence: {},
                    details: {}
                };
                
                // 1. Check WebAuthn API availability
                const hasWebAuthn = typeof window.PublicKeyCredential !== 'undefined';
                results.details.hasWebAuthn = hasWebAuthn;
                
                if (!hasWebAuthn) {
                    return results;
                }
                
                // 2. Collect inline scripts
                const inlineScripts = Array.from(document.scripts)
                    .filter(s => !s.src)
                    .map(s => s.textContent);
                
                results.details.inlineScriptCount = inlineScripts.length;
                
                // 3. Check for WebAuthn patterns in scripts
                const patterns = [
                    /navigator\.credentials\.create\s*\(\s*\{[\s\S]*?publicKey\s*:/,
                    /navigator\.credentials\.get\s*\(\s*\{[\s\S]*?publicKey\s*:/,
                    /PublicKeyCredential\.isUserVerifyingPlatformAuthenticatorAvailable/,
                    /\bPublicKeyCredential\b/
                ];
                
                // Check inline scripts
                const inlineMatches = inlineScripts.some(text => 
                    patterns.some(pattern => pattern.test(text))
                );
                
                results.details.inlineMatches = inlineMatches;
                
                // Check for WebAuthn in global scope
                const globalWebAuthnReferences = (function() {
                    try {
                        return typeof PublicKeyCredential !== 'undefined' && 
                               typeof navigator.credentials !== 'undefined' &&
                               typeof navigator.credentials.create === 'function' &&
                               typeof navigator.credentials.get === 'function';
                    } catch (e) {
                        return false;
                    }
                })();
                
                results.details.globalWebAuthnReferences = globalWebAuthnReferences;
                
                // 4. Check for event listeners that might trigger WebAuthn
                const potentialTriggerElements = Array.from(
                    document.querySelectorAll('button, a, [role="button"]')
                ).filter(el => 
                    /passkey|webauthn|fingerprint|face id|touch id|security key/i.test(
                        el.innerText || el.getAttribute('aria-label') || ''
                    )
                );
                
                results.details.potentialTriggers = potentialTriggerElements.length;
                
                // 5. Overall detection result
                // More stringent criteria: require actual code patterns, not just API availability
                const hasJsEvidence = inlineMatches;
                
                // Check for actual WebAuthn implementation, not just global API
                const hasWebAuthnImplementation = (function() {
                    try {
                        // Look for actual WebAuthn implementation indicators
                        // 1. Check for custom WebAuthn-related functions in window/global scope
                        const globalFunctions = Object.keys(window).filter(key => 
                            /passkey|webauthn|credential|biometric|fingerprint/i.test(key) && 
                            typeof window[key] === 'function'
                        );
                        
                        // 2. Check if any script has registered event listeners to potential passkey buttons
                        const hasPasskeyEventListeners = potentialTriggerElements.length > 0 && 
                            potentialTriggerElements.some(el => {
                                // Get all event listeners (simplified check)
                                const hasClickHandler = el.onclick || el.getAttribute('onclick');
                                return !!hasClickHandler;
                            });
                        
                        // 3. Search for WebAuthn-specific data attributes which indicate implementation
                        const webAuthnDataAttrs = document.querySelectorAll('[data-webauthn], [data-passkey], [data-credential]');
                        
                        return globalFunctions.length > 0 || hasPasskeyEventListeners || webAuthnDataAttrs.length > 0;
                    } catch (e) {
                        return false;
                    }
                })();
                
                results.details.hasWebAuthnImplementation = hasWebAuthnImplementation;
                
                // Require stronger evidence than just API availability:
                // Either found concrete code patterns OR a combination of potential UI triggers and implementation indicators
                if (hasWebAuthn && (
                    inlineMatches || // Direct evidence in script code
                    (potentialTriggerElements.length > 0 && hasWebAuthnImplementation) // UI + implementation indicators
                )) {
                    results.found = true;
                    results.type = "WEBAUTHN";
                    
                    // Gather evidence for the detection
                    results.evidence = {
                        hasInlineMatches: inlineMatches,
                        hasGlobalReferences: globalWebAuthnReferences,
                        hasPotentialTriggers: potentialTriggerElements.length > 0,
                        hasWebAuthnImplementation: hasWebAuthnImplementation
                    };
                    
                    // Confidence scoring based on evidence strength
                    if (inlineMatches) {
                        results.confidence = "HIGH"; // Direct script evidence
                    } else if (potentialTriggerElements.length > 0 && hasWebAuthnImplementation) {
                        results.confidence = "MEDIUM"; // Indirect evidence
                    } else {
                        results.confidence = "LOW"; 
                    }
                }
                
                return results;
            }
            ''')
            
            logger.debug(f"Passkey JS detection result: {result}")
            return result.get("found", False), result
            
        except Exception as e:
            logger.debug(f"Error in enhanced passkey JS detection: {e}")
            return False, {"error": str(e)}

    def _collect_script_contents(self):
        """
        Collect script contents from the page for JS detection
        """
        try:
            # Get all script sources
            scripts = self.page.evaluate('''
            () => {
                return Array.from(document.scripts)
                    .filter(s => s.src)
                    .map(s => s.src);
            }
            ''')
            
            # We'll only store the inline scripts since we can't easily fetch external scripts
            # in the current implementation without modifying the page navigation flow
            logger.debug(f"Found {len(scripts)} external scripts")
            
            # Try to extract external script content when possible
            external_scripts = []
            try:
                # Sample up to 5 external scripts to analyze
                for script_src in scripts[:5]:
                    try:
                        # Check if this is a same-origin script we can access
                        script_content = self.page.evaluate(f'''
                        async () => {{
                            try {{
                                const response = await fetch("{script_src}");
                                if (response.ok) {{
                                    return await response.text();
                                }}
                            }} catch (e) {{
                                // Ignore cross-origin errors
                                return null;
                            }}
                            return null;
                        }}
                        ''')
                        if script_content:
                            external_scripts.append(script_content)
                    except Exception as e:
                        logger.debug(f"Error fetching external script {script_src}: {e}")
            except Exception as e:
                logger.debug(f"Error processing external scripts: {e}")
            
            # Get inline scripts
            inline_scripts = self.page.evaluate('''
            () => {
                return Array.from(document.scripts)
                    .filter(s => !s.src)
                    .map(s => s.textContent);
            }
            ''')
            
            self.script_contents = inline_scripts + external_scripts
            logger.debug(f"Collected {len(inline_scripts)} inline scripts and {len(external_scripts)} external scripts")
            
        except Exception as e:
            logger.debug(f"Error collecting script contents: {e}")

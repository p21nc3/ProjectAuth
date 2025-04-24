import logging
from typing import List, Any, Dict
from pathlib import Path
import json
from playwright.sync_api import Page

logger = logging.getLogger(__name__)

class NavigatorCredentialsDetector:
    """Detector for navigator.credentials API usage to identify WebAuthn/Passkey and password manager integration."""

    JS_DIR = Path(__file__).parent.parent / "browser" / "js"

    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result
        self.url = None
        
        # Initialize storage for detected credentials
        if "recognized_navcreds" not in self.result:
            self.result["recognized_navcreds"] = []

    def start(self, page: Page, url: str):
        """Start monitoring navigator.credentials API calls."""
        logger.info(f"Starting navigator.credentials detection on {url}")
        self.url = url
        
        # Inject the tracking script
        try:
            with open(self.JS_DIR / "navcred-tracker.js", "r") as f:
                page.evaluate(f.read())
            
            # Set up callback function to receive events
            page.expose_function("_ssomon_navcred_callback", 
                               lambda function_name, params: self.callback(function_name, params))
            
            logger.info("Navigator.credentials tracking initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize navigator.credentials tracking: {e}")
            return False

    def callback(self, function_name: str, function_params: List[Any]):
        """Handle credential API calls from the browser."""
        navcred = {
            "login_page_url": self.url,
            "function_name": function_name,
            "function_params": function_params
        }
        
        # Check if this is a new detection
        if self.url and not self.navcred_is_duplicate(navcred):
            self.result["recognized_navcreds"].append(navcred)
            
            # Check for PassKey (WebAuthn)
            if self.is_webauthn_request(function_name, function_params):
                logger.info(f"WebAuthn API detected via {function_name}")
                # Add to recognized_idps if not already there
                if not any(idp.get("idp_name") == "PASSKEY" for idp in self.result.get("recognized_idps", [])):
                    self.result["recognized_idps"].append({
                        "idp_name": "PASSKEY",
                        "idp_integration": "WEBAUTHN",
                        "recognition_strategy": "NAVIGATOR_CREDENTIALS",
                        "element_validity": "HIGH",
                        "login_page_url": self.url
                    })
                    
                    # Update auth_methods if present
                    if "auth_methods" in self.result:
                        self.result["auth_methods"]["passkey"]["detected"] = True
                        self.result["auth_methods"]["passkey"]["validity"] = "HIGH"

    def is_webauthn_request(self, function_name: str, params: List[Any]) -> bool:
        """Check if the credentials API call is for WebAuthn/passkey."""
        if function_name not in ["credentials.create", "credentials.get"]:
            return False
            
        # Look for publicKey parameter which indicates WebAuthn
        for param in params:
            if isinstance(param, dict) and "publicKey" in param:
                return True
        return False

    def navcred_is_duplicate(self, navcred: Dict) -> bool:
        """Check if this credential API call has already been captured."""
        for existing in self.result["recognized_navcreds"]:
            if (existing["login_page_url"] == navcred["login_page_url"] and
                existing["function_name"] == navcred["function_name"]):
                return True
        return False
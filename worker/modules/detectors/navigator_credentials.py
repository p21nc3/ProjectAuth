import logging
import json
from pathlib import Path
from typing import List, Any, Tuple
from playwright.sync_api import Page


logger = logging.getLogger(__name__)


class NavigatorCredentialsDetector:


    JS_DIR = Path(__file__).parent.parent / "browser" / "js"


    def __init__(self, result: dict, page: Page):
        self.result = result
        self.page = page
        self.url = None

        self.page.add_init_script(path=f"{self.JS_DIR / 'navcred-tracker.js'}")
        self.page.expose_function("_ssomon_navcred_callback", self.callback)


    def register_callback(self, url: str):
        logger.info(f"Registering navigator credentials callback on: {url}")
        self.url = url


    def unregister_callback(self, url: str):
        logger.info(f"Unregistering navigator credentials callback from: {url}")
        self.url = None


    def callback(self, function_name: str, function_params: List[Any]):
        navcred = {
            "login_page_url": self.url,
            "function_name": function_name,
            "function_params": function_params
        }
        if self.url and not self.navcred_is_duplicate(navcred):
            self.result["recognized_navcreds"].append(navcred)


    def navcred_is_duplicate(self, navcred: dict) -> bool:
        for rnc in self.result["recognized_navcreds"]:
            if (
                rnc["login_page_url"] == navcred["login_page_url"] and
                rnc["function_name"] == navcred["function_name"] and
                json.dumps(rnc["function_params"]) == json.dumps(navcred["function_params"])
            ):
                return True
        return False
        
    def detect_passkey_api(self, url: str) -> Tuple[bool, dict]:
        """
        Detect if WebAuthn API for Passkeys is being used
        """
        logger.info(f"Checking for Passkey WebAuthn API usage on: {url}")
        
        # Check if this URL already has a passkey API detection to avoid duplicates
        for idp in self.result.get("recognized_idps", []):
            if (idp.get("idp_name") == "PASSKEY BUTTON" and 
                idp.get("login_page_url") == url and 
                idp.get("detection_method") == "PASSKEY-API"):
                logger.info(f"Passkey API already detected for {url}, skipping")
                return False, None
        
        # Check if any recognized_navcreds contains WebAuthn related calls
        webauthn_functions = [
            "navigator.credentials.create",
            "navigator.credentials.get",
            "PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable"
        ]
        
        for navcred in self.result["recognized_navcreds"]:
            # Check if the navcred is for the current URL
            if navcred["login_page_url"] == url:
                # Check if the function name matches WebAuthn functions
                if any(func in navcred["function_name"] for func in webauthn_functions):
                    logger.info(f"WebAuthn API detected: {navcred['function_name']}")
                    
                    passkey_info = {
                        "idp_name": "PASSKEY BUTTON",
                        "idp_sdk": "WEBAUTHN",
                        "idp_integration": "CUSTOM",
                        "idp_frame": "SAME_WINDOW",
                        "login_page_url": url,
                        "element_validity": "HIGH",
                        "detection_method": "PASSKEY-API",
                        "webauthn_function": navcred["function_name"]
                    }
                    return True, passkey_info
        
        return False, None

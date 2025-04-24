import logging
import json
from pathlib import Path
from typing import List, Any
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
            # Add to analysis results
            self.result["analysis_results"]["stored_credentials"].append({
                "credential_type": "passkey" if "publicKey" in str(navcred["function_params"]) else "password",
                "source": "navigator.credentials"
            })
            
            if "NAVIGATOR_CREDENTIALS" not in self.result["analysis_results"]["detected_methods"]:
                self.result["analysis_results"]["detected_methods"].append("NAVIGATOR_CREDENTIALS")
            
            # Check for passkey-related function calls
            if function_name in ["credentials.get", "credentials.create"] and "PASSKEY" not in [idp.get("idp_name", "") for idp in self.result["recognized_idps"]]:
                # Add to recognized_idps if it's a passkey
                is_passkey = False
                
                # Check for WebAuthn-specific parameters
                if function_name == "credentials.get":
                    # Look for PublicKeyCredentialRequestOptions object
                    for param in function_params:
                        if isinstance(param, dict) and "publicKey" in param:
                            is_passkey = True
                            break
                elif function_name == "credentials.create":
                    # Look for PublicKeyCredentialCreationOptions object
                    for param in function_params:
                        if isinstance(param, dict) and "publicKey" in param:
                            is_passkey = True
                            break
                
                if is_passkey:
                    logger.info(f"Detected passkey usage via {function_name}")
                    self.result["recognized_idps"].append({
                        "idp_name": "PASSKEY",
                        "login_page_url": self.url,
                        "recognition_strategy": "NAVIGATOR_CREDENTIALS",
                        "element_validity": "HIGH",
                        "navcred_function": function_name,
                        "navcred_params": function_params
                    })


    def navcred_is_duplicate(self, navcred: dict) -> bool:
        for rnc in self.result["recognized_navcreds"]:
            if (
                rnc["login_page_url"] == navcred["login_page_url"] and
                rnc["function_name"] == navcred["function_name"] and
                json.dumps(rnc["function_params"]) == json.dumps(navcred["function_params"])
            ):
                return True
        return False
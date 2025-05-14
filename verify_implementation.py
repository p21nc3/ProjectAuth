#!/usr/bin/env python3

"""
Verification script for the new authentication detection implementations.
This script checks for all required files and configurations.
"""

import os
import sys
import importlib.util
from pathlib import Path

def print_success(message):
    print(f"✓ {message}")

def print_error(message):
    print(f"✗ {message}")

def print_info(message):
    print(f"ℹ {message}")

def print_warning(message):
    print(f"⚠ {message}")

def check_file_exists(file_path, file_description):
    if os.path.exists(file_path):
        print_success(f"{file_description} found at {file_path}")
        return True
    else:
        print_error(f"{file_description} not found at {file_path}")
        return False

def check_idp_rules():
    try:
        # Try to import the module
        spec = importlib.util.spec_from_file_location("idp_rules", "worker/config/idp_rules.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Check if new IDPs are defined
        idp_rules = getattr(module, "IdpRules", {})
        
        if "PASSKEY" in idp_rules:
            print_success("PASSKEY IDP rule is defined")
        else:
            print_error("PASSKEY IDP rule is missing")
            
        if "MFA_GENERIC" in idp_rules:
            print_success("MFA_GENERIC IDP rule is defined")
        else:
            print_error("MFA_GENERIC IDP rule is missing")
            
        if "PASSWORD_BASED" in idp_rules:
            print_success("PASSWORD_BASED IDP rule is defined")
        else:
            print_error("PASSWORD_BASED IDP rule is missing")
            
        return True
        
    except Exception as e:
        print_error(f"Error checking IDP rules: {e}")
        return False

def check_detector_modules():
    detector_files = [
        ("worker/modules/detectors/password_detector.py", "Password detector module"),
        ("worker/modules/detectors/mfa_detector.py", "MFA detector module"),
        ("worker/modules/detectors/passkey_detector.py", "Passkey detector module")
    ]
    
    all_found = True
    for file_path, description in detector_files:
        if not check_file_exists(file_path, description):
            all_found = False
    
    return all_found

def check_navcred_detector():
    file_path = "worker/modules/detectors/navigator_credentials.py"
    if not check_file_exists(file_path, "Navigator credentials detector module"):
        return False
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        if "detect_passkey_api" in content:
            print_success("Navigator credentials detector has detect_passkey_api method")
            return True
        else:
            print_error("Navigator credentials detector is missing detect_passkey_api method")
            return False
            
    except Exception as e:
        print_error(f"Error checking navigator credentials detector: {e}")
        return False

def check_metadata_detector():
    file_path = "worker/modules/detectors/metadata.py"
    if not check_file_exists(file_path, "Metadata detector module"):
        return False
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        if "webauthn_api" in content and "lastpass" in content:
            print_success("Metadata detector includes webauthn_api and lastpass fields")
            return True
        else:
            print_error("Metadata detector is missing webauthn_api or lastpass fields")
            return False
            
    except Exception as e:
        print_error(f"Error checking metadata detector: {e}")
        return False

def check_sso_button_detector():
    file_path = "worker/modules/detectors/sso_button.py"
    if not check_file_exists(file_path, "SSO button detector module"):
        return False
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        new_strategies = [
            "PASSWORD-FORM", 
            "MFA-MULTIPHASE", 
            "PASSKEY-KEYWORD", 
            "PASSKEY-API"
        ]
        
        all_found = True
        for strategy in new_strategies:
            if strategy in content:
                print_success(f"SSO button detector includes {strategy} strategy")
            else:
                print_error(f"SSO button detector is missing {strategy} strategy")
                all_found = False
                
        return all_found
            
    except Exception as e:
        print_error(f"Error checking SSO button detector: {e}")
        return False

def check_schema_updates():
    file_path = "brain/static/schema/landscape_analysis.json"
    if not check_file_exists(file_path, "Schema file"):
        return False
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        new_idps = ["PASSKEY", "MFA_GENERIC", "PASSWORD_BASED"]
        new_strategies = ["PASSWORD-FORM", "MFA-MULTIPHASE", "PASSKEY-KEYWORD", "PASSKEY-API"]
        
        all_found = True
        for idp in new_idps:
            if idp in content:
                print_success(f"Schema includes {idp} in idp_scope")
            else:
                print_error(f"Schema is missing {idp} in idp_scope")
                all_found = False
                
        for strategy in new_strategies:
            if strategy in content:
                print_success(f"Schema includes {strategy} in recognition_strategy_scope")
            else:
                print_error(f"Schema is missing {strategy} in recognition_strategy_scope")
                all_found = False
                
        return all_found
            
    except Exception as e:
        print_error(f"Error checking schema updates: {e}")
        return False

def check_admin_ui_updates():
    file_path = "brain/templates/views/admin.html"
    if not check_file_exists(file_path, "Admin UI template"):
        return False
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        if "{{ passkey_count|default('0') }}" in content and "{{ mfa_count|default('0') }}" in content and "{{ password_count|default('0') }}" in content:
            print_success("Admin UI template includes the new authentication counters")
            return True
        else:
            print_error("Admin UI template is missing one or more authentication counters")
            return False
            
    except Exception as e:
        print_error(f"Error checking admin UI updates: {e}")
        return False

def check_admin_route_updates():
    file_path = "brain/blueprints/bp_views.py"
    if not check_file_exists(file_path, "Admin view route"):
        return False
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        if "passkey_count" in content and "mfa_count" in content and "password_count" in content:
            print_success("Admin route includes passkey, MFA, and password counts")
            return True
        else:
            print_error("Admin route is missing one or more authentication count variables")
            return False
            
    except Exception as e:
        print_error(f"Error checking admin route updates: {e}")
        return False

def main():
    print_info("Verifying authentication detection implementation...")
    
    all_checks_passed = True
    
    # Check all components
    print_info("\nChecking IDP rules...")
    if not check_idp_rules():
        all_checks_passed = False
    
    print_info("\nChecking detector modules...")
    if not check_detector_modules():
        all_checks_passed = False
        
    print_info("\nChecking navigator credentials detector...")
    if not check_navcred_detector():
        all_checks_passed = False
        
    print_info("\nChecking metadata detector...")
    if not check_metadata_detector():
        all_checks_passed = False
        
    print_info("\nChecking SSO button detector...")
    if not check_sso_button_detector():
        all_checks_passed = False
        
    print_info("\nChecking schema updates...")
    if not check_schema_updates():
        all_checks_passed = False
        
    print_info("\nChecking admin UI updates...")
    if not check_admin_ui_updates():
        all_checks_passed = False
        
    print_info("\nChecking admin route updates...")
    if not check_admin_route_updates():
        all_checks_passed = False
    
    # Final result
    print("\n")
    if all_checks_passed:
        print_success("All implementation checks passed! The authentication detection has been successfully extended.")
    else:
        print_error("Some implementation checks failed. Please review the issues above.")
    
    return 0 if all_checks_passed else 1

if __name__ == "__main__":
    sys.exit(main()) 
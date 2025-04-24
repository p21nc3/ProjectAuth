#!/bin/bash

# Create directories for new authentication method logos
echo "Setting up logo directories for new authentication methods..."

# Passkey logos
mkdir -p worker/config/idp_patterns/passkey/{16x16,100x100,250x250}
echo "Created passkey logo directories"

# Basic auth (password) logos
mkdir -p worker/config/idp_patterns/basic-auth/{16x16,100x100,250x250}
echo "Created basic-auth logo directories"

# MFA logos
mkdir -p worker/config/idp_patterns/mfa/{16x16,100x100,250x250}
echo "Created MFA logo directories"

echo "Done setting up logo directories"
echo "Please add logo files to these directories" 
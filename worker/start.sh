#!/bin/bash
set -e

# Start Xvfb with more memory and better configuration
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset -nolisten tcp &
export DISPLAY=:99

# Wait for Xvfb to be ready
echo "Waiting for Xvfb to start..."
sleep 5

# Make sure we have a clean DBUS environment
export DBUS_SESSION_BUS_ADDRESS=/dev/null

# Add memory check to avoid segfaults
echo "Configuring browser memory limits..."
# Set Node.js memory limits 
export NODE_OPTIONS="--max-old-space-size=8192"
# Set limit for Python's memory allocator
export PYTHONMALLOC=malloc

# Run the application with a simple process monitoring wrapper
echo "Starting Python application..."
exec python -u app.py 
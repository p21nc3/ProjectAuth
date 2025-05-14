#!/bin/bash
set -e

# Start Xvfb
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset &
export DISPLAY=:99

# Wait for Xvfb to be ready
echo "Waiting for Xvfb to start..."
sleep 3

# Make sure we have a clean DBUS environment
export DBUS_SESSION_BUS_ADDRESS=/dev/null

# Run the application
echo "Starting Python application..."
exec python app.py 

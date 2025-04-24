#!/bin/bash

# Setup script for new authentication methods
echo "Setting up new authentication detection methods..."

# 1. Set up logo directories
echo "Creating logo directories..."
bash setup_new_auth_logos.sh

# 2. Apply database migrations
echo "Applying database migrations..."

# Find MongoDB container name
MONGO_CONTAINER=$(docker ps | grep mongodb | awk '{print $NF}')
if [ -z "$MONGO_CONTAINER" ]; then
    echo "Error: MongoDB container not found"
    echo "Please make sure the Docker containers are running"
    exit 1
fi
echo "Found MongoDB container: $MONGO_CONTAINER"

# Apply migrations
echo "Applying database indexes..."
docker exec -i $MONGO_CONTAINER mongo < db_migrations/add_auth_methods_indexes.js

# 3. Create indexes via API
echo "Creating indexes via API..."
curl -X POST http://localhost:5000/admin/db_index || echo "API not available, skipping"

echo ""
echo "Setup complete!"
echo "New authentication methods are now ready to use."
echo "Please see README_NEW_AUTH.md for detailed information." 
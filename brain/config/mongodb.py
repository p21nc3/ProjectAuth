from flask_pymongo import PyMongo


def config_mongodb(app):
    mongodb_host = app.config["MONGODB_HOST"]
    mongodb_port = app.config["MONGODB_PORT"]
    mongodb_username = app.config["MONGODB_USERNAME"]
    mongodb_password = app.config["MONGODB_PASSWORD"]
    mongodb_database = app.config["MONGODB_DATABASE"]
    mongodb_auth_source = app.config["MONGODB_AUTH_SOURCE"]
    
    # Build the connection string with authentication
    app.config["MONGO_URI"] = f"mongodb://{mongodb_username}:{mongodb_password}@{mongodb_host}:{mongodb_port}/{mongodb_database}?authSource={mongodb_auth_source}"
    
    try:
        mongo = PyMongo(app)
        app.extensions["db"] = mongo.db
        app.config["db"] = mongo.db # deprecated
        app.logger.info(f"Successfully connected to MongoDB at {mongodb_host}:{mongodb_port}")
    except Exception as e:
        app.logger.error(f"Error initializing database: {e}, full error: {str(e)}")
        # Initialize with empty values to allow app to start
        app.extensions["db"] = None
        app.config["db"] = None

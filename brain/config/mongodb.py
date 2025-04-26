from flask_pymongo import PyMongo


def config_mongodb(app):
    mongodb_host = app.config.get('MONGODB_HOST', 'mongodb')
    mongodb_port = app.config.get('MONGODB_PORT', 27017)
    mongodb_username = app.config.get('MONGODB_USERNAME', 'admin')
    mongodb_password = app.config.get('MONGODB_PASSWORD', 'changeme')
    mongodb_database = app.config.get('MONGODB_DATABASE', 'sso-monitor')
    mongodb_auth_source = app.config.get('MONGODB_AUTH_SOURCE', 'admin')
    
    # Construct URI with authentication
    app.config['MONGO_URI'] = f'mongodb://{mongodb_username}:{mongodb_password}@{mongodb_host}:{mongodb_port}/{mongodb_database}?authSource={mongodb_auth_source}'
    mongo = PyMongo(app)
    app.extensions['db'] = mongo.db
    app.config['db'] = mongo.db  # deprecated 

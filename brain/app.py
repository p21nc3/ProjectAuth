from apiflask import APIFlask
from config.env import config_env
from config.logging import config_logging
from config.flask import config_flask
from config.mongodb import config_mongodb
from config.rabbitmq import config_rabbitmq
from config.minio import config_minio
from config.celery import config_celery
from config.cache import config_cache
from blueprints.bp_views import bp_views
from blueprints.bp_api import bp_api


def create_app():
    app = APIFlask(__name__, title="ProjectAuth")

    config_env(app)
    config_logging(app)
    config_flask(app)
    config_mongodb(app)
    config_rabbitmq(app)
    config_minio(app)
    config_celery(app)
    config_cache(app)

    app.register_blueprint(bp_views)
    app.register_blueprint(bp_api)

    # Configure app with initialization
    with app.app_context():
        # Initialize database indexes
        try:
            from blueprints.api.bp_init import initialize_database
            if initialize_database(app.config["db"]):
                app.logger.info("Database initialization completed successfully")
            else:
                app.logger.warning("Database initialization completed with warnings")
        except Exception as e:
            app.logger.error(f"Error during app initialization: {e}")
            # Continue anyway as this shouldn't stop the app from functioning

    return app

# Standard WSGI handler for production deployments
application = create_app()

if __name__ == "__main__":
    application.run()

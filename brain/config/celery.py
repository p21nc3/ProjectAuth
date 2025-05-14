from celery import Celery, Task


def config_celery(app):
    rabbitmq_host = app.config["RABBITMQ_HOST"]
    rabbitmq_port = app.config["RABBITMQ_PORT"]
    admin_user = app.config["ADMIN_USER"]
    admin_pass = app.config["ADMIN_PASS"]
    mongodb_host = app.config["MONGODB_HOST"]
    mongodb_port = app.config["MONGODB_PORT"]
    mongodb_username = app.config["MONGODB_USERNAME"]
    mongodb_password = app.config["MONGODB_PASSWORD"]
    mongodb_auth_source = app.config["MONGODB_AUTH_SOURCE"]

    app.config["CELERY"] = {
        "broker_url": f"amqp://{admin_user}:{admin_pass}@{rabbitmq_host}:{rabbitmq_port}/",
        "result_backend": f"mongodb://{mongodb_username}:{mongodb_password}@{mongodb_host}:{mongodb_port}/celery?authSource={mongodb_auth_source}",
        "mongodb_backend_settings": {
            "database": "celery",
            "taskmeta_collection": "celery_taskmeta_collection"
        },
        "task_ignore_result": True
    }

    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery = Celery(app.name, task_cls=FlaskTask)
    celery.config_from_object(app.config["CELERY"])
    celery.set_default()
    app.extensions["celery"] = celery

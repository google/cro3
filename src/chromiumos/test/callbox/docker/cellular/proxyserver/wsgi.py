import logging

from .flask_app import app

gunicorn_logger = logging.getLogger("gunicorn.error")
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(gunicorn_logger.level)

if gunicorn_logger.level >= logging.DEBUG:
    app.config["DEBUG"] = True

if __name__ == "__main__":
    app.run()

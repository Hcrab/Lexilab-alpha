import os
from flask import Flask, request
from .config import Config
from . import extensions
from .extensions import init_extensions, MongoJSONProvider
from apscheduler.schedulers.background import BackgroundScheduler
from .scheduler import publish_due_quizzes

def create_app(config_class=Config):
    """
    Application factory function.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set in the environment or .env")

    # Initialize extensions
    init_extensions(app)

    # Use custom JSON provider for ObjectId serialization
    app.json = MongoJSONProvider(app)

    # Register Blueprints
    from .blueprints.auth import auth_bp
    app.register_blueprint(auth_bp)

    from .blueprints.users import users_bp
    app.register_blueprint(users_bp)

    from .blueprints.word_pools import pools_bp
    app.register_blueprint(pools_bp)

    from .blueprints.words import words_bp
    app.register_blueprint(words_bp)

    from .blueprints.quizzes import quizzes_bp
    app.register_blueprint(quizzes_bp)

    from .blueprints.results import results_bp
    app.register_blueprint(results_bp)

    from .blueprints.bookmarks import bm_bp
    app.register_blueprint(bm_bp)

    from .blueprints.stats import stats_bp
    app.register_blueprint(stats_bp)

    from .blueprints.ai import ai_bp
    app.register_blueprint(ai_bp)

    from .blueprints.progress import progress_bp
    app.register_blueprint(progress_bp)

    # Request logging and path fixing
    @app.before_request
    def before_request_logging():
        # This function will now handle both logging and path fixing.
        path = request.path
        if path.startswith('/api/api/'):
            new_path = path[len('/api'):]
            request.path_info_cache = None  # Clear cache
            request.path = new_path
            extensions.logger.warning(f"Internally rewriting incorrect path {path} to {new_path}")

        # General request log
        extensions.logger.info(f"Request: {request.method} {request.path}")

    # Initialize and start the scheduler
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(publish_due_quizzes, 'interval', minutes=1, args=[app])
    scheduler.start()

    # It's good practice to shut down the scheduler when the app exits
    import atexit
    atexit.register(lambda: scheduler.shutdown())

    return app

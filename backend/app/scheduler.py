from datetime import datetime, timezone
from flask import current_app

def publish_due_quizzes(app):
    """
    Finds quizzes that are scheduled to be published and updates their status.
    This function is meant to be run periodically by a scheduler.
    It requires the app context to access extensions.
    """
    with app.app_context():
        # Now we can safely access extensions
        from .extensions import quizzes_collection, logger

        try:
            now_utc = datetime.now(timezone.utc)

            # Query for quizzes that are due
            due_quizzes_cursor = quizzes_collection.find({
                "status": "to be published",
                "publish_at": {"$lte": now_utc}
            })

            due_quiz_ids = [q["_id"] for q in due_quizzes_cursor]

            if not due_quiz_ids:
                # No quizzes to publish, this is a normal case.
                # logger.info("Scheduler run: No quizzes were due for publishing.")
                return

            # Update the status of due quizzes
            result = quizzes_collection.update_many(
                {"_id": {"$in": due_quiz_ids}},
                {"$set": {"status": "published"}}
            )

            logger.info(f"Scheduler run: Published {result.modified_count} quizzes.")

        except Exception as e:
            logger.error(f"Scheduler error during quiz publishing: {e}", exc_info=True)
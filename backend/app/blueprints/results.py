from flask import request, jsonify, Blueprint
from bson import ObjectId
from pymongo.errors import PyMongoError
from ..extensions import results_collection, quizzes_collection, logger
from werkzeug.exceptions import BadRequest
from ..config import BEIJING_TZ
from .ai import check_for_prompt_injection, grade_fill_in_the_blank_with_explanation
from .auth import auth_required
from datetime import datetime, timezone

results_bp = Blueprint('results', __name__, url_prefix='/results')

@results_bp.route("", methods=['POST'])
@auth_required
def create_result(current_user):
    try:
        data = request.get_json(force=True)
    except BadRequest:
        return jsonify(error="invalid JSON"), 400

    username = data.get("username")
    if username != current_user["username"]:
        return jsonify(error="Cannot submit another user's result"), 403
    quiz_id = data.get("quiz_id")
    details = data.get("details")
    time_spent = data.get("time_spent", 0)

    if not (username and quiz_id and details and "questions" in details):
        return jsonify(error="missing required fields"), 400

    try:
        quiz_obj_id = ObjectId(quiz_id)
    except Exception:
        return jsonify(error="invalid quiz_id"), 400

    quiz = quizzes_collection.find_one({"_id": quiz_obj_id})
    if not quiz:
        return jsonify(error="quiz not found"), 404

    quiz_questions_map = {
        str(q["id"]): q for q in quiz.get("data", {}).get("items", []) if "id" in q
    }
    # Create a secondary map based on the word for lookup if ID is missing
    quiz_questions_by_word_map = {
        q["word"]: q for q in quiz.get("data", {}).get("items", []) if "word" in q
    }

    final_score = 0
    total_possible = 0
    FILL_BLANK_POINTS = 2
    SENTENCE_POINTS = 4

    processed_questions = []

    for submitted_q in details.get("questions", []):
        q_id = str(submitted_q.get("id")) if "id" in submitted_q else None
        db_question = quiz_questions_map.get(q_id)

        # If not found by ID, try to find by word (for legacy or malformed data)
        if not db_question and "word" in submitted_q:
            db_question = quiz_questions_by_word_map.get(submitted_q["word"])

        if not db_question:
            logger.warning("Submitted question could not be matched to a DB question")
            continue

        processed_q = submitted_q.copy()
        # Ensure the word from the database is always included in the final result
        processed_q["word"] = db_question.get("word")

        # Logic for fill-in-the-blank questions
        if submitted_q.get("type") == "fill-in-the-blank":
            total_possible += FILL_BLANK_POINTS
            # Trust the 'correct' field from the frontend payload
            if submitted_q.get("correct"):
                final_score += FILL_BLANK_POINTS
            # Ensure correctAnswer is populated from the database for consistency
            processed_q["correctAnswer"] = db_question.get("answer", "")

        # Logic for sentence-building questions
        elif "score" in submitted_q:
            total_possible += SENTENCE_POINTS
            final_score += submitted_q.get("score", 0)

        else:
            logger.warning("Question with unknown format found in submission")
            continue

        processed_questions.append(processed_q)

    passed = (final_score / total_possible) >= 0.6 if total_possible > 0 else False

    # Replace original details with processed ones
    details["questions"] = processed_questions

    result_doc = {
        "username": username,
        "quiz_id": quiz_obj_id,
        "correct": final_score,
        "total": total_possible,
        "passed": passed,
        "time_spent": time_spent,
        "details": details,
        "ts": datetime.now(timezone.utc)
    }

    try:
        result = results_collection.insert_one(result_doc)
        new_result_doc = {
            "id": str(result.inserted_id),
            "username": username,
            "quiz_id": str(quiz_obj_id),
            "correct": final_score,
            "total": total_possible,
            "passed": passed,
            "time_spent": time_spent,
            "details": details,
            "ts": result_doc["ts"].isoformat()
        }
        return jsonify(new_result_doc), 201
    except PyMongoError as e:
        logger.error(f"Error inserting result: {e}")
        return jsonify(error="database error"), 500

@results_bp.route("", methods=['GET'])
@auth_required
def list_results(current_user):
    username = request.args.get("username")
    quiz_id = request.args.get("quiz_id")
    logger.info(f"list_results called with username: {username}, quiz_id: {quiz_id}")

    if not username:
        return jsonify(error="username required"), 400
    if username != current_user["username"] and current_user.get("role") != "admin":
        return jsonify(error="Forbidden"), 403

    match_stage = {"username": username}
    if quiz_id:
        try:
            match_stage["quiz_id"] = ObjectId(quiz_id)
        except Exception as e:
            logger.error(f"Invalid quiz_id '{quiz_id}': {e}")
            return jsonify(error="invalid quiz_id"), 400

    logger.info(f"Executing aggregation with match_stage: {match_stage}")

    pipeline = [
        {"$match": match_stage},
        {"$sort": {"ts": -1}},
        {"$lookup": {
            "from": "quizzes",
            "localField": "quiz_id",
            "foreignField": "_id",
            "as": "quiz_info"
        }},
        {"$unwind": {"path": "$quiz_info", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "id": {"$toString": "$_id"},
            "quiz_id": {"$toString": "$quiz_id"},
            "quiz_name": {"$ifNull": ["$quiz_info.name", "Deleted Quiz"]},
            "score": "$correct",
            "total_score": "$total",
            "passed": 1,
            "ts": 1,
            "_id": 0
        }}
    ]
    try:
        results = list(results_collection.aggregate(pipeline))
        logger.info(f"Aggregation returned {len(results)} results.")
        return jsonify(results)
    except Exception as e:
        logger.error(f"Aggregation pipeline failed: {e}")
        return jsonify(error="database aggregation failed"), 500

@results_bp.route("/<result_id>", methods=['GET'])
@auth_required
def get_result(current_user, result_id):
    logger.info(f"Received request for result_id: {result_id}")
    try:
        obj_id = ObjectId(result_id)
    except Exception as e:
        logger.error(f"Invalid result_id '{result_id}': {e}")
        return jsonify(error="invalid result_id"), 400

    try:
        result = results_collection.find_one({"_id": obj_id})
        if not result:
            logger.warning(f"Result with id '{result_id}' not found.")
            return jsonify(error="not found"), 404
        if result.get("username") != current_user["username"] and current_user.get("role") != "admin":
            return jsonify(error="Forbidden"), 403

        result['id'] = str(result.pop('_id'))
        result['score'] = result.pop('correct', 0)
        result['total_score'] = result.pop('total', 0)
        if 'quiz_id' in result:
            result['quiz_id'] = str(result['quiz_id'])

        logger.info(f"Successfully found result with id '{result_id}'.")
        return jsonify(result)
    except PyMongoError as e:
        logger.error(f"Database error fetching result '{result_id}': {e}")
        return jsonify(error="database error"), 500

@results_bp.route("/quizzes/<quiz_id>", methods=['GET'])
@auth_required
def get_results_by_quiz(current_user, quiz_id):
    username = request.args.get("username")
    logger.info(f"--- ENTERING get_results_by_quiz ---")
    logger.info(f"Raw quiz_id: {quiz_id}, Raw username: {username}")

    if not username:
        logger.warning("Username is missing")
        return jsonify(error="username required"), 400
    if username != current_user["username"] and current_user.get("role") != "admin":
        return jsonify(error="Forbidden"), 403

    try:
        quiz_obj_id = ObjectId(quiz_id)
    except Exception as e:
        logger.error(f"Invalid quiz_id '{quiz_id}': {e}")
        return jsonify(error="invalid quiz_id"), 400

    pipeline = [
        {"$match": {
            "username": username,
            "quiz_id": quiz_obj_id
        }},
        {"$sort": {"ts": -1}},
        {"$lookup": {
            "from": "quizzes",
            "localField": "quiz_id",
            "foreignField": "_id",
            "as": "quiz_info"
        }},
        {"$unwind": {"path": "$quiz_info", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "id": {"$toString": "$_id"},
            "quiz_id": {"$toString": "$quiz_id"},
            "quiz_name": {"$ifNull": ["$quiz_info.name", "Deleted Quiz"]},
            "score": "$correct",
            "total_score": "$total",
            "passed": 1,
            "ts": 1,
            "_id": 0
        }}
    ]

    try:
        results = list(results_collection.aggregate(pipeline))
        return jsonify(results)
    except Exception as e:
        logger.error(f"Aggregation pipeline failed in get_results_by_quiz: {e}", exc_info=True)
        return jsonify(error="database aggregation failed"), 500

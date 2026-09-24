import json
from flask import request, jsonify, Blueprint, g
from bson import ObjectId
from ..extensions import bookmarks_collection, quizzes_collection, logger
from ..config import beijing_now
from .auth import get_user_or_none

bm_bp = Blueprint('bookmarks', __name__, url_prefix='/bookmarks')


@bm_bp.before_request
def require_bookmark_owner():
    user = get_user_or_none()
    if user is None:
        return jsonify(error="Authentication required"), 401
    g.current_user = user


def owns_username(username):
    return username == g.current_user["username"]

@bm_bp.route("/list", methods=['POST'])
def list_bookmarks_post():
    logger.info(f"--- ENTERING /bookmarks/list (POST) ---")
    try:
        data = request.get_json(force=True)
        username = data.get("username")
        bookmark_type = data.get("type")
        logger.info(f"Received POST data: username='{username}', type='{bookmark_type}'")

        if not (username and bookmark_type):
            return jsonify(error="username and type are required"), 400
        if not owns_username(username):
            return jsonify(error="Forbidden"), 403
        if bookmark_type not in ['error_question', 'vocabulary_word']:
            return jsonify(error="invalid type specified"), 400

        match_query = {"username": username, "type": bookmark_type}

        pipeline = [
            {"$match": match_query},
            {"$sort": {"created_at": -1}}
        ]

        if bookmark_type == 'error_question':
            pipeline.extend([
                {"$lookup": {
                    "from": "quizzes",
                    "localField": "quiz_id",
                    "foreignField": "_id",
                    "as": "quiz_info"
                }},
                {"$unwind": {"path": "$quiz_info", "preserveNullAndEmptyArrays": True}},
                {"$project": {
                    "_id": 1, "type": 1, "quiz_id": 1, "result_id": 1,
                    "question_index": 1, "user_answer": 1, "word": 1,
                    "created_at": 1, "quiz_name": {"$ifNull": ["$quiz_info.name", "Deleted Quiz"]},
                    "question_prompt": 1, "correct_answer": 1, "ai_feedback": 1,
                }}
            ])

        bookmarks = list(bookmarks_collection.aggregate(pipeline))
        return jsonify(bookmarks)
    except Exception as e:
        logger.error(f"--- UNCAUGHT EXCEPTION IN /bookmarks/list: {e} ---", exc_info=True)
        return jsonify(error="An unexpected error occurred in the server."), 500

@bm_bp.route("", methods=['GET'])
def list_bookmarks():
    try:
        username = request.args.get("username")
        bookmark_type = request.args.get("type")
        result_id = request.args.get("result_id")

        if not (username and bookmark_type):
            return jsonify(error="username and type are required"), 400
        if not owns_username(username):
            return jsonify(error="Forbidden"), 403
        if bookmark_type not in ['error_question', 'vocabulary_word']:
            return jsonify(error="invalid type specified"), 400

        match_query = {"username": username, "type": bookmark_type}

        if result_id:
            try:
                match_query["result_id"] = ObjectId(result_id)
            except Exception as e:
                logger.error(f"Failed to convert result_id '{result_id}' to ObjectId. Error: {e}", exc_info=True)
                return jsonify(error=f"invalid result_id format: {result_id}"), 400

        pipeline = [
            {"$match": match_query},
            {"$sort": {"created_at": -1}}
        ]

        if bookmark_type == 'error_question':
            pipeline.extend([
                {"$lookup": {
                    "from": "quizzes",
                    "localField": "quiz_id",
                    "foreignField": "_id",
                    "as": "quiz_info"
                }},
                {"$unwind": {"path": "$quiz_info", "preserveNullAndEmptyArrays": True}},
                {"$project": {
                    "_id": 1, "type": 1, "quiz_id": 1, "result_id": 1,
                    "question_index": 1, "user_answer": 1, "word": 1,
                    "created_at": 1, "quiz_name": {"$ifNull": ["$quiz_info.name", "Deleted Quiz"]}
                }}
            ])

        bookmarks = list(bookmarks_collection.aggregate(pipeline))
        return jsonify(bookmarks)
    except Exception as e:
        logger.error(f"--- UNCAUGHT EXCEPTION IN /bookmarks: {e} ---", exc_info=True)
        return jsonify(error="An unexpected error occurred in the server."), 500

@bm_bp.route("", methods=['POST'])
def add_bookmark():
    data = request.get_json(force=True)
    username = data.get("username")
    bookmark_type = data.get("type")
    if not (username and bookmark_type):
        return jsonify(error="missing username or type"), 400
    if not owns_username(username):
        return jsonify(error="Forbidden"), 403

    doc = {"username": username, "type": bookmark_type, "created_at": beijing_now()}

    if bookmark_type == 'error_question':
        required = ['quiz_id', 'result_id', 'question_index', 'user_answer', 'word']
        if not all(f in data for f in required):
            return jsonify(error="missing fields for error_question"), 400
        try:
            doc.update({
                "quiz_id": ObjectId(data['quiz_id']),
                "result_id": ObjectId(data['result_id']),
                "question_index": data['question_index'],
                "user_answer": data['user_answer'],
                "word": data['word'],
                "question_prompt": data.get("question_prompt"),
                "correct_answer": data.get("correct_answer"),
                "ai_feedback": data.get("ai_feedback"),
            })
        except Exception:
            return jsonify(error="invalid quiz_id or result_id"), 400

        query_filter = {
            "username": username,
            "type": "error_question",
            "result_id": doc["result_id"],
            "question_index": doc["question_index"]
        }
        update_result = bookmarks_collection.update_one(query_filter, {"$setOnInsert": doc}, upsert=True)

        if update_result.upserted_id:
            new_bookmark = bookmarks_collection.find_one({"_id": update_result.upserted_id})
            return jsonify(new_bookmark), 201
        else:
            return jsonify(message="Question already bookmarked"), 200

    elif bookmark_type == 'vocabulary_word':
        required = ['word', 'definition']
        if not all(f in data for f in required):
            return jsonify(error="missing fields for vocabulary_word"), 400

        word_to_add = data['word']

        query_filter = {"username": username, "type": "vocabulary_word", "word": word_to_add}
        existing = bookmarks_collection.find_one(query_filter)

        if existing:
            return jsonify(error=f"'{word_to_add}' already exists in your vocabulary."), 409

        doc.update({"word": word_to_add, "definition": data['definition']})
        result = bookmarks_collection.insert_one(doc)
        new_bookmark = bookmarks_collection.find_one({"_id": result.inserted_id})
        return jsonify(new_bookmark), 201

    else:
        return jsonify(error="invalid bookmark type"), 400

@bm_bp.route("/<bookmark_id>", methods=['DELETE'])
def delete_bookmark(bookmark_id):
    try:
        obj_id = ObjectId(bookmark_id)
    except Exception:
        return jsonify(error="invalid bookmark_id"), 400

    result = bookmarks_collection.delete_one({"_id": obj_id, "username": g.current_user["username"]})
    if result.deleted_count == 0:
        return jsonify(error="not found"), 404
    return jsonify(ok=True)

@bm_bp.route("/vocabulary/deduplicate", methods=['POST'])
def deduplicate_vocabulary():
    data = request.get_json(force=True)
    username = data.get("username")
    if not username:
        return jsonify(error="username is required"), 400
    if not owns_username(username):
        return jsonify(error="Forbidden"), 403

    logger.info(f"--- Starting vocabulary deduplication for user: {username} ---")

    try:
        pipeline = [
            {"$match": {"username": username, "type": "vocabulary_word"}},
            {"$group": {
                "_id": {"word": "$word", "definition": "$definition"},
                "ids": {"$push": "$_id"},
                "count": {"$sum": 1}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]

        duplicates = list(bookmarks_collection.aggregate(pipeline))
        ids_to_delete = []
        for group in duplicates:
            ids_to_delete.extend(group['ids'][1:])

        if not ids_to_delete:
            return jsonify(deleted_count=0)

        result = bookmarks_collection.delete_many({"_id": {"$in": ids_to_delete}})
        deleted_count = result.deleted_count
        logger.info(f"Successfully deleted {deleted_count} duplicate entries for user: {username}")

        return jsonify(deleted_count=deleted_count)

    except Exception as e:
        logger.error(f"--- Error during vocabulary deduplication for user {username}: {e} ---", exc_info=True)
        return jsonify(error="An unexpected error occurred during deduplication."), 500

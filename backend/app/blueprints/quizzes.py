import random
from flask import request, jsonify, Blueprint
from bson import ObjectId
from datetime import date, timedelta, datetime, timezone
import uuid
from ..extensions import quizzes_collection, results_collection, bookmarks_collection, words_in_pools_collection, logger
from ..config import beijing_now
from .auth import admin_required, get_user_or_none

quizzes_bp = Blueprint('quizzes', __name__, url_prefix='/quizzes')

@quizzes_bp.route("/saturday-special", methods=['POST'])
@admin_required
def create_saturday_special(current_user):
    data = request.get_json(force=True)
    blank_count = data.get('blank_count', 0)
    sentence_count = data.get('sentence_count', 0)
    source_start_date_str = data.get('source_start_date')
    source_end_date_str = data.get('source_end_date')

    if not (isinstance(blank_count, int) and blank_count >= 0 and
            isinstance(sentence_count, int) and sentence_count >= 0):
        return jsonify(error="Invalid count provided"), 400

    if blank_count == 0 and sentence_count == 0:
        return jsonify(error="At least one question must be requested"), 400

    # --- Date Filtering Logic ---
    date_filter = {}
    if source_start_date_str and source_end_date_str:
        try:
            start_date = datetime.strptime(source_start_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            end_date = datetime.strptime(source_end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
            date_range_query = {"$gte": start_date, "$lte": end_date}
            date_filter = {
                "$or": [
                    {"publish_at": date_range_query},
                    {"$and": [
                        {"publish_at": {"$exists": False}},
                        {"created_at": date_range_query}
                    ]}
                ]
            }
            logger.info(f"Using provided date range for Saturday Special: {start_date} to {end_date}")
        except ValueError:
            return jsonify(error="Invalid date format. Use YYYY-MM-DD."), 400
    else:
        five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
        date_range_query = {"$gte": five_days_ago}
        date_filter = {
            "$or": [
                {"publish_at": date_range_query},
                {"$and": [
                    {"publish_at": {"$exists": False}},
                    {"created_at": date_range_query}
                ]}
            ]
        }
        logger.info(f"Using default last 5 days for Saturday Special, starting from {five_days_ago}")

    # --- New Word-Unique Selection Logic ---
    try:
        # 1. Fetch all possible candidates
        pipeline = [
            {"$match": {"$and": [date_filter, {"type": "weekday"}]}},
            {"$unwind": "$data.items"},
            {"$match": {"data.items.type": {"$in": ["fill-in-the-blank", "sentence"]}}},
            {"$replaceRoot": {"newRoot": "$data.items"}}
        ]
        all_candidates = list(quizzes_collection.aggregate(pipeline))

        # 2. Shuffle and select to ensure word uniqueness
        random.shuffle(all_candidates)

        used_words = set()
        final_items = []

        blanks_needed = blank_count
        sentences_needed = sentence_count

        # Iterate through shuffled candidates to pick questions
        for item in all_candidates:
            word = item.get("word")
            item_type = item.get("type")

            if not word or word in used_words:
                continue

            if item_type == "fill-in-the-blank" and blanks_needed > 0:
                final_items.append(item)
                used_words.add(word)
                blanks_needed -= 1
            elif item_type == "sentence" and sentences_needed > 0:
                final_items.append(item)
                used_words.add(word)
                sentences_needed -= 1

        # 3. Ensure new unique IDs for the new quiz
        for item in final_items:
            item['id'] = str(uuid.uuid4())

        return jsonify(final_items)

    except Exception as e:
        logger.error(f"Error during Saturday Special aggregation: {e}", exc_info=True)
        return jsonify(error="Could not generate Saturday Special quiz"), 500


@quizzes_bp.route("", methods=['POST'])
@admin_required
def create_quiz(current_user):
    data = request.get_json(force=True)
    name = data.get("name")
    qtype = data.get("type")
    qdata = data.get("data")
    pool_id = data.get("pool_id")
    status = data.get("status", "draft") # New field, default to 'draft'
    publish_at_str = data.get("publish_at") # New field

    if not (name and qtype and qdata is not None):
        return jsonify(error="missing fields"), 400

    if 'items' in qdata and isinstance(qdata['items'], list):
        for item in qdata['items']:
            if 'id' not in item or not item['id']:
                item['id'] = str(uuid.uuid4())

    publish_at = None
    if publish_at_str:
        try:
            # Expecting ISO 8601 format from frontend e.g. "2024-07-25T10:00:00.000Z"
            publish_at = datetime.fromisoformat(publish_at_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify(error="Invalid publish_at format. Use ISO 8601."), 400

    # Determine the correct status based on publish_at
    final_status = status
    if status == 'published':
        if publish_at and publish_at > datetime.now(timezone.utc):
            final_status = 'to be published'

    quiz_doc = {
        "name": name,
        "type": qtype,
        "data": qdata,
        "status": final_status,
        "created_at": datetime.now(timezone.utc),
        "publish_at": publish_at
    }

    if pool_id:
        try:
            quiz_doc["word_pool_id"] = ObjectId(pool_id)
        except Exception:
            return jsonify(error="Invalid pool_id format in quiz creation"), 400

    result = quizzes_collection.insert_one(quiz_doc)
    new_quiz = quizzes_collection.find_one({"_id": result.inserted_id})

    if qtype == 'weekday' and pool_id:
        try:
            pool_obj_id = ObjectId(pool_id)
            words_in_quiz = [item['word'] for item in qdata.get('items', []) if 'word' in item]

            if words_in_quiz:
                words_in_pools_collection.update_many(
                    {"word_pool_id": pool_obj_id, "word": {"$in": words_in_quiz}},
                    {"$set": {"status": "used", "last_status_change": datetime.now(timezone.utc)}}
                )
                logger.info(f"Updated {len(words_in_quiz)} words to 'used' in pool {pool_id} after quiz creation.")
        except Exception as e:
            logger.error(f"Error updating word status after quiz creation: {e}", exc_info=True)

    return jsonify(new_quiz), 201

@quizzes_bp.route("", methods=['GET'])
def list_quizzes():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10)) # Default to 10 quizzes per page
    except (ValueError, TypeError):
        page = 1
        per_page = 10

    user = get_user_or_none()
    query = {}
    # If user is not admin, only show published quizzes that are ready
    if not user or user.get('role') != 'admin':
        query = {
            "$and": [
                {
                    "$or": [
                        {"status": "published"},
                        {"status": {"$exists": False}}
                    ]
                },
                {
                    "$or": [
                        {"publish_at": None},
                        {"publish_at": {"$lte": datetime.now(timezone.utc)}}
                    ]
                }
            ]
        }

    try:
        total_quizzes = quizzes_collection.count_documents(query)
        total_pages = (total_quizzes + per_page - 1) // per_page

        skips = per_page * (page - 1)

        quizzes_cursor = quizzes_collection.find(query).sort("created_at", -1).skip(skips).limit(per_page)
        quizzes = list(quizzes_cursor)

        return jsonify({
            "quizzes": quizzes,
            "total_pages": total_pages,
            "current_page": page
        })
    except Exception as e:
        logger.error(f"Error during quiz listing and pagination: {e}", exc_info=True)
        return jsonify(error="Database query failed"), 500

@quizzes_bp.route("/<quiz_id>", methods=['GET'])
def get_quiz(quiz_id):
    try:
        obj_id = ObjectId(quiz_id)
    except Exception as e:
        logger.error(f"Invalid quiz_id received: '{quiz_id}' - Error: {e}")
        return jsonify(error="invalid quiz_id"), 400

    quiz = quizzes_collection.find_one({"_id": obj_id})
    if not quiz:
        return jsonify(error="not found"), 404

    # Allow admins to see any quiz, but users only see published ones
    user = get_user_or_none()
    is_admin = user and user.get('role') == 'admin'
    is_published = quiz.get('status') == 'published'
    is_ready = quiz.get('publish_at') is None or quiz.get('publish_at') <= datetime.now(timezone.utc)
    if not is_admin and not (is_published and is_ready):
       return jsonify(error="not found"), 404

    if 'data' in quiz and 'items' in quiz['data'] and isinstance(quiz['data']['items'], list):
        needs_update = False
        for item in quiz['data']['items']:
            if 'id' not in item:
                item['id'] = str(uuid.uuid4())
                needs_update = True
        if needs_update:
            quizzes_collection.update_one({'_id': obj_id}, {'$set': {'data.items': quiz['data']['items']}})
    return jsonify(quiz)

@quizzes_bp.route("/<quiz_id>", methods=['PUT'])
@admin_required
def update_quiz(current_user, quiz_id):
    try:
        obj_id = ObjectId(quiz_id)
    except Exception:
        return jsonify(error="invalid quiz_id"), 400

    data = request.get_json(force=True)
    update_data = {}
    if "name" in data: update_data["name"] = data["name"]
    if "type" in data: update_data["type"] = data["type"]
    if "data" in data: update_data["data"] = data["data"]
    if "publish_at" in data:
        publish_at_str = data["publish_at"]
        if publish_at_str:
            try:
                update_data["publish_at"] = datetime.fromisoformat(publish_at_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                return jsonify(error="Invalid publish_at format. Use ISO 8601."), 400
        else:
            update_data["publish_at"] = None

    # Determine the correct status based on the incoming status and publish_at
    if 'status' in data:
        final_status = data['status']
        if final_status == 'published':
            # Use get to check for publish_at in update_data, as it might not have been in the original request
            publish_at_val = update_data.get('publish_at')
            if publish_at_val and publish_at_val > datetime.now(timezone.utc):
                final_status = 'to be published'
        update_data['status'] = final_status


    if not update_data:
        return jsonify(error="no fields to update"), 400

    result = quizzes_collection.update_one({"_id": obj_id}, {"$set": update_data})
    if result.matched_count == 0:
        return jsonify(error="not found"), 404
    return jsonify(ok=True)

@quizzes_bp.route("/<quiz_id>", methods=['DELETE'])
@admin_required
def delete_quiz(current_user, quiz_id):
    try:
        obj_id = ObjectId(quiz_id)
    except Exception:
        return jsonify(error="invalid quiz_id"), 400

    quiz_deletion_result = quizzes_collection.delete_one({"_id": obj_id})

    if quiz_deletion_result.deleted_count == 0:
        return jsonify(error="not found"), 404

    try:
        results_deletion_result = results_collection.delete_many({"quiz_id": obj_id})
        logger.info(f"Deleted {results_deletion_result.deleted_count} results for quiz {quiz_id}")

        bookmarks_deletion_result = bookmarks_collection.delete_many({"quiz_id": obj_id})
        logger.info(f"Deleted {bookmarks_deletion_result.deleted_count} bookmarks for quiz {quiz_id}")

    except PyMongoError as e:
        logger.error(f"Error during cleanup for quiz {quiz_id}: {e}", exc_info=True)

    return jsonify(ok=True)

@quizzes_bp.route("/latest", methods=['GET'])
def latest_quiz():
    query = {
        "status": "published",
        "$or": [
            {"publish_at": None},
            {"publish_at": {"$lte": datetime.now(timezone.utc)}}
        ]
    }
    latest = quizzes_collection.find_one(query, sort=[("created_at", -1)])
    if not latest:
        return jsonify(error="not found"), 404
    return jsonify(latest)

@quizzes_bp.route("/today", methods=['GET'])
def today_quiz():
    query = {
        "status": "published",
        "$or": [
            {"publish_at": None},
            {"publish_at": {"$lte": datetime.now(timezone.utc)}}
        ]
    }
    latest_quiz = quizzes_collection.find_one(query, sort=[("created_at", -1)])
    if not latest_quiz:
        return jsonify(error="not found"), 404
    return jsonify(latest_quiz)

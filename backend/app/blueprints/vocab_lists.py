import logging
from bson import ObjectId
from flask import Blueprint, request, jsonify
from pymongo.errors import PyMongoError

# Note: The actual collection object is injected from extensions.py
# This is just a placeholder for clarity.
vocab_lists_collection = None

vocab_lists_bp = Blueprint('vocab_lists_bp', __name__)

def set_vocab_lists_collection(collection):
    """Injects the vocab_lists collection from extensions.py."""
    global vocab_lists_collection
    vocab_lists_collection = collection

@vocab_lists_bp.route('', methods=['GET'])
def get_vocab_lists():
    """Fetches all vocabulary lists."""
    try:
        lists = list(vocab_lists_collection.find({}).sort("createdAt", -1))
        return jsonify(lists), 200
    except PyMongoError as e:
        logging.error(f"Error fetching vocab lists: {e}")
        return jsonify({"error": "Database error"}), 500

@vocab_lists_bp.route('', methods=['POST'])
def save_vocab_list():
    """Saves a new vocabulary list."""
    data = request.get_json()
    if not data or 'name' not in data or 'items' not in data:
        return jsonify({"error": "Missing name or items in request body"}), 400

    try:
        new_list = {
            "name": data['name'],
            "items": data['items'],
            "createdAt": datetime.utcnow()
        }
        result = vocab_lists_collection.insert_one(new_list)
        new_list['_id'] = result.inserted_id
        return jsonify(new_list), 201
    except PyMongoError as e:
        logging.error(f"Error saving vocab list: {e}")
        return jsonify({"error": "Database error"}), 500

@vocab_lists_bp.route('/<list_id>', methods=['DELETE'])
def delete_vocab_list(list_id):
    """Deletes a vocabulary list by its ID."""
    try:
        result = vocab_lists_collection.delete_one({'_id': ObjectId(list_id)})
        if result.deleted_count == 0:
            return jsonify({"error": "List not found"}), 404
        return jsonify({"message": "List deleted successfully"}), 200
    except PyMongoError as e:
        logging.error(f"Error deleting vocab list: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        logging.error(f"Error processing delete request for list_id {list_id}: {e}")
        return jsonify({"error": "Invalid list ID format"}), 400

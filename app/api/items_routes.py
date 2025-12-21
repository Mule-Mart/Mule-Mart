"""
Items API endpoints
REST endpoints for browsing, creating, updating, and managing items
"""

from flask import request, current_app, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os

from app.models import Item, db, RecentlyViewed, User
from app.search_utils import generate_embedding
from .responses import (
    success_response, error_response, validate_json, require_api_auth,
    serialize_item
)


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file):
    """Save uploaded file and return relative path."""
    if not file or not file.filename:
        return None
    
    if not allowed_file(file.filename):
        return None
    
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{filename}"
    
    upload_folder = os.path.join(current_app.static_folder, 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)
    
    return f"uploads/{filename}"


def register_routes(api):
    """Register items routes to the API blueprint."""
    
    @api.route('/items', methods=['GET'])
    def list_items():
        """
        List all active items with filtering and sorting.
        
        GET /api/v1/items?search=&category=&seller_type=&condition=&sort_by=newest&page=1&per_page=20
        
        Query parameters:
        - search: Search term for title/description
        - category: Filter by category
        - seller_type: Filter by seller type
        - condition: Filter by condition
        - sort_by: newest, oldest, price_low, price_high (default: newest)
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20)
        
        Responses:
        - 200: List of items with pagination
        """
        # Get query parameters
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()
        seller_type = request.args.get('seller_type', '').strip()
        condition = request.args.get('condition', '').strip()
        sort_by = request.args.get('sort_by', 'newest')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Validate pagination
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 20
        
        # Build query
        query = Item.query.filter_by(is_active=True)
        
        # Apply search filter
        if search:
            semantic_results = Item.semantic_search(search, limit=100)
            if semantic_results:
                relevant_ids = [item.id for item in semantic_results]
                query = query.filter(Item.id.in_(relevant_ids))
            else:
                query = query.filter(db.false())
        
        # Apply category filter
        if category:
            query = query.filter_by(category=category)
        
        # Apply seller type filter
        if seller_type:
            query = query.filter_by(seller_type=seller_type)
        
        # Apply condition filter
        if condition:
            query = query.filter_by(condition=condition)
        
        # Apply sorting
        if sort_by == 'oldest':
            query = query.order_by(Item.created_at.asc())
        elif sort_by == 'price_low':
            query = query.order_by(Item.price.asc())
        elif sort_by == 'price_high':
            query = query.order_by(Item.price.desc())
        else:  # newest (default)
            query = query.order_by(Item.created_at.desc())
        
        # Get total count before pagination
        total = query.count()
        
        # Apply pagination
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Serialize items
        items_data = [serialize_item(item) for item in items]
        
        return success_response(
            data={
                'items': items_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                },
                'filters': {
                    'search': search,
                    'category': category,
                    'seller_type': seller_type,
                    'condition': condition,
                    'sort_by': sort_by
                }
            },
            message='Items retrieved successfully'
        )
    
    
    @api.route('/items/<int:item_id>', methods=['GET'])
    def get_item(item_id):
        """
        Get a specific item by ID.
        
        GET /api/v1/items/<item_id>
        
        Responses:
        - 200: Item details
        - 404: Item not found
        """
        item = Item.query.get(item_id)
        
        if not item or not item.is_active:
            return error_response(
                message='Item not found',
                status_code=404
            )
        
        # Track recently viewed (if authenticated)
        if current_user.is_authenticated:
            existing_view = RecentlyViewed.query.filter_by(
                user_id=current_user.id,
                item_id=item.id
            ).first()
            
            if existing_view:
                existing_view.viewed_at = datetime.utcnow()
            else:
                new_view = RecentlyViewed(user_id=current_user.id, item_id=item.id)
                db.session.add(new_view)
            
            db.session.commit()
        
        return success_response(
            data=serialize_item(item),
            message='Item retrieved successfully'
        )
    
    
    @api.route('/items', methods=['POST'])
    @require_api_auth
    @validate_json('title', 'price')
    def create_item():
        """
        Create a new item listing.
        
        POST /api/v1/items
        
        Request body (JSON or form data):
        {
            "title": "Vintage Jacket",
            "description": "Beautiful vintage jacket...",
            "category": "clothing",
            "size": "M",
            "seller_type": "individual",
            "condition": "good",
            "price": 25.99
        }
        
        Files:
        - image: Item image file (multipart/form-data)
        
        Responses:
        - 201: Item created successfully
        - 400: Validation error
        - 401: Not authenticated
        """
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            title = data.get('title', '').strip()
            description = data.get('description', '').strip()
            category = data.get('category', '').strip()
            size = data.get('size', '').strip()
            seller_type = data.get('seller_type', '').strip()
            condition = data.get('condition', '').strip()
            price_str = data.get('price', '')
        else:
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            category = request.form.get('category', '').strip()
            size = request.form.get('size', '').strip()
            seller_type = request.form.get('seller_type', '').strip()
            condition = request.form.get('condition', '').strip()
            price_str = request.form.get('price', '')
        
        # Validation
        errors = {}
        
        if not title:
            errors['title'] = 'Item title is required'
        elif len(title) > 150:
            errors['title'] = 'Title must be 150 characters or less'
        
        if price_str:
            try:
                price_clean = price_str.replace('$', '').replace(',', '').strip()
                price = float(price_clean)
                if price < 0:
                    raise ValueError()
            except (ValueError, AttributeError):
                errors['price'] = 'Price must be a valid positive number'
        else:
            errors['price'] = 'Price is required'
        
        if errors:
            return error_response(
                message='Validation failed',
                status_code=400,
                errors=errors
            )
        
        # Handle image upload
        image_url = None
        if 'image' in request.files:
            image_url = save_uploaded_file(request.files['image'])
        
        # Create item
        new_item = Item(
            title=title,
            description=description if description else None,
            category=category if category else None,
            size=size if size else None,
            seller_type=seller_type if seller_type else None,
            condition=condition if condition else None,
            price=price,
            image_url=image_url,
            seller_id=current_user.id,
            embedding=generate_embedding(f"{title} {description}")
        )
        
        db.session.add(new_item)
        db.session.commit()
        
        return success_response(
            data=serialize_item(new_item),
            message='Item created successfully',
            status_code=201
        )
    
    
    @api.route('/items/<int:item_id>', methods=['PUT'])
    @require_api_auth
    def update_item(item_id):
        """
        Update an existing item.
        
        PUT /api/v1/items/<item_id>
        
        Request body: Same as POST /items (all fields optional)
        
        Responses:
        - 200: Item updated successfully
        - 400: Validation error
        - 403: Not authorized (not item owner)
        - 404: Item not found
        """
        item = Item.query.get(item_id)
        
        if not item:
            return error_response(
                message='Item not found',
                status_code=404
            )
        
        # Check authorization
        if item.seller_id != current_user.id:
            return error_response(
                message='Not authorized to update this item',
                status_code=403
            )
        
        # Get update data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # Update fields
        if 'title' in data:
            title = data['title'].strip()
            if not title:
                return error_response(
                    message='Title cannot be empty',
                    status_code=400,
                    errors={'title': 'Title is required'}
                )
            item.title = title
        
        if 'description' in data:
            item.description = data['description'].strip() or None
        
        if 'category' in data:
            item.category = data['category'].strip() or None
        
        if 'size' in data:
            item.size = data['size'].strip() or None
        
        if 'seller_type' in data:
            item.seller_type = data['seller_type'].strip() or None
        
        if 'condition' in data:
            item.condition = data['condition'].strip() or None
        
        if 'price' in data:
            try:
                price_str = str(data['price']).replace('$', '').replace(',', '').strip()
                item.price = float(price_str)
                if item.price < 0:
                    raise ValueError()
            except (ValueError, AttributeError):
                return error_response(
                    message='Invalid price',
                    status_code=400,
                    errors={'price': 'Price must be a valid positive number'}
                )
        
        if 'is_active' in data:
            item.is_active = bool(data['is_active'])
        
        # Update image if provided
        if 'image' in request.files:
            new_image_url = save_uploaded_file(request.files['image'])
            if new_image_url:
                item.image_url = new_image_url
            else:
                return error_response(
                    message='Invalid image file',
                    status_code=400,
                    errors={'image': 'File type not allowed'}
                )
        
        # Update embedding
        item.embedding = generate_embedding(f"{item.title} {item.description or ''}")
        
        db.session.commit()
        
        return success_response(
            data=serialize_item(item),
            message='Item updated successfully'
        )
    
    
    @api.route('/items/<int:item_id>', methods=['DELETE'])
    @require_api_auth
    def delete_item(item_id):
        """
        Delete an item listing (soft delete via is_active).
        
        DELETE /api/v1/items/<item_id>
        
        Responses:
        - 200: Item deleted
        - 403: Not authorized
        - 404: Item not found
        """
        item = Item.query.get(item_id)
        
        if not item:
            return error_response(
                message='Item not found',
                status_code=404
            )
        
        # Check authorization
        if item.seller_id != current_user.id:
            return error_response(
                message='Not authorized to delete this item',
                status_code=403
            )
        
        # Soft delete
        item.is_active = False
        db.session.commit()
        
        return success_response(
            message='Item deleted successfully'
        )
    
    
    @api.route('/items/<int:item_id>/favorites', methods=['POST'])
    @require_api_auth
    def add_favorite(item_id):
        """
        Add item to user's favorites.
        
        POST /api/v1/items/<item_id>/favorites
        
        Responses:
        - 200: Added to favorites
        - 404: Item not found
        """
        item = Item.query.get(item_id)
        
        if not item or not item.is_active:
            return error_response(
                message='Item not found',
                status_code=404
            )
        
        if not current_user.favorites.filter_by(id=item.id).first():
            current_user.favorites.append(item)
            db.session.commit()
        
        return success_response(
            message='Added to favorites'
        )
    
    
    @api.route('/items/<int:item_id>/favorites', methods=['DELETE'])
    @require_api_auth
    def remove_favorite(item_id):
        """
        Remove item from user's favorites.
        
        DELETE /api/v1/items/<item_id>/favorites
        
        Responses:
        - 200: Removed from favorites
        - 404: Item not found
        """
        item = Item.query.get(item_id)
        
        if not item:
            return error_response(
                message='Item not found',
                status_code=404
            )
        
        if current_user.favorites.filter_by(id=item.id).first():
            current_user.favorites.remove(item)
            db.session.commit()
        
        return success_response(
            message='Removed from favorites'
        )
    
    
    @api.route('/items/autocomplete', methods=['GET'])
    def autocomplete():
        """
        Get search suggestions for autocomplete.
        
        GET /api/v1/items/autocomplete?q=jacket&limit=8
        
        Query parameters:
        - q: Search query (required)
        - limit: Max results (default: 8)
        
        Responses:
        - 200: List of matching items
        """
        query = request.args.get('q', '').strip()
        limit = request.args.get('limit', 8, type=int)
        
        if limit < 1 or limit > 50:
            limit = 8
        
        if not query:
            return success_response(
                data=[],
                message='No query provided'
            )
        
        items = (
            Item.query.filter_by(is_active=True)
            .filter(Item.title.ilike(f'%{query}%'))
            .order_by(Item.created_at.desc())
            .limit(limit)
            .all()
        )
        
        results = [
            {
                'id': item.id,
                'title': item.title,
                'image': item.image_url
            }
            for item in items
        ]
        
        return success_response(
            data=results,
            message='Autocomplete results retrieved'
        )

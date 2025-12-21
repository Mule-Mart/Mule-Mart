"""
Users API endpoints
REST endpoints for user profiles, listings, favorites, and stats
"""

from flask import request, current_app
from flask_login import current_user
from datetime import datetime
import os

from app.models import User, Item, Order, db
from .responses import (
    success_response,
    error_response,
    require_api_auth,
    serialize_user,
    serialize_item
)

# File upload configuration

ALLOWED_PROFILE_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def allowed_image(filename):
    """Check if profile image extension is allowed."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_PROFILE_IMAGE_EXTENSIONS
    )


def save_profile_image(file, user_id):
    """Save profile image and return relative path."""
    if not file or not file.filename:
        return None

    if not allowed_image(file.filename):
        return None

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{user_id}.{ext}"

    upload_dir = os.path.join(current_app.static_folder, "profile_images")
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    return f"profile_images/{filename}"


# Route registration

def register_routes(api):
    """Register users routes to the API blueprint."""


    # Public user endpoints


    @api.route("/users/<int:user_id>", methods=["GET"])
    def get_user(user_id):
        """Get public user profile information."""
        user = User.query.get(user_id)

        if not user:
            return error_response("User not found", 404)

        return success_response(
            data=serialize_user(user, include_stats=True),
            message="User profile retrieved successfully",
        )

    @api.route("/users/<int:user_id>/listings", methods=["GET"])
    def get_user_listings(user_id):
        """Get all active listings for a user."""
        user = User.query.get(user_id)
        if not user:
            return error_response("User not found", 404)

        page = max(request.args.get("page", 1, type=int), 1)
        per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

        query = Item.query.filter_by(seller_id=user_id, is_active=True)
        total = query.count()

        items = (
            query.order_by(Item.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return success_response(
            data={
                "seller": serialize_user(user),
                "listings": [serialize_item(item) for item in items],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page,
                },
            },
            message="User listings retrieved successfully",
        )


    # Authenticated user endpoints


    @api.route("/users/me", methods=["GET"])
    @require_api_auth
    def get_current_user_profile():
        """Get current authenticated user's profile."""
        return success_response(
            data=serialize_user(
                current_user, include_email=True, include_stats=True
            ),
            message="Current user profile retrieved successfully",
        )

    @api.route("/users/me", methods=["PUT"])
    @require_api_auth
    def update_current_user():
        """Update current user's profile."""
        if request.is_json:
            data = request.get_json()
            first_name = data.get("first_name", "").strip()
            last_name = data.get("last_name", "").strip()
        else:
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()

        errors = {}
        if not first_name:
            errors["first_name"] = "First name is required"
        if not last_name:
            errors["last_name"] = "Last name is required"

        if errors:
            return error_response("Validation failed", 400, errors)

        current_user.first_name = first_name
        current_user.last_name = last_name

        if "profile_image" in request.files:
            image_path = save_profile_image(
                request.files["profile_image"], current_user.id
            )
            if not image_path:
                return error_response(
                    "Invalid profile image",
                    400,
                    {"profile_image": "Unsupported file type"},
                )
            current_user.profile_image = image_path

        db.session.commit()

        return success_response(
            data=serialize_user(
                current_user, include_email=True, include_stats=True
            ),
            message="Profile updated successfully",
        )

    @api.route("/users/me/listings", methods=["GET"])
    @require_api_auth
    def get_my_listings():
        """Get all listings created by the current user."""
        search = request.args.get("search", "").strip()
        page = max(request.args.get("page", 1, type=int), 1)
        per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

        query = Item.query.filter_by(seller_id=current_user.id)

        if search:
            for term in search.split():
                query = query.filter(Item.title.ilike(f"%{term}%"))

        total = query.count()

        items = (
            query.order_by(Item.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return success_response(
            data={
                "listings": [serialize_item(item) for item in items],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page,
                },
                "filters": {"search": search},
            },
            message="Your listings retrieved successfully",
        )

    @api.route("/users/me/favorites", methods=["GET"])
    @require_api_auth
    def get_my_favorites():
        """Get current user's favorite items."""
        page = max(request.args.get("page", 1, type=int), 1)
        per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

        query = current_user.favorites
        total = query.count()

        items = (
            query.order_by(Item.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return success_response(
            data={
                "favorites": [serialize_item(item) for item in items],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page,
                },
            },
            message="Your favorites retrieved successfully",
        )

    @api.route("/users/me/recently-viewed", methods=["GET"])
    @require_api_auth
    def get_recently_viewed():
        """Get recently viewed items."""
        from app.models import RecentlyViewed

        limit = request.args.get("limit", 10, type=int)
        limit = min(max(limit, 1), 50)

        views = (
            current_user.viewed_history
            .order_by(RecentlyViewed.viewed_at.desc())
            .limit(limit)
            .all()
        )

        return success_response(
            data={
                "recently_viewed": [
                    {
                        "item": serialize_item(view.item),
                        "viewed_at": view.viewed_at.isoformat()
                        if view.viewed_at
                        else None,
                    }
                    for view in views
                ]
            },
            message="Recently viewed items retrieved successfully",
        )

    @api.route("/users/me/stats", methods=["GET"])
    @require_api_auth
    def get_user_stats():
        """Get account statistics for current user."""
        listings_active = Item.query.filter_by(
            seller_id=current_user.id, is_active=True
        ).count()

        listings_total = Item.query.filter_by(
            seller_id=current_user.id
        ).count()

        orders_as_buyer = Order.query.filter_by(
            buyer_id=current_user.id
        ).count()

        orders_as_seller = (
            Order.query.join(Item)
            .filter(Item.seller_id == current_user.id)
            .count()
        )

        return success_response(
            data={
                "account_created": current_user.created_at.isoformat()
                if current_user.created_at
                else None,
                "is_verified": current_user.is_verified,
                "listings": {
                    "active": listings_active,
                    "total": listings_total,
                },
                "orders": {
                    "as_buyer": orders_as_buyer,
                    "as_seller": orders_as_seller,
                },
                "favorites": current_user.favorites.count(),
                "recently_viewed": current_user.viewed_history.count(),
            },
            message="User statistics retrieved successfully",
        )

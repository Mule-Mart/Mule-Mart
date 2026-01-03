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
    serialize_item,
    validate_json,
)

from app.services.storage_service import (
    is_mimetype_allowed,
    generate_unique_filename,
    generate_put_url,
    delete_file,
    validate_profile_image_upload,
    PROFILE_IMAGES_FOLDER,
)

from app.services.user_service import get_user_activity_stats


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

        query = Item.query.filter_by(
            seller_id=user_id, is_active=True, is_deleted=False
        )
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
            data=serialize_user(current_user, include_email=True, include_stats=True),
            message="Current user profile retrieved successfully",
        )

    @api.route("/users/me", methods=["PUT"])
    @require_api_auth
    def update_current_user():
        """Update current user's profile."""
        data = request.get_json()
        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        uploaded_image_filename = data.get("uploaded_image_filename", "").strip()

        errors = {}
        if not first_name:
            errors["first_name"] = "First name is required"
        elif len(first_name) > 150:
            errors["first_name"] = "First name must be less than 150 characters"
        if not last_name:
            errors["last_name"] = "Last name is required"
        elif len(last_name) > 150:
            errors["last_name"] = "Last name must be less than 150 characters"

        if errors:
            return error_response("Validation failed", 400, errors)

        old_profile_image = None
        if uploaded_image_filename:
            try:
                is_valid, error_message = validate_profile_image_upload(
                    new_profile_image=uploaded_image_filename,
                    old_profile_image=current_user.profile_image,
                )

                if not is_valid:
                    current_app.logger.error(error_message)
                    return error_response(message=error_message, status_code=400)

                old_profile_image = current_user.profile_image
                current_user.profile_image = uploaded_image_filename

            except Exception:
                current_app.logger.exception(
                    "An error occurred while updating the user's profile image."
                )
                return error_response(
                    message="There was an error updating the user's profile image. Please try again later.",
                    status_code=500,
                )

        current_user.first_name = first_name
        current_user.last_name = last_name

        try:
            db.session.commit()
        except Exception:
            current_app.logger.exception(
                "An error occurred while updating the user's profile image."
            )
            return error_response(
                message="There was an error updating the user's profile image. Please try again later.",
                status_code=500,
            )

        if old_profile_image and not delete_file(filename=old_profile_image):
            current_app.logger.warning(
                f"Failed to delete old profile image: `{old_profile_image}`"
            )

        return success_response(
            data=serialize_user(current_user, include_email=True, include_stats=True),
            message="Profile updated successfully",
        )

    @api.route("/users/me/listings", methods=["GET"])
    @require_api_auth
    def get_my_listings():
        """Get all listings created by the current user."""
        search = request.args.get("search", "").strip()
        page = max(request.args.get("page", 1, type=int), 1)
        per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

        query = Item.query.filter_by(seller_id=current_user.id, is_deleted=False)

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

        query = current_user.favorites.filter_by(is_deleted=False)
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
            current_user.viewed_history.join(Item)
            .filter(Item.is_deleted == False)
            .order_by(RecentlyViewed.viewed_at.desc())
            .limit(limit)
            .all()
        )

        return success_response(
            data={
                "recently_viewed": [
                    {
                        "item": serialize_item(view.item),
                        "viewed_at": (
                            view.viewed_at.isoformat() if view.viewed_at else None
                        ),
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
        user_stats = get_user_activity_stats(current_user)
        return success_response(
            data=user_stats, message="User statistics retrieved successfully!"
        )

    @api.route("/users/me/profile-image-url", methods=["POST"])
    @require_api_auth
    @validate_json("filename", "contentType")
    def profile_image_put_url():
        data = request.get_json()
        filename = data.get("filename", "").strip()
        contentType = data.get("contentType", "").strip()

        if not filename or not contentType:
            return error_response(
                message="filename and content type cannot be empty", status_code=400
            )
        if not is_mimetype_allowed(mimetype=contentType):
            return error_response(
                message=f"Unsupported content type: `{contentType}`", status_code=400
            )

        unique_filename = generate_unique_filename(
            original_filename=filename,
            folder=PROFILE_IMAGES_FOLDER,
            content_type=contentType,
        )

        put_url = generate_put_url(filename=unique_filename, content_type=contentType)

        if not put_url:
            return error_response(
                message="There was an error generating the profile image upload URL. Please try again later.",
                status_code=500,
            )

        return success_response(
            message="Image upload URL generated successfully",
            status_code=200,
            data={"putUrl": put_url, "newFilename": unique_filename},
        )

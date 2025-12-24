"""
Chat API endpoints
REST endpoints for messaging between users
"""

from flask import request
from flask_login import current_user
from sqlalchemy import or_, func

from app.models import Chat, User, db
from .responses import (
    success_response,
    error_response,
    validate_json,
    require_api_auth,
    serialize_user,
    serialize_chat_message,
)


def register_routes(api):
    """Register chat routes to the API blueprint."""

    # Conversations

    @api.route("/chat/conversations", methods=["GET"])
    @require_api_auth
    def get_conversations():
        """Get all conversations for the current user."""
        page = max(request.args.get("page", 1, type=int), 1)
        per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

        users = (
            User.query.join(
                Chat,
                or_(
                    Chat.sender_id == User.id,
                    Chat.receiver_id == User.id,
                ),
            )
            .filter(
                or_(
                    Chat.sender_id == current_user.id,
                    Chat.receiver_id == current_user.id,
                )
            )
            .filter(User.id != current_user.id)
            .distinct()
            .order_by(User.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        conversations = []
        for user in users:
            last_message = (
                Chat.query.filter(
                    or_(
                        (Chat.sender_id == current_user.id)
                        & (Chat.receiver_id == user.id),
                        (Chat.sender_id == user.id)
                        & (Chat.receiver_id == current_user.id),
                    )
                )
                .order_by(Chat.timestamp.desc())
                .first()
            )

            unread_count = Chat.query.filter_by(
                sender_id=user.id,
                receiver_id=current_user.id,
                is_read=False,
            ).count()

            conversations.append(
                {
                    "user": serialize_user(user),
                    "last_message": (
                        serialize_chat_message(last_message) if last_message else None
                    ),
                    "unread_count": unread_count,
                }
            )

        return success_response(
            data={
                "conversations": conversations,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                },
            },
            message="Conversations retrieved successfully",
        )

    # Messages

    @api.route("/chat/<int:user_id>/messages", methods=["GET"])
    @require_api_auth
    def get_conversation(user_id):
        """Get all messages between current user and another user."""
        other_user = User.query.get(user_id)
        if not other_user:
            return error_response("User not found", 404)

        page = max(request.args.get("page", 1, type=int), 1)
        per_page = min(max(request.args.get("per_page", 50, type=int), 1), 100)

        query = Chat.query.filter(
            or_(
                (Chat.sender_id == current_user.id) & (Chat.receiver_id == user_id),
                (Chat.sender_id == user_id) & (Chat.receiver_id == current_user.id),
            )
        )

        total = query.count()

        messages = (
            query.order_by(Chat.timestamp.asc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        Chat.query.filter_by(
            sender_id=user_id,
            receiver_id=current_user.id,
            is_read=False,
        ).update({"is_read": True})

        db.session.commit()

        return success_response(
            data={
                "other_user": serialize_user(other_user),
                "messages": [serialize_chat_message(m) for m in messages],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page,
                },
            },
            message="Messages retrieved successfully",
        )

    # Send message

    @api.route("/chat/<int:user_id>/messages", methods=["POST"])
    @require_api_auth
    @validate_json("content")
    def send_message(user_id):
        """Send a message to another user."""
        if user_id == current_user.id:
            return error_response("Cannot message yourself", 400)

        recipient = User.query.get(user_id)
        if not recipient:
            return error_response("Recipient not found", 404)

        content = request.get_json()["content"].strip()
        if not content:
            return error_response(
                "Message content cannot be empty",
                400,
                {"content": "Content is required"},
            )

        if len(content) > 5000:
            return error_response(
                "Message too long",
                400,
                {"content": "Max length is 5000 characters"},
            )

        message = Chat(
            sender_id=current_user.id,
            receiver_id=user_id,
            content=content,
        )

        db.session.add(message)
        db.session.commit()

        return success_response(
            data=serialize_chat_message(message),
            message="Message sent successfully",
            status_code=201,
        )

    # Read status

    @api.route("/chat/unread-count", methods=["GET"])
    @require_api_auth
    def get_unread_count():
        """Get unread message count."""
        total = Chat.query.filter_by(
            receiver_id=current_user.id,
            is_read=False,
        ).count()

        breakdown = (
            db.session.query(
                Chat.sender_id,
                func.count(Chat.id).label("count"),
            )
            .filter(
                Chat.receiver_id == current_user.id,
                Chat.is_read.is_(False),
            )
            .group_by(Chat.sender_id)
            .all()
        )

        return success_response(
            data={
                "total_unread": total,
                "by_sender": [
                    {"sender_id": sid, "unread_count": count}
                    for sid, count in breakdown
                ],
            },
            message="Unread count retrieved successfully",
        )

    @api.route("/chat/<int:user_id>/messages/mark-read", methods=["POST"])
    @require_api_auth
    def mark_messages_as_read(user_id):
        """Mark all messages from a user as read."""
        if not User.query.get(user_id):
            return error_response("User not found", 404)

        updated = Chat.query.filter_by(
            sender_id=user_id,
            receiver_id=current_user.id,
            is_read=False,
        ).update({"is_read": True})

        db.session.commit()

        return success_response(
            data={"marked_read": updated},
            message=f"Marked {updated} messages as read",
        )

    # Delete message

    @api.route("/chat/messages/<int:message_id>", methods=["DELETE"])
    @require_api_auth
    def delete_message(message_id):
        """Delete a message (sender only)."""
        message = Chat.query.get(message_id)
        if not message:
            return error_response("Message not found", 404)

        if message.sender_id != current_user.id:
            return error_response("Not authorized", 403)

        db.session.delete(message)
        db.session.commit()

        return success_response(message="Message deleted successfully")

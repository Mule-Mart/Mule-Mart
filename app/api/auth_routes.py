"""
Auth API endpoints
REST authentication routes
"""

from flask import request, current_app
from flask_login import login_user, logout_user, current_user

from app.services.auth_service import (
    create_user,
    authenticate_user,
    generate_password_reset,
    reset_password_with_token,
    verify_email_token,
    resend_verification_email,
)

from .responses import (
    success_response,
    error_response,
    require_api_auth,
    validate_json,
)


def register_routes(api):
    """Register auth routes to the API blueprint."""

    @api.route("/auth/signup", methods=["POST"])
    @validate_json("first_name", "last_name", "email", "password", "confirm_password")
    def api_signup():
        data = request.get_json()

        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        confirm_password = data.get("confirm_password", "")

        user, error = create_user(
            first_name, last_name, email, password, confirm_password
        )

        if error:
            return error_response(error, 400)

        return success_response(message="Account created. Please verify your email.")

    @api.route("/auth/login", methods=["POST"])
    @validate_json("email", "password")
    def api_login():
        data = request.get_json()

        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        user, error = authenticate_user(email, password)

        if error:
            return error_response(error, 401)

        login_user(user)

        return success_response(message="Login successful")

    @api.route("/auth/logout", methods=["POST"])
    @require_api_auth
    def api_logout():
        logout_user()
        return success_response(message="Logged out successfully")

    @api.route("/auth/forgot-password", methods=["POST"])
    @validate_json("email")
    def api_forgot_password():
        data = request.get_json()
        email = data.get("email", "").strip().lower()

        success = generate_password_reset(email)

        if not success:
            current_app.logger.error(
                f"No account was found with the email address `{email}`"
            )

        return success_response(message="Password reset instructions sent")

    @api.route("/auth/reset-password", methods=["POST"])
    @validate_json("token", "password")
    def api_reset_password():
        data = request.get_json()
        token = data.get("token")
        new_password = data.get("password")

        if not token or not new_password:
            return error_response("Token and password required", 400)

        success = reset_password_with_token(token, new_password)

        if not success:
            return error_response("Invalid or expired token", 400)

        return success_response(message="Password reset successful")

    @api.route("/auth/verify/<token>", methods=["GET"])
    def api_verify_email(token):
        success = verify_email_token(token)

        if not success:
            return error_response("Invalid or expired verification token", 400)

        return success_response(message="Email verified successfully")

    @api.route("/auth/resend-verification", methods=["POST"])
    @validate_json("email")
    def api_resend_verification():
        data = request.get_json()
        email = data.get("email", "").strip()

        if not email:
            return error_response(message="Email cannot be empty", status_code=400)

        resend_verification_email(email=email)

        return success_response(
            message=f"If an account exists with `{email}`, a verification email has been sent.",
            status_code=200,
        )

    @api.route("/auth/me", methods=["GET"])
    @require_api_auth
    def api_me():
        return success_response(
            data={
                "id": current_user.id,
                "first_name": current_user.first_name,
                "last_name": current_user.last_name,
                "email": current_user.email,
                "is_verified": current_user.is_verified,
            }
        )

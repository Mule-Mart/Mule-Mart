from flask import Flask, redirect, url_for
from auth import auth
import os

def create_app():
    # paths for templates and static files
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), '../frontend/templates'),
        static_folder=os.path.join(os.path.dirname(__file__), '../frontend/static')
    )

    app.secret_key = "your_secret_key_here"

    # Redirect root URL ("/") to login page for secure access
    @app.route('/')
    def home():
        return redirect(url_for('auth.login'))

    # Register the authentication blueprint
    app.register_blueprint(auth, url_prefix="/auth")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

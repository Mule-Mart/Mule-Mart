from flask import Blueprint, render_template
from flask_login import login_required, current_user

# Create a new blueprint for main pages
main = Blueprint('main', __name__)

@main.route('/')
@login_required
def home():
    """
    Displays the homepage after a successful login or signup.
    Requires user to be authenticated.
    """
    return render_template('home.html', user=current_user, items=[], recent_items=[])

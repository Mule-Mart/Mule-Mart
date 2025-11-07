from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from .models import Item, db

# Create a new blueprint for main pages
main = Blueprint("main", __name__)


@main.route("/")
@login_required
def home():
    """
    Displays the homepage after a successful login or signup.
    Requires user to be authenticated.
    """
    categories = ["electronics", "clothing", "furniture"]
    category_items = [
        Item.query.filter_by(category=category).order_by(Item.created_at.desc()).first()
        for category in categories
    ]
    category_items = [
        category_item for category_item in category_items if category_item is not None
    ]
    recent_items = Item.query.order_by(Item.created_at.desc()).limit(6).all()
    return render_template(
        "home.html",
        user=current_user,
        category_items=category_items,
        recent_items=recent_items,
    )


@main.route("/buy_item")
@login_required
def buy_item():
    """
    Displays all items available for purchase with filtering and sorting.
    """
    # Get query parameters
    category = request.args.get("category", type=str)
    seller_type = request.args.get("seller_type", type=str)
    condition = request.args.get("condition", type=str)
    search = request.args.get("search", type=str)
    sort_by = request.args.get("sort_by", default="newest", type=str)

    # Start with base query
    query = Item.query

    # Apply filters
    if category:
        query = query.filter_by(category=category)

    if seller_type:
        query = query.filter_by(seller_type=seller_type)

    if condition:
        query = query.filter_by(condition=condition)

    # Apply search
    if search:
        query = query.filter(
            Item.title.ilike(f"%{search}%") | Item.description.ilike(f"%{search}%")
        )

    # Apply sorting
    if sort_by == "newest":
        query = query.order_by(Item.created_at.desc())
    elif sort_by == "oldest":
        query = query.order_by(Item.created_at.asc())
    elif sort_by == "price_low":
        query = query.order_by(Item.price.asc())
    elif sort_by == "price_high":
        query = query.order_by(Item.price.desc())
    else:
        query = query.order_by(Item.created_at.desc())

    # Get all items
    items = query.all()

    # Get unique values for filter options
    all_categories = db.session.query(Item.category).distinct().all()
    categories = [cat[0] for cat in all_categories if cat[0]]

    all_seller_types = db.session.query(Item.seller_type).distinct().all()
    seller_types = [st[0] for st in all_seller_types if st[0]]

    all_conditions = db.session.query(Item.condition).distinct().all()
    conditions = [cond[0] for cond in all_conditions if cond[0]]

    return render_template(
        "buy_item.html",
        items=items,
        categories=categories,
        seller_types=seller_types,
        conditions=conditions,
        current_category=category,
        current_seller_type=seller_type,
        current_condition=condition,
        current_search=search,
        current_sort=sort_by,
        item_count=len(items),
    )

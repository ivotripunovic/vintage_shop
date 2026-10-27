from .services import pending_sales


def pending_ratings(request):
    """Number of sales waiting for the user's rating, for the menu badge."""
    if not request.user.is_authenticated:
        return {}
    return {"pending_ratings_count": pending_sales(request.user).count()}

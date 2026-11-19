from .services import pending_sales


def pending_ratings(request):
    """Number of sales waiting for the user's rating, for the menu badge."""
    # request.user is missing when an error page is rendered for a request
    # rejected before AuthenticationMiddleware ran (e.g. a disallowed Host)
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"pending_ratings_count": pending_sales(user).count()}

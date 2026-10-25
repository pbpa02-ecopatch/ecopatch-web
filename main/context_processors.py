from django.conf import settings


def google_auth(request):
    """Lets the login and register pages show the Google button only when the credentials are configured."""
    return {'google_auth_enabled': settings.GOOGLE_AUTH_ENABLED}

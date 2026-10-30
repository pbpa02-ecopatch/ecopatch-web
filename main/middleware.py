from django.conf import settings
from django.shortcuts import render


class MaintenanceModeMiddleware:
    """While MAINTENANCE_MODE is on, visitors get the "EcoPatch is being prepared" page (HTTP 503).

    Staff can still get in: /admin/ stays open to log in, and a logged-in staff member sees the site as usual.
    Static files are served earlier by WhiteNoise, so the page keeps its fonts and styles. It is off by default,
    so local work and the tests are not affected; on PWS set MAINTENANCE_MODE=True in the environment.
    """

    OPEN_PREFIXES = ('/admin/',)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.MAINTENANCE_MODE and not self._may_pass(request):
            response = render(request, 'maintenance.html', status=503)
            response['Retry-After'] = '3600'
            return response
        return self.get_response(request)

    def _may_pass(self, request):
        if request.path.startswith(self.OPEN_PREFIXES):
            return True
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and user.is_staff)

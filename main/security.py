"""Security headers that Django does not send by itself.

Django's SecurityMiddleware already adds X-Content-Type-Options, Referrer-Policy and Cross-Origin-Opener-Policy,
and XFrameOptionsMiddleware adds X-Frame-Options. This adds the two that need to know about EcoPatch:

* Content-Security-Policy, so a script injected into a page cannot pull code from, or send data to, a stranger's
  server, and the page cannot be framed, rebased (<base>) or turned into a form that posts somewhere else.
  Inline scripts and styles are still allowed because the pages use them (so the policy is a second line of
  defence; the first one is that everything typed by a person is escaped before it reaches a page).
* Permissions-Policy, which switches off the browser features the site never uses.

Uploaded files get a much stricter policy: they are only ever pictures, so nothing in them may run.
"""
from django.conf import settings

# Every host a page loads something from: Bootstrap and the icons font (jsDelivr), htmx (unpkg), Three.js and
# Rellax on the landing page (cdnjs), and the Baloo 2 / Plus Jakarta Sans fonts (Google Fonts).
CSP_PAGE = '; '.join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
    "font-src 'self' data: https://fonts.gstatic.com",
    # plant photos can be a link to a picture elsewhere (Plant.image_url), so any https image is fine
    "img-src 'self' data: blob: https:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    # the Google sign-in answers a form post with a redirect to accounts.google.com, which counts as a form target
    "form-action 'self' https://accounts.google.com",
    "frame-ancestors 'none'",
])

CSP_UPLOAD = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox"

PERMISSIONS_POLICY = 'camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()'


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(settings.MEDIA_URL):
            response.headers['Content-Security-Policy'] = CSP_UPLOAD
        else:
            response.headers.setdefault('Content-Security-Policy', CSP_PAGE)
        response.headers.setdefault('Permissions-Policy', PERMISSIONS_POLICY)
        return response

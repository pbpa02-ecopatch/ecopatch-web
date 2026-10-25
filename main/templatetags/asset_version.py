import hashlib
import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()

# path on disk -> (mtime, size, digest); the file is only re-read when it changed
_digests = {}


def _digest(path):
    stat = os.stat(path)
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _digests.get(path)
    if cached and cached[0] == stamp:
        return cached[1]
    with open(path, 'rb') as f:
        digest = hashlib.md5(f.read(), usedforsecurity=False).hexdigest()[:10]
    _digests[path] = (stamp, digest)
    return digest


@register.simple_tag
def static_v(path):
    """Like {% static %}, plus ?v=<hash of the file>.

    The URL changes whenever the file's content changes, so a browser that cached
    an older copy fetches the new one instead of mixing new HTML with old CSS/JS.
    """
    url = static(path)
    found = finders.find(path)
    if not found or isinstance(found, (list, tuple)):
        return url
    try:
        return f'{url}?v={_digest(found)}'
    except OSError:
        return url

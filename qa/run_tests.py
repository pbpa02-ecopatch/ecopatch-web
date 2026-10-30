"""Run Django tests with uploads isolated from real project media."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecopatch_project.settings')
from django.conf import settings
from django.core.management import execute_from_command_line

with tempfile.TemporaryDirectory(prefix='ecopatch-tests-') as media:
    settings.MEDIA_ROOT = Path(media)
    execute_from_command_line(['manage.py', 'test', *sys.argv[1:]])

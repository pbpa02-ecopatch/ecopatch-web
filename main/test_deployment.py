import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase


SETTINGS_FILE = Path(__file__).resolve().parents[1] / 'ecopatch_project' / 'settings.py'
STRONG_KEY = 'audit-only-' + 'abc123DEFxyz-' * 5


class DeploymentSettingsTests(SimpleTestCase):
    def load(self, **env):
        with patch.dict(os.environ, env, clear=True):
            return runpy.run_path(str(SETTINGS_FILE))

    def test_production_requires_a_private_secret(self):
        for value in ('', 'short', 'django-insecure-' + 'a' * 60, 'a' * 60):
            with self.subTest(value=value[:10]), self.assertRaises(ImproperlyConfigured):
                self.load(DEBUG='False', SECRET_KEY=value)

    def test_production_uses_secure_cookies_and_redirect(self):
        config = self.load(DEBUG='false', SECRET_KEY=STRONG_KEY)
        self.assertFalse(config['DEBUG'])
        for key in ('SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE', 'SECURE_SSL_REDIRECT'):
            self.assertTrue(config.get(key), key)

    def test_environment_configures_hosts_and_proxy_without_source_edits(self):
        config = self.load(DEBUG='false', SECRET_KEY=STRONG_KEY,
            ALLOWED_HOSTS='example.com, www.example.com ',
            CSRF_TRUSTED_ORIGINS='https://example.com,https://www.example.com',
            BEHIND_HTTPS_PROXY='true', SECURE_HSTS_SECONDS='3600')
        self.assertEqual(config['ALLOWED_HOSTS'], ['example.com', 'www.example.com'])
        self.assertEqual(config['CSRF_TRUSTED_ORIGINS'], ['https://example.com', 'https://www.example.com'])
        self.assertEqual(config.get('SECURE_PROXY_SSL_HEADER'), ('HTTP_X_FORWARDED_PROTO', 'https'))
        self.assertEqual(config.get('SECURE_HSTS_SECONDS'), 3600)

    def test_local_http_remains_supported(self):
        config = self.load(DEBUG='true')
        self.assertTrue(config['DEBUG'])
        self.assertFalse(config['SESSION_COOKIE_SECURE'])
        self.assertFalse(config.get('SECURE_SSL_REDIRECT'))

    def test_production_redirect_can_be_handled_by_a_trusted_proxy(self):
        config = self.load(DEBUG='false', SECRET_KEY=STRONG_KEY, SECURE_SSL_REDIRECT='false')
        self.assertFalse(config.get('SECURE_SSL_REDIRECT'))

    def test_production_database_url_is_optional_and_never_overrides_local_default(self):
        config = self.load(DEBUG='true')
        self.assertEqual(config['DATABASES']['default']['ENGINE'], 'django.db.backends.sqlite3')

    def test_postgres_url_supports_encoded_credentials_and_ssl(self):
        config = self.load(DEBUG='false', SECRET_KEY=STRONG_KEY,
            DATABASE_URL='postgresql://eco:p%40ss@database.example:5433/ecopatch?sslmode=require')
        database = config['DATABASES']['default']
        self.assertEqual(database['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(database['NAME'], 'ecopatch')
        self.assertEqual(database['USER'], 'eco')
        self.assertEqual(database['PASSWORD'], 'p@ss')
        self.assertEqual(database['HOST'], 'database.example')
        self.assertEqual(database['PORT'], 5433)
        self.assertEqual(database['OPTIONS'], {'sslmode': 'require'})

    def test_invalid_database_url_is_reported_before_startup(self):
        for value in ('mysql://host/db', 'postgres://host/', 'postgres://host:wrong/db'):
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                self.load(DEBUG='false', SECRET_KEY=STRONG_KEY, DATABASE_URL=value)

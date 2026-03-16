"""
Tests for the logo upload → splash screen display flow.

Root cause fixed: portal stored logo_url as a relative path
(e.g. /static/uploads/logos/...) while the Windows client
only fetches logos whose URL starts with http:// or https://.

Fix 1 (portal_dashboard.py): store an absolute URL by calling
    get_public_base_url() when constructing logo_url on upload.
Fix 2 (admin_api.py): convert any legacy relative URL to absolute
    using the PORTAL_PUBLIC_BASE_URL env var for backward compatibility.
"""

import io
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Inline the pure helper so we can test it without triggering module-level DB
# init (portal_database.py creates /opt/iptv-panel/iptv_business.db on import).
# ---------------------------------------------------------------------------

def logo_url_to_disk_path(logo_url, upload_dir):
    """Copy of portal_dashboard.logo_url_to_disk_path for isolated testing."""
    try:
        parsed = urlparse(logo_url)
        url_path = parsed.path if parsed.scheme else logo_url
        filename = os.path.basename(url_path)
        if not filename:
            return None
        candidate = os.path.realpath(os.path.join(upload_dir, filename))
        real_upload_dir = os.path.realpath(upload_dir)
        # Use os.path.commonpath for a robust cross-platform containment check
        if os.path.commonpath([candidate, real_upload_dir]) != real_upload_dir:
            return None
        if candidate == real_upload_dir:
            return None
        return candidate
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers to stand-up minimal Flask apps without touching the real filesystem
# ---------------------------------------------------------------------------

def _make_admin_app(db_path):
    """Return a minimal Flask test app for admin_api."""
    admin_dir = os.path.join(os.path.dirname(__file__), '..', 'admin')
    admin_dir = os.path.realpath(admin_dir)
    if admin_dir not in sys.path:
        sys.path.insert(0, admin_dir)

    # Inject a stub admin_database module that uses our temp DB
    mock_adb = types.ModuleType('admin_database')

    def _get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    mock_adb.get_db_connection = _get_db
    sys.modules['admin_database'] = mock_adb

    # Re-import admin_api fresh each time
    if 'admin_api' in sys.modules:
        del sys.modules['admin_api']

    import admin_api

    from flask import Flask
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(admin_api.api_bp)
    return app


def _init_admin_db(db_path, logo_url):
    """Seed an in-memory-style SQLite DB with one license and one customization."""
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY,
            license_key TEXT UNIQUE,
            customer_name TEXT,
            status TEXT DEFAULT 'active',
            device_id TEXT,
            last_used DATETIME,
            features TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS customizations (
            id INTEGER PRIMARY KEY,
            license_key TEXT UNIQUE,
            app_name TEXT,
            logo_url TEXT,
            theme TEXT DEFAULT 'dark',
            primary_color TEXT,
            secondary_color TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS license_profiles (
            id INTEGER PRIMARY KEY,
            license_key TEXT,
            profile_name TEXT,
            dns_url TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.execute(
        "INSERT INTO licenses (license_key, customer_name, status, features) "
        "VALUES (?, ?, 'active', '{}')",
        ('X87-TEST-0000-AAAA', 'Test Customer'),
    )
    conn.execute(
        'INSERT INTO customizations (license_key, app_name, logo_url) VALUES (?, ?, ?)',
        ('X87-TEST-0000-AAAA', 'TestApp', logo_url),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# 1. Pure unit tests: logo_url_to_disk_path()
# ---------------------------------------------------------------------------

class TestLogoUrlToDiskPath(unittest.TestCase):
    """logo_url_to_disk_path resolves URLs to filesystem paths safely."""

    def setUp(self):
        self.upload_dir = tempfile.mkdtemp()

    def test_absolute_https_url_extracts_filename(self):
        path = logo_url_to_disk_path(
            'https://portal.example.com/static/uploads/logos/test_logo.png',
            self.upload_dir,
        )
        self.assertIsNotNone(path)
        self.assertTrue(path.startswith(self.upload_dir))
        self.assertTrue(path.endswith('test_logo.png'))

    def test_relative_path_extracts_filename(self):
        path = logo_url_to_disk_path(
            '/static/uploads/logos/old_logo.png',
            self.upload_dir,
        )
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith('old_logo.png'))

    def test_path_traversal_is_contained_in_upload_dir(self):
        # os.path.basename() strips directory traversal sequences, so the
        # final filename resolves safely inside the upload_dir.
        path = logo_url_to_disk_path(
            'https://portal.example.com/static/uploads/logos/../../etc/passwd',
            self.upload_dir,
        )
        # The function may return a path or None; what matters is it NEVER
        # escapes upload_dir.
        if path is not None:
            self.assertTrue(
                path.startswith(self.upload_dir),
                f'Resolved path must stay inside upload_dir, got: {path}',
            )
            self.assertNotIn('/etc/', path, 'Must not resolve to /etc/passwd')

    def test_empty_filename_returns_none(self):
        # URL ends with a slash — no filename component
        path = logo_url_to_disk_path(
            'https://portal.example.com/static/uploads/logos/',
            self.upload_dir,
        )
        self.assertIsNone(path)


# ---------------------------------------------------------------------------
# 2. admin_api: logo_url normalization in /api/license/validate
# ---------------------------------------------------------------------------

class TestAdminApiLogoUrlConversion(unittest.TestCase):
    """admin_api must return an absolute logo_url to the client."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        os.environ.pop('PORTAL_PUBLIC_BASE_URL', None)

    def test_relative_logo_url_converted_when_env_set(self):
        """A legacy relative logo_url is upgraded to an absolute URL."""
        db = os.path.join(self.tmp, 'test1.db')
        _init_admin_db(db, '/static/uploads/logos/old_logo.png')

        os.environ['PORTAL_PUBLIC_BASE_URL'] = 'https://portal.example.com'
        app = _make_admin_app(db)
        with app.test_client() as client:
            resp = client.post(
                '/api/license/validate',
                json={'license_key': 'X87-TEST-0000-AAAA', 'hardware_id': 'hw123'},
                content_type='application/json',
            )
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        self.assertTrue(body.get('success'), body)
        logo = body['user_settings']['logo_url']
        self.assertTrue(
            logo.startswith('https://'),
            f'Expected absolute HTTPS URL, got: {logo}',
        )
        self.assertIn('portal.example.com', logo)
        self.assertIn('old_logo.png', logo)

    def test_relative_logo_url_cleared_when_env_not_set(self):
        """Without PORTAL_PUBLIC_BASE_URL, a relative URL becomes empty (not broken)."""
        db = os.path.join(self.tmp, 'test2.db')
        _init_admin_db(db, '/static/uploads/logos/old_logo.png')

        os.environ.pop('PORTAL_PUBLIC_BASE_URL', None)
        app = _make_admin_app(db)
        with app.test_client() as client:
            resp = client.post(
                '/api/license/validate',
                json={'license_key': 'X87-TEST-0000-AAAA', 'hardware_id': 'hw123'},
                content_type='application/json',
            )
        body = json.loads(resp.data)
        logo = body['user_settings']['logo_url']
        # Must NOT forward a relative URL — the client would silently ignore it
        self.assertFalse(
            logo.startswith('/'),
            f'Relative logo_url must not be forwarded to client, got: {logo!r}',
        )

    def test_absolute_logo_url_passed_through_unchanged(self):
        """An already-absolute logo_url is returned as-is."""
        db = os.path.join(self.tmp, 'test3.db')
        abs_url = 'https://portal.example.com/static/uploads/logos/new_logo.png'
        _init_admin_db(db, abs_url)

        app = _make_admin_app(db)
        with app.test_client() as client:
            resp = client.post(
                '/api/license/validate',
                json={'license_key': 'X87-TEST-0000-AAAA', 'hardware_id': 'hw123'},
                content_type='application/json',
            )
        body = json.loads(resp.data)
        self.assertEqual(body['user_settings']['logo_url'], abs_url)

    def test_null_logo_url_returns_empty_string(self):
        """A NULL logo_url in the DB becomes an empty string (not None)."""
        db = os.path.join(self.tmp, 'test4.db')
        _init_admin_db(db, None)

        app = _make_admin_app(db)
        with app.test_client() as client:
            resp = client.post(
                '/api/license/validate',
                json={'license_key': 'X87-TEST-0000-AAAA', 'hardware_id': 'hw123'},
                content_type='application/json',
            )
        body = json.loads(resp.data)
        logo = body['user_settings']['logo_url']
        self.assertIsNotNone(logo)
        self.assertEqual(logo, '')


# ---------------------------------------------------------------------------
# 3. Verify get_public_base_url() uses the PORTAL_PUBLIC_BASE_URL env var
# ---------------------------------------------------------------------------

class TestGetPublicBaseUrl(unittest.TestCase):
    """get_public_base_url() must prefer the PORTAL_PUBLIC_BASE_URL env var."""

    def _call_in_request_context(self, env_value=None):
        """
        Import and call get_public_base_url() inside a Flask request context so
        the fallback to request.url_root works.  We inject a stub portal_database
        to avoid triggering the module-level DB init.
        """
        # Stub out portal_database so portal_dashboard can be imported
        portal_dir = os.path.join(os.path.dirname(__file__), '..', 'portal')
        portal_dir = os.path.realpath(portal_dir)
        if portal_dir not in sys.path:
            sys.path.insert(0, portal_dir)

        # Provide a minimal stub for portal_database
        mock_pdb = types.ModuleType('portal_database')
        mock_pdb.DB_PATH = ':memory:'
        mock_pdb.get_db_connection = lambda: None
        mock_pdb.log_action = lambda *a, **kw: None
        sys.modules['portal_database'] = mock_pdb

        # portal_auth depends on portal_database; stub it too
        mock_auth = types.ModuleType('portal_auth')

        def _login_required(f):
            return f

        mock_auth.login_required = _login_required
        sys.modules['portal_auth'] = mock_auth

        if 'portal_dashboard' in sys.modules:
            del sys.modules['portal_dashboard']

        import portal_dashboard as pdash

        from flask import Flask
        app = Flask(__name__)
        if env_value is not None:
            os.environ['PORTAL_PUBLIC_BASE_URL'] = env_value
        else:
            os.environ.pop('PORTAL_PUBLIC_BASE_URL', None)

        with app.test_request_context('/', environ_base={'SERVER_NAME': 'testserver', 'wsgi.url_scheme': 'https'}):
            result = pdash.get_public_base_url()

        return result

    def tearDown(self):
        os.environ.pop('PORTAL_PUBLIC_BASE_URL', None)

    def test_env_var_takes_priority(self):
        result = self._call_in_request_context('https://portal.example.com')
        self.assertEqual(result, 'https://portal.example.com')

    def test_env_var_trailing_slash_stripped(self):
        result = self._call_in_request_context('https://portal.example.com/')
        self.assertEqual(result, 'https://portal.example.com')

    def test_falls_back_to_request_url_root(self):
        result = self._call_in_request_context(None)
        # Should return something from request context (not empty)
        self.assertTrue(result.startswith('http'), f'Expected http-based URL, got: {result}')


if __name__ == '__main__':
    unittest.main()

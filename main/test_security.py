"""Security checks that cut across the modules: headers, escaping of what people type, sign-in guessing."""
import datetime
import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from garden_journal.models import GardenJournal
from main.models import Profile
from my_ecopatch.models import EcoPatch

SCRIPT = '</script><script>alert(1)</script>'
IMG = '<img src=x onerror=alert(1)>'


class SecurityHeaderTests(TestCase):
    def test_pages_carry_a_content_security_policy_that_closes_the_usual_doors(self):
        csp = self.client.get(reverse('main:home'))['Content-Security-Policy']
        for rule in ("object-src 'none'", "base-uri 'self'", "frame-ancestors 'none'", "default-src 'self'", "connect-src 'self'"):
            self.assertIn(rule, csp)
        self.assertNotIn('*', csp.replace('https:', ''))

    def test_script_sources_are_limited_to_the_hosts_the_pages_use(self):
        csp = self.client.get(reverse('main:home'))['Content-Security-Policy']
        script_rule = next(rule for rule in csp.split('; ') if rule.startswith('script-src'))
        hosts = set(re.findall(r'https://[^\s]+', script_rule))
        self.assertEqual(hosts, {'https://cdn.jsdelivr.net', 'https://unpkg.com', 'https://cdnjs.cloudflare.com'})

    def test_other_browser_protections_are_on(self):
        response = self.client.get(reverse('main:home'))
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('same-origin', response['Referrer-Policy'])
        self.assertIn('camera=()', response['Permissions-Policy'])

    def test_uploaded_files_may_not_run_anything(self):
        response = self.client.get('/media/does-not-exist.png')
        self.assertIn('sandbox', response['Content-Security-Policy'])
        self.assertIn("default-src 'none'", response['Content-Security-Policy'])

    def test_cookies_are_httponly(self):
        from django.conf import settings
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)


class TypedTextIsNeverMarkupTests(TestCase):
    """Whatever a member types can contain markup. It has to arrive in the page as text."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('petak', password='pw12345678')
        self.client.force_login(self.user)

    def test_journal_history_data_cannot_close_its_script_tag(self):
        GardenJournal.objects.create(
            user=self.user, plant_name='Cabai', ecopatch_name='Balkon', date=datetime.date(2026, 10, 1),
            title=SCRIPT, notes=SCRIPT + IMG, plant_height=12,
        )
        html = self.client.get(reverse('garden_journal:plant_history', args=['Cabai'])).content.decode()
        self.assertNotIn(SCRIPT, html)
        self.assertNotIn('</script><script>alert(1)', html)
        # the data is still there, written so that it cannot end the tag
        self.assertIn('\\u003C/script\\u003E', html)

    def test_history_page_escapes_quotes_before_putting_text_into_attributes(self):
        html = self.client.get(reverse('garden_journal:plant_history', args=['Cabai'])).content.decode()
        escape_helper = html[html.index('function escHtml'):][:400]
        for quote in ('&quot;', '&#39;'):
            self.assertIn(quote, escape_helper)

    def test_journal_form_puts_names_into_the_page_as_text(self):
        html = self.client.get(reverse('garden_journal:create')).content.decode()
        self.assertIn('function escapeHtml', html)
        self.assertNotIn("innerHTML = '<span class=\"fw-semibold\">' +", html)

    def test_ecopatch_names_are_escaped_in_the_garden_pages(self):
        patch = EcoPatch.objects.create(owner=self.user, name=IMG, space_type='balcony', city='Depok')
        for url in (reverse('my_ecopatch:list'), reverse('my_ecopatch:detail', args=[patch.pk])):
            html = self.client.get(url).content.decode()
            self.assertNotIn(IMG, html)
            self.assertIn('&lt;img src=x onerror=alert(1)&gt;', html)

    def test_profile_text_is_escaped(self):
        Profile.objects.update_or_create(user=self.user, defaults={'bio': IMG, 'city': 'Depok'})
        html = self.client.get(reverse('main:profile')).content.decode()
        self.assertNotIn(IMG, html)

    def test_contact_links_only_use_digits_and_handle_characters(self):
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.whatsapp = '6281234567890'
        profile.instagram = 'kebun_ku.id'
        self.assertEqual(profile.whatsapp_url, 'https://wa.me/6281234567890')
        self.assertEqual(profile.instagram_url, 'https://instagram.com/kebun_ku.id')


class LoginGuessingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('petak', password='pw12345678')
        self.url = reverse('main:login')

    def tearDown(self):
        cache.clear()

    def wrong(self, username='petak'):
        return self.client.post(self.url, {'username': username, 'password': 'salah-terus'})

    def test_a_few_wrong_passwords_are_just_wrong_passwords(self):
        for _ in range(4):
            self.assertEqual(self.wrong().status_code, 200)

    def test_after_five_wrong_tries_even_the_right_password_waits(self):
        for _ in range(5):
            self.wrong()
        response = self.client.post(self.url, {'username': 'petak', 'password': 'pw12345678'})
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, 'Terlalu banyak percobaan masuk', status_code=429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_the_lock_is_per_username(self):
        for _ in range(5):
            self.wrong()
        get_user_model().objects.create_user('lain', password='pw12345678')
        response = self.client.post(self.url, {'username': 'lain', 'password': 'pw12345678'})
        self.assertEqual(response.status_code, 302)

    def test_a_good_login_clears_the_count(self):
        for _ in range(4):
            self.wrong()
        self.client.post(self.url, {'username': 'petak', 'password': 'pw12345678'})
        self.client.logout()
        for _ in range(4):
            self.assertEqual(self.wrong().status_code, 200)

    def test_next_cannot_send_people_to_another_site(self):
        response = self.client.post(self.url + '?next=https://evil.example/', {'username': 'petak', 'password': 'pw12345678'})
        self.assertRedirects(response, reverse('my_ecopatch:list'), fetch_redirect_response=False)

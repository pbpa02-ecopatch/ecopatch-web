import io
import os
import shutil
import tempfile
import re
import smtplib
from io import StringIO
from unittest import mock
from urllib.parse import parse_qs, urlparse

from allauth.account.middleware import AccountMiddleware
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount, SocialApp
from allauth.socialaccount.providers.google.provider import GoogleProvider
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Profile


class LandingPageTests(TestCase):
    def test_guest_sees_login_and_register_links(self):
        response = self.client.get(reverse('main:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('main:login'))
        self.assertContains(response, reverse('main:register'))
        self.assertNotContains(response, reverse('my_ecopatch:list'))

    def test_signed_in_people_skip_the_landing_page(self):
        user = get_user_model().objects.create_user('petak', password='pw12345678')
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse('main:home')), reverse('my_ecopatch:list'), fetch_redirect_response=False)

    def test_landing_links_to_the_plant_library_when_it_exists(self):
        response = self.client.get(reverse('main:home'))
        self.assertEqual(response.context['plant_library_url'], reverse('plant_library:plant_list'))
        self.assertContains(response, 'data-plant-library-url="/plants/"')

    def test_landing_falls_back_to_its_own_anchor_without_the_plant_library_route(self):
        from django.urls import NoReverseMatch
        with mock.patch('main.views.reverse', side_effect=NoReverseMatch()):
            response = self.client.get(reverse('main:home'))
        self.assertEqual(response.context['plant_library_url'], '')
        self.assertContains(response, 'data-plant-library-url=""')

    def test_anchors_used_by_the_auth_pages_exist(self):
        response = self.client.get(reverse('main:home'))
        self.assertContains(response, 'id="fitur"')
        self.assertContains(response, 'id="faq"')

    def test_messages_are_shown(self):
        from django.contrib import messages
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory
        from main.views import home

        request = RequestFactory().get('/')
        request.user = AnonymousUser()
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        messages.success(request, 'Sampai jumpa lagi')
        self.assertContains(home(request), 'Sampai jumpa lagi')


FAKE_GOOGLE = {
    'google': {
        'APP': {'client_id': 'test-client-id.apps.googleusercontent.com', 'secret': 'test-secret', 'key': ''},
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
}


@override_settings(GOOGLE_AUTH_ENABLED=False)
class GoogleLoginDisabledTests(TestCase):
    def test_pages_hide_the_google_button(self):
        self.assertNotContains(self.client.get(reverse('main:login')), 'dengan Google')
        self.assertNotContains(self.client.get(reverse('main:register')), 'dengan Google')

    def test_google_urls_send_people_back_to_login(self):
        for url in ('/accounts/google/login/', '/accounts/google/login/callback/'):
            self.assertRedirects(self.client.get(url), reverse('main:login'), fetch_redirect_response=False)

    def test_allauth_own_pages_redirect_to_ours(self):
        self.assertRedirects(self.client.get('/accounts/login/?next=/journal/'), '/login/?next=/journal/', fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/accounts/signup/'), reverse('main:register'), fetch_redirect_response=False)


@override_settings(GOOGLE_AUTH_ENABLED=True, SOCIALACCOUNT_PROVIDERS=FAKE_GOOGLE)
class GoogleLoginEnabledTests(TestCase):
    def test_login_and_register_pages_offer_google(self):
        login = self.client.get(reverse('main:login'))
        self.assertContains(login, 'Masuk dengan Google')
        self.assertContains(login, 'action="/accounts/google/login/?process=login"')
        self.assertContains(self.client.get(reverse('main:register')), 'Daftar dengan Google')

    def test_button_sends_the_browser_to_google_with_our_callback(self):
        response = self.client.post('/accounts/google/login/', {'process': 'login'})
        self.assertEqual(response.status_code, 302)
        parts = urlparse(response['Location'])
        query = parse_qs(parts.query)
        self.assertEqual(parts.netloc, 'accounts.google.com')
        self.assertEqual(query['client_id'], ['test-client-id.apps.googleusercontent.com'])
        self.assertEqual(query['redirect_uri'], ['http://testserver/accounts/google/login/callback/'])
        self.assertIn('state', query)

    def test_a_google_account_gets_an_ecopatch_account_on_first_visit_and_is_reused_after(self):
        def visit(email='budi@example.com', uid='google-uid-123'):
            request = RequestFactory().get('/accounts/google/login/callback/')
            SessionMiddleware(lambda r: None).process_request(request)
            MessageMiddleware(lambda r: None).process_request(request)
            request.user = AnonymousUser()
            out = {}

            def finish_login(req):
                # allauth keeps the current request in a context that AccountMiddleware opens, so run inside it
                provider = GoogleProvider(req, app=SocialApp(provider='google', client_id='x', secret='y'))
                login = provider.sociallogin_from_response(req, {
                    'sub': uid, 'email': email, 'email_verified': True,
                    'given_name': 'Budi', 'family_name': 'Santoso', 'name': 'Budi Santoso',
                })
                out['response'] = complete_social_login(req, login)
                return out['response']

            AccountMiddleware(finish_login)(request)
            return request, out['response']

        request, response = visit()
        user = get_user_model().objects.get(email='budi@example.com')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.user, user)
        self.assertEqual(list(get_messages(request)), [])
        self.assertEqual((user.first_name, user.last_name), ('Budi', 'Santoso'))
        self.assertTrue(user.username)
        self.assertEqual(SocialAccount.objects.filter(user=user, provider='google', uid='google-uid-123').count(), 1)

        request, _ = visit()
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(request.user, user)

    def _google_visit(self, email, uid):
        request = RequestFactory().get('/accounts/google/login/callback/')
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        request.user = AnonymousUser()
        out = {}

        def finish_login(req):
            provider = GoogleProvider(req, app=SocialApp(provider='google', client_id='x', secret='y'))
            login = provider.sociallogin_from_response(req, {'sub': uid, 'email': email, 'email_verified': True, 'name': 'Budi Santoso'})
            try:
                out['response'] = complete_social_login(req, login)
            except ImmediateHttpResponse as stop:
                out['response'] = stop.response
            return out['response']

        AccountMiddleware(finish_login)(request)
        return request, out['response']

    def test_google_signs_in_to_an_existing_user_whose_email_is_verified(self):
        existing = get_user_model().objects.create_user('tesEcopatch', email='budi@example.com', password='pw12345678')
        EmailAddress.objects.create(user=existing, email='budi@example.com', verified=True, primary=True)

        request, response = self._google_visit('budi@example.com', 'google-uid-999')
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('/signup', response['Location'])
        self.assertEqual(request.user, existing)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(SocialAccount.objects.filter(user=existing, provider='google', uid='google-uid-999').count(), 1)

    def test_google_does_not_enter_an_account_whose_email_is_not_verified(self):
        existing = get_user_model().objects.create_user('tesEcopatch', email='budi@example.com', password='pw12345678')

        request, response = self._google_visit('budi@example.com', 'google-uid-999')
        self.assertRedirects(response, reverse('main:login'), fetch_redirect_response=False)
        self.assertFalse(request.user.is_authenticated)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertFalse(SocialAccount.objects.filter(user=existing).exists())
        self.assertIn('belum terverifikasi', ' '.join(str(m) for m in get_messages(request)))


class SiteNameTests(TestCase):
    def test_default_site_is_called_ecopatch(self):
        from django.contrib.sites.models import Site
        self.assertEqual(Site.objects.get(pk=1).name, 'EcoPatch')


class AssetVersionTests(TestCase):
    """{% static_v %} puts a content hash in the URL so a browser never reuses a stale copy."""

    def render(self, path):
        from django.template import Context, Template
        return Template('{% load asset_version %}{% static_v path %}').render(Context({'path': path}))

    def test_url_carries_a_hash_of_the_file(self):
        url = self.render('css/custom.css')
        self.assertRegex(url, r'^/static/css/custom\.css\?v=[0-9a-f]{10}$')
        self.assertEqual(url, self.render('css/custom.css'))

    def test_hash_changes_when_the_file_changes(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        target = os.path.join(folder, 'probe.css')
        with open(target, 'w') as f:
            f.write('a { color: red; }')
        with override_settings(STATICFILES_DIRS=[folder]):
            before = self.render('probe.css')
            with open(target, 'w') as f:
                f.write('a { color: blue; }')
            after = self.render('probe.css')
        self.assertNotEqual(before, after)
        self.assertTrue(before.startswith('/static/probe.css?v='))

    def test_unknown_file_falls_back_to_the_plain_url(self):
        self.assertEqual(self.render('css/does-not-exist.css'), '/static/css/does-not-exist.css')

    def test_pages_link_their_assets_with_a_version(self):
        for name in ('main:home', 'main:login', 'main:register'):
            html = self.client.get(reverse(name)).content.decode()
            self.assertRegex(html, r'\.css\?v=[0-9a-f]{10}', name)
        user = get_user_model().objects.create_user('asset_user', password='pw-12345-xx')
        self.client.force_login(user)
        html = self.client.get(reverse('my_ecopatch:list')).content.decode()
        self.assertRegex(html, r'css/custom\.css\?v=[0-9a-f]{10}')


class SidebarMenuTests(TestCase):
    """The profile row of the sidebar opens a small menu; there is no separate sign-out icon any more."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('menu_user', password='pw-12345-xx')

    def page(self):
        self.client.force_login(self.user)
        return self.client.get(reverse('my_ecopatch:list')).content.decode()

    def test_the_menu_holds_the_profile_link_and_the_sign_out_form(self):
        html = self.page()
        start = html.index('id="sidebar-user-menu"')
        menu = html[start:html.index('class="sidebar-foot"', start)]
        self.assertIn('role="menu" hidden', menu)  # closed until the profile row is clicked
        self.assertIn(f'href="{reverse("main:profile")}"', menu)
        self.assertIn(f'action="{reverse("main:logout")}"', menu)
        self.assertIn('method="post"', menu)
        self.assertIn('csrfmiddlewaretoken', menu)
        self.assertIn('Keluar', menu)

    def test_the_profile_row_is_the_button_that_opens_it(self):
        html = self.page()
        self.assertIn('id="sidebar-user-toggle"', html)
        self.assertIn('aria-controls="sidebar-user-menu"', html)
        self.assertIn('aria-expanded="false"', html)

    def test_the_old_sign_out_icon_is_gone(self):
        self.assertNotIn('sidebar-logout', self.page())

    def test_the_collapse_button_is_at_the_bottom_not_next_to_the_logo(self):
        html = self.page()
        self.assertGreater(html.index('id="sidebar-toggle"'), html.index('id="sidebar-user-toggle"'))
        self.assertLess(html.index('class="sidebar-head"'), html.index('id="sidebar-user-menu"'))
        head = html[html.index('class="sidebar-head"'):html.index('class="navbar-toggler"')]
        self.assertNotIn('sidebar-toggle', head)

    def test_guests_get_no_sidebar_menu(self):
        html = self.client.get(reverse('plant_library:plant_list')).content.decode()
        # the shared script in base.html names these ids; what must be missing is the markup itself
        self.assertNotIn('id="sidebar-user-menu"', html)
        self.assertNotIn('id="sidebar-user-toggle"', html)
        self.assertNotIn('id="sidebar-toggle"', html)


class AfterLoginTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('petak', password='pw12345678')

    def test_login_goes_to_my_ecopatch_by_default(self):
        response = self.client.post(reverse('main:login'), {'username': 'petak', 'password': 'pw12345678'})
        self.assertRedirects(response, reverse('my_ecopatch:list'), fetch_redirect_response=False)

    def test_login_goes_back_to_where_the_person_came_from(self):
        target = reverse('seed_exchange:list')
        response = self.client.post(reverse('main:login'), {'username': 'petak', 'password': 'pw12345678', 'next': target})
        self.assertRedirects(response, target, fetch_redirect_response=False)

    def test_signed_in_people_skip_the_login_and_register_pages(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse('main:login')), reverse('my_ecopatch:list'), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse('main:register')), reverse('my_ecopatch:list'), fetch_redirect_response=False)

    def test_register_hands_the_destination_on_to_login(self):
        target = reverse('seed_exchange:list')
        page = self.client.get(reverse('main:register') + '?next=' + target)
        self.assertContains(page, 'login/?next=')
        response = self.client.post(reverse('main:register') + '?next=' + target, {
            'username': 'baru', 'email': 'baru@example.com', 'password1': 'Sup3r-rahasia-99', 'password2': 'Sup3r-rahasia-99',
        })
        self.assertRedirects(response, reverse('main:login') + '?next=%2Fseed-exchange%2F', fetch_redirect_response=False)

    def test_register_ignores_a_destination_on_another_site(self):
        response = self.client.post(reverse('main:register') + '?next=https://evil.example/', {
            'username': 'baru2', 'email': 'baru2@example.com', 'password1': 'Sup3r-rahasia-99', 'password2': 'Sup3r-rahasia-99',
        })
        self.assertRedirects(response, reverse('main:login'), fetch_redirect_response=False)

    def test_google_button_on_register_carries_the_destination(self):
        with override_settings(GOOGLE_AUTH_ENABLED=True, SOCIALACCOUNT_PROVIDERS=FAKE_GOOGLE):
            page = self.client.get(reverse('main:register') + '?next=/seed-exchange/')
        self.assertContains(page, 'name="next" value="/seed-exchange/"')


class AuthPagesTests(TestCase):
    def test_wrong_password_shows_the_error_and_keeps_the_username(self):
        response = self.client.post(reverse('main:login'), {'username': 'tidak_ada', 'password': 'salah'})
        self.assertContains(response, 'Username atau password salah. Coba lagi.')
        self.assertContains(response, 'data-server="1"')
        self.assertContains(response, 'value="tidak_ada"')

    def test_taken_username_is_reported_in_indonesian(self):
        get_user_model().objects.create_user('petak', password='pw12345678')
        response = self.client.post(reverse('main:register'), {
            'username': 'petak', 'email': 'lain@example.com', 'password1': 'Sup3r-rahasia-99', 'password2': 'Sup3r-rahasia-99',
        })
        self.assertContains(response, 'sudah ada')
        self.assertContains(response, 'aria-invalid="true"')

    def test_weak_password_is_reported_in_indonesian(self):
        response = self.client.post(reverse('main:register'), {'username': 'baru', 'email': 'baru@example.com', 'password1': '12345678', 'password2': '12345678'})
        self.assertContains(response, 'class="err"')
        self.assertNotContains(response, 'This password')

    def test_account_created_message_shows_on_the_login_page(self):
        response = self.client.post(reverse('main:register'), {
            'username': 'baru3', 'email': 'baru3@example.com', 'password1': 'Sup3r-rahasia-99', 'password2': 'Sup3r-rahasia-99',
        }, follow=True)
        self.assertContains(response, 'Akun berhasil dibuat. Silakan masuk.')
        self.assertTrue(get_user_model().objects.filter(username='baru3').exists())


class RegisterEmailTests(TestCase):
    def post(self, **extra):
        data = {'username': 'baru', 'email': 'baru@example.com', 'password1': 'Sup3r-rahasia-99', 'password2': 'Sup3r-rahasia-99'}
        data.update(extra)
        return self.client.post(reverse('main:register'), data)

    def test_the_email_is_saved(self):
        self.post()
        self.assertEqual(get_user_model().objects.get(username='baru').email, 'baru@example.com')

    def test_an_email_is_required(self):
        response = self.post(email='')
        self.assertContains(response, 'Isi email kamu dulu ya.')
        self.assertFalse(get_user_model().objects.filter(username='baru').exists())

    def test_the_same_email_cannot_register_twice(self):
        get_user_model().objects.create_user('lama', email='Baru@Example.com', password='pw12345678')
        self.assertContains(self.post(), 'Email ini sudah terdaftar')
        self.assertFalse(get_user_model().objects.filter(username='baru').exists())

    def test_register_page_asks_for_the_email(self):
        self.assertContains(self.client.get(reverse('main:register')), 'name="email"')


class ForgotPasswordTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('petak', email='petak@example.com', password='lama-12345678')

    def request_link(self, email='petak@example.com'):
        response = self.client.post(reverse('main:password_reset'), {'email': email})
        self.assertRedirects(response, reverse('main:password_reset_done'))
        return response

    def link_from_email(self):
        match = re.search(r'https?://\S+', mail.outbox[0].body)
        return match.group(0)

    def test_login_page_links_to_forgot_password(self):
        self.assertContains(self.client.get(reverse('main:login')), reverse('main:password_reset'))

    def test_an_email_with_a_link_is_sent_in_indonesian_using_this_host(self):
        self.request_link()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['petak@example.com'])
        self.assertEqual(message.subject, 'Atur ulang password EcoPatch kamu')
        self.assertIn('Halo petak', message.body)
        self.assertIn('http://testserver/lupa-password/', message.body)
        self.assertNotIn('example.com/lupa', message.body)

    def test_an_unknown_email_looks_exactly_the_same_and_sends_nothing(self):
        self.request_link('tidak-ada@example.com')
        self.assertEqual(len(mail.outbox), 0)

    def test_an_account_without_a_password_can_get_one_through_the_link(self):
        google_user = get_user_model().objects.create_user('lewat_google', email='g@example.com')
        google_user.set_unusable_password()
        google_user.save()
        self.request_link('g@example.com')
        self.assertEqual(len(mail.outbox), 1)
        link = self.link_from_email().replace('http://testserver', '')
        form_url = self.client.get(link, follow=True).redirect_chain[-1][0]
        self.client.post(form_url, {'new_password1': 'Baru-9876-rahasia', 'new_password2': 'Baru-9876-rahasia'})
        self.assertTrue(self.client.login(username='lewat_google', password='Baru-9876-rahasia'))
        self.assertTrue(EmailAddress.objects.filter(user=google_user, verified=True).exists())

    def test_an_inactive_account_gets_no_email(self):
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
        self.request_link()
        self.assertEqual(len(mail.outbox), 0)

    def test_the_whole_flow_changes_the_password_and_verifies_the_email(self):
        self.request_link()
        link = self.link_from_email().replace('http://testserver', '')
        page = self.client.get(link, follow=True)
        self.assertContains(page, 'Buat password baru')
        form_url = page.redirect_chain[-1][0]
        done = self.client.post(form_url, {'new_password1': 'Baru-9876-rahasia', 'new_password2': 'Baru-9876-rahasia'})
        self.assertRedirects(done, reverse('main:password_reset_complete'))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Baru-9876-rahasia'))
        self.assertTrue(EmailAddress.objects.filter(user=self.user, email='petak@example.com', verified=True).exists())
        self.assertTrue(self.client.login(username='petak', password='Baru-9876-rahasia'))

    def test_a_link_works_only_once(self):
        self.request_link()
        link = self.link_from_email().replace('http://testserver', '')
        page = self.client.get(link, follow=True)
        form_url = page.redirect_chain[-1][0]
        self.client.post(form_url, {'new_password1': 'Baru-9876-rahasia', 'new_password2': 'Baru-9876-rahasia'})
        again = self.client.get(link, follow=True)
        self.assertContains(again, 'Tautan tidak berlaku')

    def test_a_weak_new_password_is_refused_in_indonesian(self):
        self.request_link()
        link = self.link_from_email().replace('http://testserver', '')
        form_url = self.client.get(link, follow=True).redirect_chain[-1][0]
        response = self.client.post(form_url, {'new_password1': '12345678', 'new_password2': '12345678'})
        self.assertContains(response, 'class="err"')
        self.assertNotContains(response, 'This password')

    def test_a_made_up_link_is_refused(self):
        self.assertContains(self.client.get('/lupa-password/abc/def/', follow=True), 'Tautan tidak berlaku')

    def test_after_the_reset_google_may_enter_that_account(self):
        self.request_link()
        link = self.link_from_email().replace('http://testserver', '')
        form_url = self.client.get(link, follow=True).redirect_chain[-1][0]
        self.client.post(form_url, {'new_password1': 'Baru-9876-rahasia', 'new_password2': 'Baru-9876-rahasia'})
        self.assertTrue(EmailAddress.objects.filter(user=self.user, verified=True).exists())


class EmailSendingTests(TestCase):
    def test_the_test_command_sends_one_email(self):
        out = StringIO()
        call_command('send_test_email', 'kamu@example.com', stdout=out)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['kamu@example.com'])
        self.assertIn('Terkirim ke kamu@example.com', out.getvalue())

    def test_the_test_command_explains_a_refused_login(self):
        with mock.patch('main.management.commands.send_test_email.send_mail', side_effect=smtplib.SMTPAuthenticationError(535, b'bad')):
            with self.assertRaisesMessage(CommandError, 'app password'):
                call_command('send_test_email', 'kamu@example.com', stdout=StringIO())

    def test_the_test_command_explains_a_login_that_closes_the_connection(self):
        with mock.patch('main.management.commands.send_test_email.send_mail', side_effect=smtplib.SMTPServerDisconnected('Connection unexpectedly closed')):
            with self.assertRaisesMessage(CommandError, 'app password'):
                call_command('send_test_email', 'kamu@example.com', stdout=StringIO())

    def test_the_test_command_explains_a_blocked_port(self):
        with mock.patch('main.management.commands.send_test_email.send_mail', side_effect=TimeoutError()):
            with self.assertRaisesMessage(CommandError, 'port 465'):
                call_command('send_test_email', 'kamu@example.com', stdout=StringIO())

    def test_a_broken_mail_server_does_not_break_forgot_password(self):
        get_user_model().objects.create_user('petak', email='petak@example.com', password='lama-12345678')
        with mock.patch('django.core.mail.message.EmailMultiAlternatives.send', side_effect=smtplib.SMTPServerDisconnected('down')):
            with self.assertLogs('django.contrib.auth', level='ERROR'):  # Django logs the failure and carries on
                response = self.client.post(reverse('main:password_reset'), {'email': 'petak@example.com'})
        self.assertRedirects(response, reverse('main:password_reset_done'))


TEMP_MEDIA = tempfile.mkdtemp()


def make_image(name='foto.png', size=(20, 20)):
    buf = io.BytesIO()
    Image.new('RGB', size, 'green').save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ProfileViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = get_user_model().objects.create_user('tanam', 'lama@example.com', 'pass12345')
        self.url = reverse('main:profile')
        self.client.force_login(self.user)

    def post_profile(self, **overrides):
        data = {
            'action': 'profile',
            'first_name': 'Siti',
            'last_name': 'Aminah',
            'email': 'lama@example.com',
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    # ---- contact (WhatsApp, Instagram): optional and private
    def post_contact(self, **data):
        return self.client.post(self.url, {'action': 'contact', **data})

    def test_contact_is_saved_in_one_tidy_format(self):
        response = self.post_contact(whatsapp='+62 812-3456-7890', instagram='@Kebunku.Id')
        self.assertRedirects(response, self.url)
        profile = Profile.objects.get(user=self.user)
        self.assertEqual((profile.whatsapp, profile.instagram), ('6281234567890', 'kebunku.id'))
        self.assertEqual(profile.whatsapp_display, '+62 812-3456-7890')
        self.assertEqual(profile.whatsapp_url, 'https://wa.me/6281234567890')
        self.assertEqual(profile.instagram_url, 'https://instagram.com/kebunku.id')

    def test_whatsapp_accepts_the_usual_ways_of_writing_a_number(self):
        for typed in ('081234567890', '0812 3456 7890', '+6281234567890', '6281234567890', '(0812) 3456-7890', '81234567890'):
            self.post_contact(whatsapp=typed)
            self.assertEqual(Profile.objects.get(user=self.user).whatsapp, '6281234567890', typed)

    def test_a_number_from_another_country_is_kept(self):
        self.post_contact(whatsapp='+60 12-345 6789')
        self.assertEqual(Profile.objects.get(user=self.user).whatsapp, '60123456789')

    def test_bad_whatsapp_numbers_are_refused(self):
        for typed in ('abc123', '0812', '0712 3456 7890', '0812 3456 7890 1234 5678', '12'):
            response = self.post_contact(whatsapp=typed)
            self.assertEqual(response.status_code, 200, typed)
            self.assertTrue(response.context['contact_form'].errors['whatsapp'], typed)
        self.assertEqual(Profile.objects.get(user=self.user).whatsapp, '')

    def test_instagram_takes_a_username_a_handle_or_a_pasted_link(self):
        for typed in ('kebunku', '@kebunku', 'https://www.instagram.com/kebunku/', 'instagram.com/kebunku?igsh=abc'):
            self.post_contact(instagram=typed)
            self.assertEqual(Profile.objects.get(user=self.user).instagram, 'kebunku', typed)

    def test_bad_instagram_usernames_are_refused(self):
        for typed in ('kebun ku', 'kebun!', 'a' * 31, 'kebunku.', 'ke..bun', 'https://example.com/kebunku'):
            response = self.post_contact(instagram=typed)
            self.assertTrue(response.context['contact_form'].errors['instagram'], typed)

    def test_both_fields_are_optional_and_can_be_cleared(self):
        self.post_contact(whatsapp='0812 3456 7890', instagram='kebunku')
        response = self.post_contact(whatsapp='', instagram='')
        self.assertRedirects(response, self.url)
        profile = Profile.objects.get(user=self.user)
        self.assertEqual((profile.whatsapp, profile.instagram, profile.contact_text()), ('', '', ''))

    def test_the_contact_shows_on_the_owners_profile_with_links(self):
        self.post_contact(whatsapp='0812 3456 7890', instagram='kebunku')
        response = self.client.get(self.url)
        self.assertContains(response, 'href="https://wa.me/6281234567890"')
        self.assertContains(response, '+62 812-3456-7890')
        self.assertContains(response, 'href="https://instagram.com/kebunku"')
        self.assertContains(response, 'rel="noopener noreferrer"')
        self.assertContains(response, 'hanya kamu yang melihatnya')

    def test_the_saved_number_is_shown_in_the_field_in_its_readable_form_and_can_be_saved_again(self):
        self.post_contact(whatsapp='081234567890')
        response = self.client.get(self.url)
        self.assertEqual(response.context['contact_form']['whatsapp'].value(), '+62 812-3456-7890')
        self.post_contact(whatsapp='+62 812-3456-7890')  # what the field now holds goes back in unchanged
        self.assertEqual(Profile.objects.get(user=self.user).whatsapp, '6281234567890')

    def test_without_contact_the_card_has_no_contact_chips(self):
        self.assertNotContains(self.client.get(self.url), 'class="profile-contacts"')

    def test_one_users_contact_never_reaches_another_users_pages(self):
        self.post_contact(whatsapp='0812 3456 7890', instagram='sawah_rahasia')
        other = get_user_model().objects.create_user('lain', 'lain@example.com', 'pass12345')
        self.client.force_login(other)
        for name in ('main:profile', 'seed_exchange:list', 'seed_exchange:create'):
            body = self.client.get(reverse(name)).content.decode()
            self.assertNotIn('6281234567890', body, name)
            self.assertNotIn('sawah_rahasia', body, name)

    def test_contact_text_joins_what_is_filled_in(self):
        profile = Profile(whatsapp='6281234567890', instagram='kebunku')
        self.assertEqual(profile.contact_text(), 'WhatsApp +62 812-3456-7890 / Instagram @kebunku')
        self.assertEqual(Profile(instagram='kebunku').contact_text(), 'Instagram @kebunku')
        self.assertEqual(Profile().contact_text(), '')


    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('main:login')}?next={self.url}")

    def test_get_creates_profile_and_prefills(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Profile.objects.filter(user=self.user).exists())
        self.assertContains(response, 'name="email" value="lama@example.com"')
        self.assertContains(response, 'lama@example.com')

    def test_card_shows_stats_and_logout_button(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'class="profile-stats"')
        self.assertContains(response, 'class="profile-logout"')
        self.assertEqual(response.context['stats'], {'patches': 0, 'journals': 0, 'listings': 0})

    def test_member_since_uses_indonesian_month(self):
        self.user.date_joined = self.user.date_joined.replace(year=2026, month=10, day=5)
        self.user.save()
        response = self.client.get(self.url)
        self.assertContains(response, 'Anggota sejak Oktober 2026')

    def test_logged_in_pages_use_the_sidebar_layout(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'has-sidebar')
        self.assertContains(response, 'site-navbar--side')
        self.assertContains(response, 'class="sidebar-user')

    def test_sidebar_user_row_has_tooltip(self):
        self.assertContains(self.client.get(self.url), 'title="tanam - lama@example.com"')

    def test_sidebar_has_collapse_toggle(self):
        self.assertContains(self.client.get(self.url), 'id="sidebar-toggle"')

    def test_guest_pages_keep_the_top_navbar(self):
        self.client.logout()
        response = self.client.get(reverse('main:home'))
        self.assertNotContains(response, 'has-sidebar')
        self.assertNotContains(response, 'site-navbar site-navbar--side')  # kelas pada <nav>, bukan selector JS
        self.assertNotContains(response, 'id="sidebar-toggle"')

    def test_each_section_has_its_own_form(self):
        response = self.client.get(self.url)
        for action in ('profile', 'bio'):
            self.assertContains(response, f'name="action" value="{action}"')

    def test_profile_updates_names_and_email(self):
        response = self.post_profile(email='baru@example.com')
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), 'Siti Aminah')
        self.assertEqual(self.user.email, 'baru@example.com')

    def test_bio_updates_only_bio(self):
        response = self.client.post(self.url, {'action': 'bio', 'bio': 'Suka cabai di balkon.'})
        self.assertRedirects(response, self.url)
        self.assertEqual(Profile.objects.get(user=self.user).bio, 'Suka cabai di balkon.')
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'tanam')

    def test_city_saved_with_bio_and_shown_on_card(self):
        response = self.client.post(self.url, {'action': 'bio', 'city': 'Bandung', 'bio': ''})
        self.assertRedirects(response, self.url)
        self.assertEqual(Profile.objects.get(user=self.user).city, 'Bandung')
        self.assertContains(self.client.get(self.url), 'class="profile-city">Bandung')

    def test_city_outside_supported_list_rejected(self):
        response = self.client.post(self.url, {'action': 'bio', 'city': 'Atlantis', 'bio': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Profile.objects.get(user=self.user).city, '')

    def test_city_is_optional(self):
        response = self.client.post(self.url, {'action': 'bio', 'city': '', 'bio': 'Halo'})
        self.assertRedirects(response, self.url)

    def test_remove_button_only_when_avatar_exists(self):
        self.assertContains(self.client.get(self.url), 'id="avatar-remove-btn" aria-label="Hapus foto profil" hidden')
        self.post_profile(avatar=make_image())
        self.assertNotContains(self.client.get(self.url), 'aria-label="Hapus foto profil" hidden')

    def test_saving_info_keeps_bio_and_avatar(self):
        self.client.post(self.url, {'action': 'bio', 'bio': 'Tetap ada.'})
        self.post_profile(avatar=make_image())
        self.post_profile()
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.bio, 'Tetap ada.')
        self.assertTrue(profile.avatar)

    def test_upload_avatar(self):
        response = self.post_profile(avatar=make_image())
        self.assertRedirects(response, self.url)
        self.assertTrue(Profile.objects.get(user=self.user).avatar.name.startswith('avatars/'))

    def test_non_image_avatar_rejected(self):
        fake = SimpleUploadedFile('x.png', b'bukan gambar', content_type='image/png')
        response = self.post_profile(avatar=fake)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Profile.objects.get(user=self.user).avatar)

    def test_oversized_avatar_rejected(self):
        buf = io.BytesIO()
        Image.new('RGB', (20, 20), 'green').save(buf, format='PNG')
        # Data tambahan setelah chunk IEND diabaikan Pillow, jadi tetap gambar valid tapi > 2 MB
        big = SimpleUploadedFile('besar.png', buf.getvalue() + b'0' * (3 * 1024 * 1024), content_type='image/png')
        response = self.post_profile(avatar=big)
        self.assertContains(response, 'maksimal 2 MB')

    def test_remove_avatar(self):
        self.post_profile(avatar=make_image())
        response = self.post_profile(remove_avatar='on')
        self.assertRedirects(response, self.url)
        self.assertFalse(Profile.objects.get(user=self.user).avatar)

    def test_username_cannot_be_changed(self):
        response = self.post_profile(username='petani')
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'tanam')

    def test_username_not_in_edit_form(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, 'name="username"')
        self.assertNotContains(response, 'username-readonly')
        self.assertContains(response, '@tanam')  # tetap terlihat di card profil

    def test_post_without_action_changes_nothing(self):
        response = self.client.post(self.url, {'username': 'diam-diam', 'bio': 'x'})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'tanam')
        self.assertEqual(Profile.objects.get(user=self.user).bio, '')


class ChangePasswordTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('tanam', 'a@example.com', 'lama-12345')
        self.client.force_login(self.user)
        self.url = reverse('main:profile')

    def post_password(self, **overrides):
        data = {
            'action': 'password',
            'old_password': 'lama-12345',
            'new_password1': 'baru-Sangat-Aman-987',
            'new_password2': 'baru-Sangat-Aman-987',
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_change_password_keeps_user_logged_in(self):
        response = self.post_password()
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('baru-Sangat-Aman-987'))
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_wrong_current_password_rejected(self):
        response = self.post_password(old_password='salah')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('lama-12345'))

    def test_mismatched_confirmation_rejected(self):
        response = self.post_password(new_password2='beda-12345-xyz')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('lama-12345'))

    def test_weak_password_rejected(self):
        response = self.post_password(new_password1='12345678', new_password2='12345678')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('lama-12345'))

    def test_password_form_is_inside_modal(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'id="password-modal"')
        self.assertContains(response, 'data-bs-target="#password-modal"')

    def test_modal_reopens_on_error(self):
        errored = self.post_password(old_password='salah')
        self.assertContains(errored, "getOrCreateInstance(document.getElementById('password-modal')).show()")
        clean = self.client.get(self.url)
        self.assertNotContains(clean, "getOrCreateInstance(document.getElementById('password-modal')).show()")

    def test_password_post_does_not_touch_profile(self):
        self.post_password()
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'tanam')

    def test_settings_page_is_gone(self):
        self.assertEqual(self.client.get('/settings/').status_code, 404)

    def test_navbar_has_no_settings_item(self):
        self.assertNotContains(self.client.get(self.url), 'Pengaturan')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class DeleteAccountTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('tanam', 'a@example.com', 'lama-12345')
        self.client.force_login(self.user)
        self.url = reverse('main:profile')

    def test_delete_with_correct_password(self):
        response = self.client.post(self.url, {'action': 'delete', 'password': 'lama-12345'})
        self.assertRedirects(response, reverse('main:home'))
        self.assertFalse(get_user_model().objects.filter(username='tanam').exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_wrong_password_keeps_account(self):
        response = self.client.post(self.url, {'action': 'delete', 'password': 'salah'})
        self.assertContains(response, 'Password salah.')
        self.assertTrue(get_user_model().objects.filter(username='tanam').exists())
        self.assertContains(response, "getElementById('delete-modal')")

    def test_missing_password_keeps_account(self):
        self.client.post(self.url, {'action': 'delete'})
        self.assertTrue(get_user_model().objects.filter(username='tanam').exists())

    def test_avatar_file_removed(self):
        profile = Profile.objects.create(user=self.user, avatar=make_image())
        path = profile.avatar.path
        self.assertTrue(os.path.exists(path))
        self.client.post(self.url, {'action': 'delete', 'password': 'lama-12345'})
        self.assertFalse(os.path.exists(path))


class NotFoundPageTests(TestCase):
    """Every URL that does not exist gets the EcoPatch 404 page (Django shows it whenever DEBUG is off)."""

    def assertIsOurNotFoundPage(self, response):
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Halaman yang kamu cari tidak ketemu.', status_code=404)
        self.assertContains(response, f'href="{reverse("main:home")}"', status_code=404)
        self.assertContains(response, 'noindex', status_code=404)

    def test_an_unknown_url_shows_the_page_to_a_guest(self):
        self.assertIsOurNotFoundPage(self.client.get('/tidak-ada-halaman-ini/'))

    def test_an_unknown_url_shows_the_page_to_a_logged_in_user(self):
        self.client.force_login(get_user_model().objects.create_user('tanam', 't@example.com', 'pass12345'))
        self.assertIsOurNotFoundPage(self.client.get('/smart-care/tidak-ada/'))

    def test_a_missing_object_shows_it_too(self):
        self.client.force_login(get_user_model().objects.create_user('tanam', 't@example.com', 'pass12345'))
        self.assertIsOurNotFoundPage(self.client.get(reverse('plant_library:plant_detail', args=[99999])))

    def test_the_page_is_self_contained(self):
        body = self.client.get('/tidak-ada/').content.decode()
        self.assertNotIn('site-navbar', body)  # it does not extend base.html
        self.assertEqual(body.count('<!doctype html>'), 1)
        self.assertNotIn('{%', body)
        self.assertNotIn('{{', body)

    def test_the_game_still_has_its_five_pieces(self):
        body = self.client.get('/tidak-ada/').content.decode()
        self.assertEqual(body.count('class="shard"'), 5)
        self.assertEqual(body.count('class="hole"'), 5)


class MediaServingTests(TestCase):
    """Uploads must be reachable with DEBUG off too (the test runner always runs with DEBUG off)."""

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        os.makedirs(os.path.join(self.media, 'avatars'))
        with open(os.path.join(self.media, 'avatars', 'foto.txt'), 'w') as handle:
            handle.write('isi foto')
        self.secret = os.path.join(os.path.dirname(self.media), 'rahasia-di-luar-media.txt')
        with open(self.secret, 'w') as handle:
            handle.write('jangan bocor')
        self.addCleanup(lambda: os.path.exists(self.secret) and os.remove(self.secret))

    def test_an_uploaded_file_is_served(self):
        with override_settings(MEDIA_ROOT=self.media, DEBUG=False):
            response = self.client.get('/media/avatars/foto.txt')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'isi foto')

    def test_a_missing_file_is_a_404(self):
        with override_settings(MEDIA_ROOT=self.media, DEBUG=False):
            self.assertEqual(self.client.get('/media/avatars/tidak-ada.png').status_code, 404)

    def test_a_path_that_climbs_out_of_media_is_refused(self):
        with override_settings(MEDIA_ROOT=self.media, DEBUG=False):
            for path in ('/media/../rahasia-di-luar-media.txt', '/media/avatars/../../rahasia-di-luar-media.txt',
                         '/media/%2e%2e/rahasia-di-luar-media.txt'):
                response = self.client.get(path)
                self.assertIn(response.status_code, (400, 404), path)  # refused either way, never the file
                self.assertNotIn(b'jangan bocor', response.content)

    def test_the_avatar_url_of_a_profile_points_into_media(self):
        user = get_user_model().objects.create_user('foto', 'f@example.com', 'pass12345')
        with override_settings(MEDIA_ROOT=self.media, DEBUG=False):
            profile = Profile.objects.create(user=user)
            profile.avatar.name = 'avatars/foto.txt'
            profile.save()
            self.assertTrue(profile.avatar.url.startswith('/media/'))
            self.assertEqual(self.client.get(profile.avatar.url).status_code, 200)

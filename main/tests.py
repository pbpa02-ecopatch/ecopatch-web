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
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse


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

    def test_plant_library_url_is_blank_until_that_route_exists(self):
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

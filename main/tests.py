from urllib.parse import parse_qs, urlparse

from allauth.account.middleware import AccountMiddleware
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount, SocialApp
from allauth.socialaccount.providers.google.provider import GoogleProvider
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
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

    def test_google_login_with_an_email_that_already_has_a_user_signs_in_to_that_user(self):
        existing = get_user_model().objects.create_user('tesEcopatch', email='budi@example.com', password='pw12345678')

        def visit():
            request = RequestFactory().get('/accounts/google/login/callback/')
            SessionMiddleware(lambda r: None).process_request(request)
            MessageMiddleware(lambda r: None).process_request(request)
            request.user = AnonymousUser()
            out = {}

            def finish_login(req):
                provider = GoogleProvider(req, app=SocialApp(provider='google', client_id='x', secret='y'))
                login = provider.sociallogin_from_response(req, {
                    'sub': 'google-uid-999', 'email': 'budi@example.com', 'email_verified': True, 'name': 'Budi Santoso',
                })
                out['response'] = complete_social_login(req, login)
                return out['response']

            AccountMiddleware(finish_login)(request)
            return request, out['response']

        request, response = visit()
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('/signup', response['Location'])
        self.assertEqual(request.user, existing)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(SocialAccount.objects.filter(user=existing, provider='google', uid='google-uid-999').count(), 1)


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
            'username': 'baru', 'password1': 'Sup3r-rahasia-99', 'password2': 'Sup3r-rahasia-99',
        })
        self.assertRedirects(response, reverse('main:login') + '?next=%2Fseed-exchange%2F', fetch_redirect_response=False)

    def test_register_ignores_a_destination_on_another_site(self):
        response = self.client.post(reverse('main:register') + '?next=https://evil.example/', {
            'username': 'baru2', 'password1': 'Sup3r-rahasia-99', 'password2': 'Sup3r-rahasia-99',
        })
        self.assertRedirects(response, reverse('main:login'), fetch_redirect_response=False)

    def test_google_button_on_register_carries_the_destination(self):
        with override_settings(GOOGLE_AUTH_ENABLED=True, SOCIALACCOUNT_PROVIDERS=FAKE_GOOGLE):
            page = self.client.get(reverse('main:register') + '?next=/seed-exchange/')
        self.assertContains(page, 'name="next" value="/seed-exchange/"')

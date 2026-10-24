from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.urls import reverse


class LandingPageTests(TestCase):
    def test_guest_sees_login_and_register_links(self):
        response = self.client.get(reverse('main:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('main:login'))
        self.assertContains(response, reverse('main:register'))
        self.assertNotContains(response, reverse('my_ecopatch:list'))

    def test_logged_in_user_is_sent_to_my_ecopatch_instead_of_register(self):
        user = get_user_model().objects.create_user('petak', password='pw12345678')
        self.client.force_login(user)
        response = self.client.get(reverse('main:home'))
        self.assertContains(response, reverse('my_ecopatch:list'))
        self.assertNotContains(response, reverse('main:register'))

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

"""The EcoPatch logo is one file (static/img/logo.svg) used by every page that shows a mark or a tab icon."""
import xml.dom.minidom

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class LogoTests(TestCase):
    def test_the_logo_file_is_a_valid_svg(self):
        path = finders.find('img/logo.svg')
        self.assertTrue(path)
        document = xml.dom.minidom.parse(path)
        self.assertEqual(document.documentElement.tagName, 'svg')
        self.assertEqual(document.documentElement.getAttribute('viewBox'), '0 0 300 300')

    def test_public_pages_show_the_logo_and_use_it_as_the_tab_icon(self):
        for name in ('main:home', 'main:login', 'main:register'):
            with self.subTest(page=name):
                html = self.client.get(reverse(name)).content.decode()
                self.assertIn('img/logo.svg', html)
                self.assertIn('rel="icon" type="image/svg+xml"', html)

    def test_the_404_page_shows_the_logo(self):
        html = self.client.get('/tidak-ada-halaman-ini/').content.decode()
        self.assertIn('img/logo.svg', html)
        self.assertIn('rel="icon"', html)

    def test_the_sidebar_shows_the_logo_once_signed_in(self):
        user = get_user_model().objects.create_user('petak', password='pw12345678')
        self.client.force_login(user)
        html = self.client.get(reverse('my_ecopatch:list')).content.decode()
        self.assertIn('class="brand-sprout" src="/static/img/logo.svg"', html)
        self.assertIn('rel="icon" type="image/svg+xml"', html)

    def test_the_old_drawn_marks_are_gone(self):
        user = get_user_model().objects.create_user('petak', password='pw12345678')
        self.client.force_login(user)
        html = self.client.get(reverse('my_ecopatch:list')).content.decode()
        self.assertNotIn('<svg class="brand-sprout"', html)
        landing = self.client.logout() or self.client.get(reverse('main:home')).content.decode()
        self.assertNotIn('<svg class="mark"', landing)

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(MAINTENANCE_MODE=True)
class MaintenanceModeOnTests(TestCase):
    """With the switch on, visitors get the "being prepared" page and staff can still work."""

    def assertMaintenancePage(self, response):
        self.assertEqual(response.status_code, 503)
        self.assertTemplateUsed(response, 'maintenance.html')
        self.assertContains(response, 'EcoPatch lagi disiapkan', status_code=503)
        self.assertEqual(response['Retry-After'], '3600')

    def test_a_guest_sees_the_page_on_any_url(self):
        for url in ('/', '/login/', '/plants/', '/smart-care/', '/halaman-ngawur/'):
            self.assertMaintenancePage(self.client.get(url))

    def test_forms_cannot_be_posted_either(self):
        self.assertMaintenancePage(self.client.post(reverse('main:login'), {'username': 'a', 'password': 'b'}))

    def test_a_logged_in_regular_user_sees_it_too(self):
        self.client.force_login(get_user_model().objects.create_user('biasa', 'b@example.com', 'pass12345'))
        self.assertMaintenancePage(self.client.get(reverse('my_ecopatch:list')))

    def test_the_admin_login_stays_open_so_staff_can_get_in(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)

    def test_a_staff_member_sees_the_site_as_usual(self):
        self.client.force_login(get_user_model().objects.create_user('staf', 's@example.com', 'pass12345', is_staff=True))
        response = self.client.get(reverse('my_ecopatch:list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateNotUsed(response, 'maintenance.html')
        self.assertEqual(self.client.get('/halaman-ngawur/').status_code, 404)  # the normal 404, not the page

    def test_the_page_is_self_contained(self):
        body = self.client.get('/').content.decode()
        self.assertNotIn('site-navbar', body)
        self.assertIn('noindex', body)
        self.assertEqual(body.count('data-k="happy"'), 1)
        self.assertNotIn('data-k="cheer"', body)


class MaintenanceModeOffTests(TestCase):
    def test_off_by_default_and_the_site_works(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get(reverse('main:login')).status_code, 200)

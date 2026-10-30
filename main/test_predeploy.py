from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from main.forms import UserForm


class AccountRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('audit', email='audit@example.com')
        get_user_model().objects.create_user('other', email='other@example.com')

    def setUp(self):
        self.client.force_login(self.user)

    def test_get_cannot_log_a_user_out(self):
        response = self.client.get(reverse('main:logout'))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_post_logs_a_user_out(self):
        self.assertRedirects(self.client.post(reverse('main:logout')), reverse('main:home'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_profile_cannot_take_another_accounts_email(self):
        form = UserForm({'first_name': '', 'last_name': '', 'email': 'OTHER@example.com'}, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_profile_keeps_its_own_email(self):
        form = UserForm({'first_name': '', 'last_name': '', 'email': 'audit@example.com'}, instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)

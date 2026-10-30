from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db.models.query import QuerySet
from django.test import TestCase
from django.urls import reverse
from .models import SeedExchange


class BookingRaceGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner=get_user_model().objects.create_user('owner')
        cls.member=get_user_model().objects.create_user('member')

    def listing(self,status,reserved=False):
        return SeedExchange.objects.create(user=self.owner,title='Bibit',item_type='seed',city='Depok',
            contact='test',transaction_type='giveaway',status=status,reserved_by=self.member if reserved else None)

    def test_get_booking_actions_never_mutate_the_listing(self):
        for action,status,reserved,user in [
            ('accept','requested',True,self.owner),('complete','reserved',True,self.owner),
            ('reopen','reserved',True,self.owner),('cancel_reserve','requested',True,self.member)]:
            with self.subTest(action=action):
                item=self.listing(status,reserved)
                self.client.force_login(user)
                response=self.client.get(reverse('seed_exchange:'+action,args=[item.pk]))
                self.assertEqual(response.status_code,302)
                item.refresh_from_db()
                self.assertEqual(item.status,status)

    def test_stale_conditional_updates_are_reported_without_overwriting_a_booking(self):
        for action,status,reserved,user in [
            ('accept','requested',True,self.owner),('complete','reserved',True,self.owner),
            ('reopen','reserved',True,self.owner),('cancel_reserve','requested',True,self.member)]:
            with self.subTest(action=action):
                item=self.listing(status,reserved)
                self.client.force_login(user)
                with patch.object(QuerySet,'update',return_value=0):
                    response=self.client.post(reverse('seed_exchange:'+action,args=[item.pk]))
                self.assertEqual(response.status_code,400)
                item.refresh_from_db()
                self.assertEqual(item.status,status)

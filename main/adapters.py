from allauth.core.exceptions import ImmediateHttpResponse
from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Signs a Google account in to an existing EcoPatch user only when that user's email is verified.

    EcoPatch users type their own email when they register, so an unverified email must never be enough to
    reach an account: someone could register with another person's address and wait for them to use Google.
    An email counts as verified once its owner has used it (a completed password reset, or a Google sign-up).
    """

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            return
        email = next((a.email for a in sociallogin.email_addresses if a.verified), None)
        if not email:
            return
        user = get_user_model().objects.filter(email__iexact=email).first()
        if user is None:
            return  # a new person: allauth creates the account
        if EmailAddress.objects.filter(user=user, email__iexact=email, verified=True).exists():
            sociallogin.connect(request, user)
            return
        messages.error(
            request,
            'Email Google ini sudah dipakai sebuah akun EcoPatch yang emailnya belum terverifikasi. '
            'Masuk dengan username dan password, atau pakai Lupa password untuk memverifikasi emailnya.',
        )
        raise ImmediateHttpResponse(redirect('main:login'))

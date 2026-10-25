import smtplib
import socket

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Send one test email with the current email settings, so "Lupa password" can be checked before relying on it.'

    def add_arguments(self, parser):
        parser.add_argument('to', help='address that should receive the test email')

    def handle(self, *args, to, **options):
        backend = settings.EMAIL_BACKEND.rsplit('.', 2)[-2]
        self.stdout.write(f'Backend: {backend}')
        if backend == 'console':
            self.stdout.write(self.style.WARNING(
                'EMAIL_HOST is empty, so the email is only printed below and nothing is delivered. '
                'Fill EMAIL_HOST, EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env to send for real.'
            ))
        else:
            self.stdout.write(f'Server: {settings.EMAIL_HOST}:{settings.EMAIL_PORT} (user {settings.EMAIL_HOST_USER or "-"})')
        self.stdout.write(f'From: {settings.DEFAULT_FROM_EMAIL}')

        try:
            send_mail(
                'Tes email EcoPatch',
                'Kalau kamu membaca ini, pengaturan email EcoPatch sudah benar dan "Lupa password" akan sampai ke inbox.',
                None, [to],
            )
        except smtplib.SMTPAuthenticationError:
            raise CommandError('Login ke server email ditolak. Untuk Gmail pakai app password (bukan password biasa) dan aktifkan verifikasi 2 langkah.')
        except smtplib.SMTPServerDisconnected:
            # Python reports a refused login (Gmail answers 535 BadCredentials) like this on some versions
            raise CommandError('Server email memutus koneksi saat login. Biasanya alamat atau app password ditolak: pastikan app password dibuat di akun yang sama dengan EMAIL_HOST_USER, ditulis tanpa spasi, dan Verifikasi 2 langkah aktif. Kalau yakin benar, coba port 465 dengan EMAIL_USE_SSL=True.')
        except (socket.timeout, TimeoutError, ConnectionRefusedError, smtplib.SMTPConnectError):
            raise CommandError('Tidak bisa tersambung ke server email. Periksa EMAIL_HOST dan EMAIL_PORT, atau mungkin hosting memblokir port SMTP (coba port 465 dengan EMAIL_USE_SSL=True).')
        except Exception as error:  # noqa: BLE001 - show whatever the mail server said
            raise CommandError(f'Gagal mengirim: {error.__class__.__name__}: {error}')
        if backend != 'console':
            self.stdout.write(self.style.SUCCESS(f'Terkirim ke {to}. Cek inbox (dan folder spam).'))

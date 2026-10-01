from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from urllib.parse import urlencode

from .forms import SeedExchangeForm
from .models import SeedExchange


def _filtered_queryset(request):
    """Queryset dengan filter jenis item / tanaman / kota / transaksi / status."""
    qs = SeedExchange.objects.select_related('user').order_by('-created_at')

    item_type = request.GET.get('item_type', '').strip()
    q = request.GET.get('q', '').strip()
    city = request.GET.get('city', '').strip()
    transaction_type = request.GET.get('transaction_type', '').strip()
    status = request.GET.get('status', '').strip()

    valid_item_types = {c[0] for c in SeedExchange.ItemType.choices}
    valid_transactions = {c[0] for c in SeedExchange.TransactionType.choices}
    valid_statuses = {c[0] for c in SeedExchange.Status.choices}
    valid_cities = {c[0] for c in SeedExchange.CITY_CHOICES}

    if item_type in valid_item_types:
        qs = qs.filter(item_type=item_type)
    if q:
        qs = qs.filter(title__icontains=q) | qs.filter(plant_name__icontains=q)
        # NOTE: `|` di atas menggabungkan dua filter; tidak perlu distinct
        # karena satu tabel, tapi aman bila nanti ada join M2M.
        qs = qs.distinct()
    if city in valid_cities:
        qs = qs.filter(city=city)
    if transaction_type in valid_transactions:
        qs = qs.filter(transaction_type=transaction_type)
    if status in valid_statuses:
        qs = qs.filter(status=status)

    active = {
        'item_type': item_type if item_type in valid_item_types else '',
        'q': q,
        'city': city if city in valid_cities else '',
        'transaction_type': transaction_type if transaction_type in valid_transactions else '',
        'status': status if status in valid_statuses else '',
    }
    return qs, active


def _is_htmx(request):
    return request.headers.get('HX-Request') == 'true'


def _filter_url(current, name, value):
    """URL filter yang mempertahankan param lain (dipakai dropdown custom)."""
    params = dict(current)
    if value:
        params[name] = value
    else:
        params.pop(name, None)
    qs = urlencode({k: v for k, v in params.items() if v})
    base = reverse('seed_exchange:list')
    return f'{base}?{qs}' if qs else base


def _filter_dropdowns(active):
    """Opsi tiap dropdown custom: label, url (pertahankan filter lain), selected."""
    config = [
        ('item_type', 'Semua jenis', list(SeedExchange.ItemType.choices)),
        ('city', 'Semua kota', list(SeedExchange.CITY_CHOICES)),
        ('transaction_type', 'Semua transaksi', list(SeedExchange.TransactionType.choices)),
        ('status', 'Semua status', list(SeedExchange.Status.choices)),
    ]
    dropdowns = []
    for name, all_label, options in config:
        labels = dict(options)
        current_value = active[name]
        items = [{
            'label': all_label,
            'url': _filter_url(active, name, ''),
            'selected': not current_value,
        }]
        for value, label in options:
            items.append({
                'label': label,
                'url': _filter_url(active, name, value),
                'selected': current_value == value,
            })
        dropdowns.append({
            'name': name,
            'current_label': labels.get(current_value, all_label),
            'items': items,
        })
    return dropdowns


def listing_list(request):
    """List read-only untuk guest; filter dinamis via HTMX (partial tanpa reload).

    Kalau login: "Listing Saya" (milik sendiri, bisa diedit) tampil terpisah,
    bagian jelajah hanya berisi listing milik orang lain (bisa di-reserve).
    """
    qs, active = _filtered_queryset(request)
    if request.user.is_authenticated:
        my_listings = list(
            SeedExchange.objects.filter(user=request.user)
            .select_related('user')
            .order_by('-created_at')
        )
        browse = qs.exclude(user=request.user)
    else:
        my_listings = None
        browse = qs
    context = {
        'listings': browse,
        'my_listings': my_listings,
        'active': active,
        'dropdowns': _filter_dropdowns(active),
        'item_types': SeedExchange.ItemType.choices,
        'transaction_types': SeedExchange.TransactionType.choices,
        'statuses': SeedExchange.Status.choices,
        'cities': SeedExchange.CITY_CHOICES,
    }
    if _is_htmx(request):
        return render(request, 'seed_exchange/partials/cards.html', context)
    return render(request, 'seed_exchange/list.html', context)


def listing_detail(request, pk):
    listing = get_object_or_404(SeedExchange.objects.select_related('user', 'reserved_by'), pk=pk)
    is_owner = request.user.is_authenticated and listing.user_id == request.user.id
    is_requester = (
        request.user.is_authenticated
        and listing.reserved_by_id is not None
        and listing.reserved_by_id == request.user.id
        and listing.status == SeedExchange.Status.REQUESTED
    )
    is_accepted = (
        request.user.is_authenticated
        and listing.reserved_by_id is not None
        and listing.reserved_by_id == request.user.id
        and listing.status == SeedExchange.Status.RESERVED
    )
    can_reserve = (
        request.user.is_authenticated
        and not is_owner
        and listing.status == SeedExchange.Status.AVAILABLE
    )
    return render(request, 'seed_exchange/detail.html', {
        'listing': listing,
        'is_owner': is_owner,
        'is_requester': is_requester,
        'is_accepted': is_accepted,
        'can_reserve': can_reserve,
    })


@login_required
def listing_create(request):
    if request.method == 'POST':
        form = SeedExchangeForm(request.POST)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.user = request.user
            listing.save()
            messages.success(request, 'Listing berhasil dibuat.')
            return redirect('seed_exchange:detail', pk=listing.pk)
    else:
        form = SeedExchangeForm()
    return render(request, 'seed_exchange/form.html', {
        'form': form,
        'rows': _form_rows(form),
        'mode': 'create',
    })


@login_required
def listing_update(request, pk):
    listing = get_object_or_404(SeedExchange, pk=pk, user=request.user)
    if request.method == 'POST':
        form = SeedExchangeForm(request.POST, instance=listing)
        if form.is_valid():
            form.save()
            messages.success(request, 'Listing berhasil diperbarui.')
            return redirect('seed_exchange:detail', pk=listing.pk)
    else:
        form = SeedExchangeForm(instance=listing)
    return render(request, 'seed_exchange/form.html', {
        'form': form,
        'rows': _form_rows(form),
        'mode': 'update',
        'listing': listing,
    })


@login_required
def listing_delete(request, pk):
    listing = get_object_or_404(SeedExchange, pk=pk, user=request.user)
    if request.method == 'POST':
        listing.delete()
        messages.success(request, 'Listing berhasil dihapus.')
        return redirect('seed_exchange:list')
    return render(request, 'seed_exchange/confirm_delete.html', {'listing': listing})


def _render_card(request, listing):
    listing = SeedExchange.objects.select_related('user', 'reserved_by').get(pk=listing.pk)
    return render(request, 'seed_exchange/partials/card.html', {'listing': listing})


@login_required
def listing_reserve(request, pk):
    """User login (bukan owner) booking listing yang masih Available.

    Booking = minta, status jadi "Menunggu konfirmasi". Serah terima
    terjadi setelah pemilik menekan Terima (tidak ada pembayaran/chat di v1).
    """
    listing = get_object_or_404(SeedExchange, pk=pk)
    if listing.user_id == request.user.id:
        return HttpResponseForbidden('Tidak bisa memesan listing sendiri.')
    if request.method != 'POST':
        return redirect('seed_exchange:detail', pk=pk)
    if listing.status != SeedExchange.Status.AVAILABLE:
        return HttpResponseBadRequest('Listing sudah tidak available.')
    listing.status = SeedExchange.Status.REQUESTED
    listing.reserved_by = request.user
    listing.save(update_fields=['status', 'reserved_by', 'updated_at'])
    if _is_htmx(request):
        return _render_card(request, listing)
    messages.success(request, f'Booking "{listing.title}" terkirim. Tunggu konfirmasi pemilik ya.')
    return redirect('seed_exchange:detail', pk=pk)


@login_required
def listing_accept(request, pk):
    """Owner menerima booking (Menunggu konfirmasi -> Reserved)."""
    listing = get_object_or_404(
        SeedExchange, pk=pk, user=request.user,
        status=SeedExchange.Status.REQUESTED,
    )
    if request.method != 'POST':
        return redirect('seed_exchange:detail', pk=pk)
    listing.status = SeedExchange.Status.RESERVED
    listing.save(update_fields=['status', 'updated_at'])
    if _is_htmx(request):
        return _render_card(request, listing)
    messages.success(request, 'Booking diterima.')
    return redirect('seed_exchange:detail', pk=pk)


@login_required
def listing_complete(request, pk):
    """Owner menandai listing Selesai (sudah diserahterimakan)."""
    listing = get_object_or_404(SeedExchange, pk=pk, user=request.user)
    if request.method != 'POST':
        return redirect('seed_exchange:detail', pk=pk)
    if listing.status != SeedExchange.Status.RESERVED:
        return HttpResponseBadRequest('Hanya listing yang sudah diterima yang bisa diselesaikan.')
    listing.status = SeedExchange.Status.COMPLETED
    listing.save(update_fields=['status', 'updated_at'])
    if _is_htmx(request):
        return _render_card(request, listing)
    messages.success(request, 'Listing ditandai selesai.')
    return redirect('seed_exchange:detail', pk=pk)


@login_required
def listing_reopen(request, pk):
    """Owner membuka kembali listing (Reserved/Completed -> Available)."""
    listing = get_object_or_404(SeedExchange, pk=pk, user=request.user)
    if request.method != 'POST':
        return redirect('seed_exchange:detail', pk=pk)
    if listing.status == SeedExchange.Status.AVAILABLE:
        return HttpResponseBadRequest('Listing sudah available.')
    listing.status = SeedExchange.Status.AVAILABLE
    listing.reserved_by = None
    listing.save(update_fields=['status', 'reserved_by', 'updated_at'])
    if _is_htmx(request):
        return _render_card(request, listing)
    messages.success(request, 'Listing dibuka kembali.')
    return redirect('seed_exchange:detail', pk=pk)


@login_required
def listing_cancel_reserve(request, pk):
    """Yang booking membatalkan minatnya sendiri.

    Hanya bisa selama masih "Menunggu konfirmasi". Kalau sudah diterima
    pemilik, pembatalan harus lewat pemilik langsung.
    """
    listing = get_object_or_404(
        SeedExchange,
        pk=pk,
        reserved_by=request.user,
        status=SeedExchange.Status.REQUESTED,
    )
    if request.method != 'POST':
        return redirect('seed_exchange:detail', pk=pk)
    listing.status = SeedExchange.Status.AVAILABLE
    listing.reserved_by = None
    listing.save(update_fields=['status', 'reserved_by', 'updated_at'])
    if _is_htmx(request):
        return _render_card(request, listing)
    messages.success(request, 'Booking dibatalkan.')
    return redirect('seed_exchange:detail', pk=pk)


def _form_rows(form):
    """Baris field untuk form.html; select dirender jadi dropdown custom."""
    select_names = {'item_type', 'city', 'transaction_type', 'status'}
    rows = []
    for bound_field in form:
        select = None
        if bound_field.name in select_names:
            value = bound_field.value()
            value = '' if value is None else str(value)
            # Abaikan opsi kosong bawaan Django ("---------"); placeholder
            # "Pilih ..." yang tampil kalau belum ada nilai.
            options = [
                (str(v), label)
                for v, label in bound_field.field.choices if str(v) != ''
            ]
            labels = dict(options)
            select = {
                'value': value,
                'display': labels.get(value, ''),
                'options': [
                    {'value': v, 'label': label, 'selected': v == value}
                    for v, label in options
                ],
                'required': bound_field.field.required,
            }
        rows.append({'field': bound_field, 'select': select})
    return rows

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from main.models import Profile

from .forms import SeedExchangeForm
from .models import SeedExchange

VALID_TABS = ('mine', 'bookings', 'browse')
MAX_SEARCH_LENGTH = 100
MAX_BACK_URL_LENGTH = 2000


def _clean_query(value, limit=MAX_SEARCH_LENGTH):
    """Typed search text: drop control characters, trim it and cap its length.

    A very long or control-character-laden query is harmless to the ORM, but it
    bloats every filter link on the page, so it is kept short.
    """
    printable = ''.join(ch for ch in value if ch.isprintable())
    return printable.strip()[:limit]


def _current_tab(request):
    """Read and validate the ?tab= value (defaults to browse)."""
    tab = request.GET.get('tab', 'browse')
    return tab if tab in VALID_TABS else 'browse'


def _search_filter(qs, q):
    """Case-insensitive search over title, plant name and description."""
    return qs.filter(
        Q(title__icontains=q)
        | Q(plant_name__icontains=q)
        | Q(description__icontains=q)
    )


def _filtered_queryset(request):
    """Filtered queryset for list view (search, item type, city, transaction, status)."""
    qs = SeedExchange.objects.select_related('user').order_by('-created_at')

    item_type = request.GET.get('item_type', '').strip()
    q = _clean_query(request.GET.get('q', ''))
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
        qs = _search_filter(qs, q)
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


def _apply_filters_to_qs(qs, active):
    """Apply the same filters from _filtered_queryset to any queryset."""
    if active.get('item_type'):
        qs = qs.filter(item_type=active['item_type'])
    if active.get('q'):
        qs = _search_filter(qs, active['q'])
    if active.get('city'):
        qs = qs.filter(city=active['city'])
    if active.get('transaction_type'):
        qs = qs.filter(transaction_type=active['transaction_type'])
    if active.get('status'):
        qs = qs.filter(status=active['status'])
    return qs


def _is_htmx(request):
    return request.headers.get('HX-Request') == 'true'


def _filter_url(current, name, value):
    """Build filter URL preserving other params + the current tab (custom dropdowns)."""
    params = {k: v for k, v in current.items() if v}
    if value:
        params[name] = value
    else:
        params.pop(name, None)
    qs = urlencode(params)
    base = reverse('seed_exchange:list')
    return f'{base}?{qs}' if qs else base


def _filter_dropdowns(active):
    """Build dropdown options for template: [{name, current_label, items: [{label, url, selected}]}]."""
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
            'is_active': bool(current_value),
        })
    return dropdowns


@login_required
def listing_list(request):
    """List view with 3 sections: Listing Saya, Booking Saya, Jelajahi."""
    # Remember where the user was so the detail page can send them back to the
    # same tab/filters even after an edit redirect (which drops the query string).
    request.session['seed_exchange_last_list'] = request.get_full_path()[:MAX_BACK_URL_LENGTH]
    qs, active = _filtered_queryset(request)
    active_tab = _current_tab(request)
    # Keep the tab inside `active` so filter URLs preserve it, but never build
    # tab links from it (that produced duplicate ?tab= params).
    active['tab'] = active_tab

    browse_qs = qs.exclude(
        status__in=[
            SeedExchange.Status.REQUESTED,
            SeedExchange.Status.RESERVED,
            SeedExchange.Status.COMPLETED,
        ]
    )
    my_listings = []
    my_bookings = []

    if request.user.is_authenticated:
        my_listings = list(
            _apply_filters_to_qs(
                SeedExchange.objects.filter(user=request.user).select_related('user'), active
            ).order_by('-created_at')
        )
        my_bookings = list(
            _apply_filters_to_qs(
                SeedExchange.objects.filter(reserved_by=request.user)
                .select_related('user', 'reserved_by')
                .exclude(status=SeedExchange.Status.COMPLETED),
                active,
            ).order_by('-updated_at')
        )
        # Never show your own listings (or already booked ones) in Jelajahi.
        browse_qs = browse_qs.exclude(user=request.user)

    listings = list(browse_qs)

    # Filters to carry across tab switches / search (URL encoded once here so
    # templates never emit raw, unescaped values).
    tab_filters = {k: v for k, v in active.items() if v and k != 'tab'}
    q_clear_filters = {k: v for k, v in tab_filters.items() if k != 'q'}

    context = {
        'listings': listings,
        # all of the user's listings, filters aside: the empty Jelajahi uses it to say where theirs are
        'own_listing_total': SeedExchange.objects.filter(user=request.user).count(),
        'my_listings': my_listings,
        'my_bookings': my_bookings,
        'active': active,
        'active_tab': active_tab,
        'tab_qs': urlencode(tab_filters),
        'q_clear_qs': urlencode(q_clear_filters),
        'dropdowns': _filter_dropdowns(active),
        'item_types': SeedExchange.ItemType.choices,
        'transaction_types': SeedExchange.TransactionType.choices,
        'statuses': SeedExchange.Status.choices,
        'cities': SeedExchange.CITY_CHOICES,
    }

    # Both guests and members swap the whole tabs+filter block via HTMX.
    if _is_htmx(request):
        return render(request, 'seed_exchange/partials/tabs_content.html', context)

    return render(request, 'seed_exchange/list.html', context)


def _back_to_my_listings(request):
    """After making, editing or deleting a listing, "back to the list" means Listing Saya.

    The browse tab never shows your own listings, so sending people there made a listing they had just saved
    look as if it had vanished. Returns the URL, which the detail page's back link also reads from the session.
    """
    url = f"{reverse('seed_exchange:list')}?tab=mine"
    request.session['seed_exchange_last_list'] = url
    return url


@login_required
def listing_detail(request, pk):
    listing = get_object_or_404(SeedExchange.objects.select_related('user', 'reserved_by'), pk=pk)
    back_url = reverse('seed_exchange:list')
    if request.GET:
        back_url = f'{back_url}?{request.GET.urlencode()}'[:MAX_BACK_URL_LENGTH]
    else:
        last_list = request.session.get('seed_exchange_last_list', '')
        if last_list.startswith('/seed-exchange/'):
            back_url = last_list
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
        'back_url': back_url,
        'is_owner': is_owner,
        'is_requester': is_requester,
        'is_accepted': is_accepted,
        'can_reserve': can_reserve,
    })


def _location_context(profile, form):
    """Values shown by the read-only location card on the listing form.

    City and contact are never typed here: they come from the profile (the
    listing's old copy is only the fallback), so this card just shows what the
    listing will carry and points to the profile when something is missing.
    """
    city = profile.city or form.instance.city or ''
    contact = profile.contact_text() or form.instance.contact or ''
    return {
        'location_city': city,
        'location_contact': contact,
        'location_ready': bool(city and contact),
    }


@login_required
def listing_create(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = SeedExchangeForm(request.POST, request.FILES, create=True, profile=profile)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.user = request.user
            # New listings always start as available; the owner changes status later.
            listing.status = SeedExchange.Status.AVAILABLE
            listing.save()
            messages.success(request, 'Listing berhasil dibuat.')
            _back_to_my_listings(request)
            return redirect('seed_exchange:detail', pk=listing.pk)
    else:
        form = SeedExchangeForm(create=True, profile=profile)
    return render(request, 'seed_exchange/form.html', {
        'form': form,
        'rows': _form_rows(form),
        'mode': 'create',
        'profile': profile,
        **_location_context(profile, form),
    })


@login_required
def listing_update(request, pk):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    listing = get_object_or_404(SeedExchange, pk=pk, user=request.user)
    if request.method == 'POST':
        form = SeedExchangeForm(request.POST, request.FILES, instance=listing, profile=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Listing berhasil diperbarui.')
            _back_to_my_listings(request)
            return redirect('seed_exchange:detail', pk=listing.pk)
    else:
        form = SeedExchangeForm(instance=listing, profile=profile)
    return render(request, 'seed_exchange/form.html', {
        'form': form,
        'rows': _form_rows(form),
        'mode': 'update',
        'listing': listing,
        'profile': profile,
        **_location_context(profile, form),
    })


@login_required
def listing_delete(request, pk):
    listing = get_object_or_404(SeedExchange, pk=pk, user=request.user)
    if request.method == 'POST':
        listing.delete()
        messages.success(request, 'Listing berhasil dihapus.')
        return redirect(_back_to_my_listings(request))
    return render(request, 'seed_exchange/confirm_delete.html', {'listing': listing})


def _render_card(request, listing):
    listing = SeedExchange.objects.select_related('user', 'reserved_by').get(pk=listing.pk)
    return render(request, 'seed_exchange/partials/card.html', {'listing': listing})


@login_required
def listing_reserve(request, pk):
    """Booking: user requests listing (status -> Menunggu konfirmasi)."""
    listing = get_object_or_404(SeedExchange, pk=pk)
    if listing.user_id == request.user.id:
        return HttpResponseForbidden('Tidak bisa memesan listing sendiri.')
    if request.method != 'POST':
        return redirect('seed_exchange:detail', pk=pk)
    # One conditional UPDATE instead of read-then-save: when two people press "Booking" at
    # the same moment only the first claims it, the second gets the "already taken" answer
    # rather than silently overwriting the first requester.
    claimed = SeedExchange.objects.filter(pk=pk, status=SeedExchange.Status.AVAILABLE).update(
        status=SeedExchange.Status.REQUESTED,
        reserved_by=request.user,
        updated_at=timezone.now(),
    )
    if not claimed:
        return HttpResponseBadRequest('Listing sudah tidak available.')
    if _is_htmx(request):
        return _render_card(request, listing)
    messages.success(request, f'Booking "{listing.title}" terkirim. Tunggu konfirmasi pemilik ya.')
    return redirect('seed_exchange:detail', pk=pk)


@login_required
def listing_accept(request, pk):
    """Owner accepts booking (Menunggu konfirmasi -> Reserved)."""
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
    """Owner marks listing done (Reserved -> Completed)."""
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
    """Owner reopens listing (Reserved/Completed -> Available)."""
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
    """Requester cancels booking (only while Menunggu konfirmasi)."""
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
    """Form rows for template: [{field, select: {value, display, options, required}}].

    City and contact are not form fields at all: they live in the profile and
    the location card only shows them.
    """
    select_names = {'item_type', 'transaction_type', 'status'}
    rows = []
    for bound_field in form:
        select = None
        if bound_field.name in select_names:
            value = bound_field.value()
            value = '' if value is None else str(value)
            # Skip Django's empty choice ("---------"); placeholder shows instead.
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

from django import template

register = template.Library()


@register.filter
def is_select(bound_field):
    """True kalau field dirender sebagai <select> (ChoiceField / ModelChoiceField)."""
    return getattr(bound_field.field.widget, 'input_type', '') == 'select'


@register.simple_tag
def select_data(bound_field):
    """Siapkan data untuk dropdown kustom: nilai saat ini, teks tampilan, placeholder, dan opsi."""
    field = bound_field.field
    raw = bound_field.value()
    current = '' if raw is None else str(raw)

    placeholder = f'Pilih {str(bound_field.label).lower()}…'
    options = []
    display = ''
    for value, label in field.choices:
        value = '' if value is None else str(value)
        if value == '':
            # Opsi kosong: jadi placeholder. Hanya tampil di menu kalau field opsional (supaya bisa dikosongkan).
            placeholder = str(label)
            if field.required:
                continue
        selected = value == current
        if selected and value != '':
            display = str(label)
        options.append({'value': value, 'label': str(label), 'selected': selected})

    # Nilai lama yang sudah tidak ada di pilihan (mis. kota teks bebas) dikosongkan, bukan dikirim ulang.
    if current not in {o['value'] for o in options}:
        current = ''
    return {'value': current, 'display': display, 'placeholder': placeholder, 'options': options}

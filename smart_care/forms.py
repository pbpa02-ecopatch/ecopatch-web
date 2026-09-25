from django import forms

from .models import CareTask


class CareTaskForm(forms.ModelForm):
    class Meta:
        model = CareTask
        fields = ["task_type", "due_date", "is_completed", "notes"]
        widgets = {
            "task_type": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "is_completed": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

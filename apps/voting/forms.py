from django import forms
from .models import Poll
from apps.camps.models import Camp


class PollForm(forms.ModelForm):
    class Meta:
        model  = Poll
        fields = ["camp", "title", "description", "min_votes", "max_votes"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

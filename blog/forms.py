from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from .models import Comment
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ваш комментарий...',
                'minlength': '10',
                'maxlength': '2000',
            }),
        }
        labels = {
            'text': ''
        }

    def clean_text(self):
        text = self.cleaned_data['text']
        stripped_text = strip_tags(text).strip()
        
        if len(stripped_text) < 10:
            raise ValidationError('Комментарий должен содержать минимум 10 символов')
            
        if len(stripped_text) > 2000:
            raise ValidationError('Комментарий не должен превышать 2000 символов')
            
        return stripped_text

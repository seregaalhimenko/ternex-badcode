from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Profile
import hashlib
import random


def create_public_key(id, email):
    salt = str(random.randint(1, 9999999))
    string = str(id) + email + str(salt)
    return hashlib.sha256(bytes(string, "utf-8")).hexdigest()


class UserRegisterForm(UserCreationForm):
    first_name = forms.CharField(
        error_messages={"required": ""},
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-user",
                "placeholder": "Имя",
                "x-autocompletetype": "given-name",
                "autocomplete": "on",
            }
        ),
    )
    last_name = forms.CharField(
        error_messages={"required": ""},
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-user",
                "placeholder": "Фамилия",
                "x-autocompletetype": "family-name",
                "autocomplete": "on",
            }
        ),
    )
    number = forms.CharField(
        error_messages={"required": ""},
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-user",
                "type": "tel",
                "placeholder": "Номер телефона",
                "x-autocompletetype": "tel",
                "autocomplete": "on",
            }
        ),
    )
    email = forms.EmailField(
        error_messages={"required": ""},
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-user mb-3 mb-sm-0",
                "type": "email",
                "placeholder": "Email адрес",
                "x-autocompletetype": "email",
                "autocomplete": "on",
            }
        ),
    )
    password1 = forms.CharField(
        error_messages={"required": ""},
        widget=forms.PasswordInput(
            attrs={"class": "form-control form-control-user", "placeholder": "Пароль", "autocomplete": "off"}
        ),
    )
    password2 = forms.CharField(
        error_messages={"required": ""},
        widget=forms.PasswordInput(
            attrs={"class": "form-control form-control-user", "placeholder": "Пароль еще раз ", "autocomplete": "off"}
        ),
    )

    class Meta:
        model = Profile
        fields = ("email", "first_name", "last_name", "number", "password1", "password2")

    def save(self, commit=True):
        user = super(UserRegisterForm, self).save(commit=False)
        user.username = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.number = self.cleaned_data["number"]
        user.public_key = create_public_key(user.id, user.username)
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-user",
                "aria-describedby": "emailHelp",
                "placeholder": "Введите ваш email...",
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control form-control-user", "placeholder": "Пароль"})
    )


class SMSForm(forms.Form):
    code = forms.IntegerField(
        widget=forms.TextInput(
            attrs={"class": "form-control form-control-user", "placeholder": "Введите полученный в СМС код"}
        )
    )


class WifiUsersLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.TextInput(attrs={"type": "text", "name": "login", "placeholder": "Введите email"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"type": "password", "name": "password", "placeholder": "Введите пароль"})
    )


class ChangeDataForm(forms.Form):
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={"type": "text", "class": "form-control form-control-user p-3", "placeholder": "Имя"}
        ),
    )
    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={"type": "text", "class": "form-control form-control-user p-3", "placeholder": "Фамилия"}  # readonly
        ),
    )
    email = forms.EmailField(
        disabled=True,
        widget=forms.TextInput(
            attrs={
                "type": "email",
                "class": "form-control form-control-user mb-sm-3 mb-md-0 p-3",
                "placeholder": "Email адрес",
            }
        ),
    )
    phone = forms.IntegerField(
        disabled=True,
        widget=forms.TextInput(
            attrs={"type": "text", "class": "form-control form-control-user p-3", "placeholder": "Номер телефона"}
        ),
    )
    MY_CHOICES = (
        (True, "Мужской"),
        (False, "Женский"),
    )
    sex = forms.ChoiceField(
        required=True,
        widget=forms.RadioSelect(
            attrs={
                "class": "sex-radio-buttons form-check-input form-check form-check-inline btn-group-toggle",
                "type": "radio",
            }
        ),
        choices=MY_CHOICES,
    )


class ChangePasswordForm(forms.Form):
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={"type": "password", "class": "form-control form-control-user p-3", "placeholder": "Старый пароль"}
        ),
    )
    new_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={"type": "password", "class": "form-control form-control-user p-3", "placeholder": "Новый пароль"}
        ),
    )


class UploadFileForm(forms.Form):
    image = forms.ImageField(
        required=True,
        widget=forms.FileInput(attrs={"type": "file", "class": "custom-file-input", "accept": "image/*"}),
    )


class UploadUsbFileForm(forms.Form):
    filename = forms.CharField(required=True, widget=forms.TextInput(attrs={"type": "hidden", "class": "filename_usb"}))
    file = forms.FileField(
        required=True,
        widget=forms.FileInput(attrs={"type": "file", "class": "custom-file-input"}),
    )

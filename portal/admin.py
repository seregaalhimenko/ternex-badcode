from django.contrib import admin
from .models import (
    Profile,
    Router,
    Statistics,
    Users_now_Stats,
    NotificationCenter,
    RouterConfiguration,
    Advertisement,
    AdvertisementLog,
    App,
    App_and_Profile,
    Url_Filename_Router,
    SecondEmails,
    Licenses,
    Product,
    Payment,
    SettingsFiscalization,
)
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm


class MyUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Profile


class MyUserAdmin(UserAdmin):
    form = MyUserChangeForm

    fieldsets = UserAdmin.fieldsets + (
        (None, {"fields": ("number", "notification", "sex", "public_key", "coins", "sending_data", "mailing")}),
    )


admin.site.register(Profile, MyUserAdmin)
admin.site.register(Router)
admin.site.register(Statistics)
admin.site.register(Users_now_Stats)
admin.site.register(RouterConfiguration)
admin.site.register(Advertisement)
admin.site.register(AdvertisementLog)
admin.site.register(NotificationCenter)
admin.site.register(App)
admin.site.register(App_and_Profile)
admin.site.register(Url_Filename_Router)
admin.site.register(SecondEmails)
admin.site.register(Licenses)
admin.site.register(Product)
admin.site.register(Payment)
admin.site.register(SettingsFiscalization)

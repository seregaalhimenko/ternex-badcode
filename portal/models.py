import datetime
import hashlib
import json
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import JSONField
from django.utils import timezone


class Profile(AbstractUser):
    """USER"""

    number = models.CharField(max_length=12, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    notification = models.BooleanField(default=True)
    sex = models.BooleanField(default=True)  # men = true, women = false
    photo = models.CharField(max_length=500, default="/static/portal/img/user/user_male.png")
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
    coins = models.IntegerField(default=0)
    public_key = models.CharField(max_length=1000, default="unknown")  # unique=True
    sending_data = models.BooleanField(default=True)
    mailing = models.BooleanField(default=True)


class Licenses(models.Model):
    user = models.ForeignKey(Profile, on_delete=models.CASCADE)
    user_email = models.EmailField()
    date_from = models.DateField()
    date_to = models.DateField()

    def __str__(self):
        return "{} FROM {} TO {}".format(self.user.email, self.date_from, self.date_to)


class Product(models.Model):
    name = models.CharField(max_length=500, unique=True)
    price = models.IntegerField()
    description = models.CharField(max_length=100, default="Лицензия")

    def __str__(self):
        return self.name


class SettingsFiscalization(models.Model):
    """Фискализация из робокасы"""

    sno = models.CharField(max_length=50)
    payment_method = models.CharField(max_length=50)
    payment_object = models.CharField(max_length=50)
    tax = models.CharField(max_length=50)
    price = models.FloatField()
    quantity = models.IntegerField()
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    def get_json(self) -> str:
        return json.dumps(
            {
                "sno": self.sno,
                "items": [
                    {
                        "name": str(self.product),
                        "quantity": self.quantity,
                        "sum": self.price,
                        "payment_method": self.payment_method,
                        "payment_object": self.payment_object,
                        "tax": self.tax,
                    }
                ],
            }
        )


class Payment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    time = models.TimeField(auto_now=True)
    date = models.DateField(auto_now=True)
    order_description = models.CharField(max_length=100, default="Лицензия")
    sum_of_order = models.IntegerField(default=229)
    code_of_goods = models.IntegerField(default=1)
    email_buyer = models.ForeignKey(Profile, on_delete=models.CASCADE)
    status = models.CharField(max_length=100, default="not confirmed")

    def __str__(self):
        return "{},{}: name:{}, price:{}, status: {}".format(
            self.date.strftime("%d.%m.%Y"), self.time.strftime("%H:%M"), self.product, self.sum_of_order, self.status
        )


class SecondEmails(models.Model):
    user = models.ForeignKey(Profile, on_delete=models.CASCADE)
    user_main_email = models.EmailField(max_length=255)
    email = models.EmailField(max_length=255)


def json_default():
    return {"mash_info": []}


class Router(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.EmailField(max_length=50)
    brand = models.CharField(max_length=15)
    model = models.CharField(max_length=15)
    version = models.CharField(max_length=5)
    memory = models.CharField(max_length=10)
    cpu = models.CharField(max_length=20)
    ipv6 = models.CharField(max_length=50, unique=True)
    public_key = models.CharField(max_length=60, unique=True)
    activity = models.BooleanField(default=True)
    state_change_time = models.TimeField(auto_now=True)
    state_change_date = models.DateField(auto_now=True)
    name = models.CharField(max_length=100, default="Router")
    lat = models.CharField(max_length=50, default="unknown")
    lon = models.CharField(max_length=50, default="unknown")
    url = models.CharField(max_length=10000, default="unknown")
    host = models.BooleanField(default=False)
    mac = models.CharField(max_length=50, default="unknown")
    mesh_info = JSONField(default=json_default)

    def __str__(self):
        return self.ipv6


class Statistics(models.Model):
    """Five_Minute_Statistics"""

    # models.ForeignKey(Router, on_delete=models.CASCADE)
    ipv6_router = models.CharField(max_length=50)
    memory_used = models.IntegerField()
    memory_free = models.IntegerField()
    cpu_idle = models.CharField(max_length=15)
    active_users = models.IntegerField()
    openwrt_version = models.CharField(max_length=60)
    time = models.TimeField(auto_now=True)
    date = models.DateField(auto_now=True)
    upload_speed = models.CharField(max_length=20, default="0.0 kbit/s")
    download_speed = models.CharField(max_length=20, default="0.0 kbit/s")
    usb_all_memory = models.CharField(max_length=20, default="0")
    usb_available_memory = models.CharField(max_length=20, default="0")
    channel = models.CharField(max_length=5, default="0")


class Users_now_Stats(models.Model):
    mac_user = models.CharField(max_length=50)
    router = models.ForeignKey(Router, on_delete=models.CASCADE)
    owner_router = models.EmailField(max_length=255, default="unknown@unknown.unknown")
    rx = models.IntegerField()
    tx = models.IntegerField()
    time = models.TimeField(auto_now=True)
    date = models.DateField(auto_now=True)
    session_duration = models.IntegerField(default=0)


class Hotspots(models.Model):
    id_router = models.CharField(max_length=50)
    ssid = models.CharField(max_length=50)
    encryption = models.CharField(max_length=50, default="WPA2")
    key = models.CharField(max_length=50, default="none")


class NotificationCenter(models.Model):
    userBd = models.ForeignKey(Profile, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField()
    title = models.CharField(max_length=150)
    message = models.CharField(max_length=10000)
    new = models.BooleanField(default=True)


class RouterConfiguration(models.Model):
    # router=models.ForeignKey(Router, on_delete=models.CASCADE)
    ipv6_router = models.CharField(max_length=50)
    config = models.CharField(max_length=1000)


class Advertisement(models.Model):
    user = models.ForeignKey(Profile, on_delete=models.CASCADE)
    header = models.CharField(max_length=150)
    message = models.CharField(max_length=1000)
    activity = models.BooleanField(default=True)
    count_transition = models.IntegerField(default=0)  # количество переходов
    count_views = models.IntegerField(default=0)  # количество просмотров


class AdvertisementLog(models.Model):
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE)
    url = models.CharField(max_length=1000)


def user_directory_path_app(instance, filename):
    filename = "archive.tar.gz"
    return "{0}/app/{1}".format(instance.name, filename)


def user_directory_path_script(instance, filename):
    filename = "install "
    return "{0}/scripts/{1}".format(instance.name, filename)


def user_directory_path_logo(instance, filename):
    name_and_expansion = filename.split(".")
    name_and_expansion[0] = hashlib.sha1(bytes(name_and_expansion[0], "utf-8")).hexdigest()
    filename = ".".join(name_and_expansion)
    return "{0}/logo/{1}".format(instance.name, filename)


def user_directory_path_screenshots(instance, filename):
    name_and_expansion = filename.split(".")
    name_and_expansion[0] = hashlib.sha1(bytes(name_and_expansion[0], "utf-8")).hexdigest()
    filename = ".".join(name_and_expansion)
    return "{0}/screenshots/{1}".format(instance.name, filename)


class App(models.Model):
    name = models.CharField(max_length=150)
    short_description = models.CharField(max_length=500)
    full_description = models.CharField(max_length=10000)
    developer = models.EmailField(max_length=50)
    logo = models.ImageField(upload_to=user_directory_path_logo)
    screenshots1 = models.ImageField(upload_to=user_directory_path_screenshots)
    screenshots2 = models.ImageField(upload_to=user_directory_path_screenshots)
    screenshots3 = models.ImageField(upload_to=user_directory_path_screenshots)
    script = models.FileField(upload_to=user_directory_path_script)
    app = models.FileField(upload_to=user_directory_path_app)
    confirmed = models.BooleanField(default=False)
    date_of_creation = models.DateField(default=datetime.date.today)
    time_of_creation = models.TimeField(default=timezone.now)


class App_and_Profile(models.Model):
    email_user = models.EmailField(max_length=255)
    router = models.ForeignKey(Router, on_delete=models.CASCADE)
    id_app = models.IntegerField()
    name_app = models.CharField(max_length=150, default="none")
    installed = models.BooleanField()


class Url_Filename_Router(models.Model):
    url = models.CharField(max_length=10000)
    filename = models.CharField(max_length=10000)
    router = models.ForeignKey(Router, on_delete=models.CASCADE)

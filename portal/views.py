import os
from django.db import router
import requests
import json
import datetime
import pexpect
import hashlib
import logging
import random
from urllib import parse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from .forms import (
    UserRegisterForm,
    LoginForm,
    SMSForm,
    WifiUsersLoginForm,
    ChangeDataForm,
    ChangePasswordForm,
    UploadFileForm,
    UploadUsbFileForm,
)
from PIL import Image
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound, JsonResponse
from django.http import HttpResponseRedirect
from django.contrib.auth import authenticate, login, get_user
from django.shortcuts import render, redirect
from .models import (
    Profile,
    Router,
    Statistics,
    Users_now_Stats,
    NotificationCenter,
    RouterConfiguration,
    Advertisement,
    App,
    App_and_Profile,
    AdvertisementLog,
    Url_Filename_Router,
    Licenses,
    Payment,
    Product,
    SettingsFiscalization,
)


def check_license(request: HttpRequest):
    date_now = datetime.datetime.now().date()
    user = get_user(request)
    license = Licenses.objects.filter(user=user)
    if license:
        if date_now <= license[0].date_to:
            return True
    routers = Router.objects.filter(user=request.user.email)
    if routers.count() == 0:
        return True
    if routers.count() <= 5:
        for router in routers:
            if router.host:
                return True
        return False
    return False


def create_license(user: Profile):
    license = Licenses.objects.filter(user=user)
    if not license:
        license = Licenses(
            user=user,
            user_email=user.email,
            date_from=datetime.datetime.now().date(),
            date_to=(datetime.datetime.now() + datetime.timedelta(days=30)).date(),
        )
        license.save()
        return license
    license[0].date_from = datetime.datetime.now().date()
    license[0].date_to = (datetime.datetime.now() + datetime.timedelta(days=30)).date()
    license[0].save()
    return license[0]


def create_notification(userEmail, title, message):
    """Создание уведомления"""
    dt = datetime.datetime.now()
    user = Profile.objects.filter(email=userEmail)
    notificationBD = NotificationCenter(userBd=user[0], date=dt.date(), time=dt.time(), title=title, message=message)
    notificationBD.save()


def create_data_statistic(email):
    """Обработка данных для отправки на html"""
    routers_by_email = Router.objects.filter(user=email)
    routers = []
    current_time = datetime.datetime.now()
    for router in routers_by_email:
        statistics_and_router = {}
        statistics_and_router["online_days"] = (current_time.date() - router.state_change_date).days
        statistics_and_router["id"] = router.id
        statistics_and_router["user"] = router.user
        statistics_and_router["host"] = router.host
        statistics_and_router["brand"] = router.brand
        statistics_and_router["model"] = router.model
        statistics_and_router["version"] = router.version
        statistics_and_router["memory"] = router.memory
        statistics_and_router["cpu"] = router.cpu
        statistics_and_router["ipv6"] = router.ipv6
        statistics_and_router["public_key"] = router.public_key
        statistics_and_router["activity"] = router.activity
        statistics_and_router["state_change_time"] = router.state_change_time
        statistics_and_router["state_change_date"] = router.state_change_date
        statistics_and_router["name"] = router.name
        statistics_and_router["lat"] = router.lat
        statistics_and_router["lon"] = router.lon
        statistics_and_router["last_statistic"] = Statistics.objects.filter(ipv6_router=router.ipv6).last()
        statistics_and_router["time"] = []
        statistics_and_router["active_users"] = []
        statistics_and_router["memory_used"] = []
        statistics_and_router["memory_free"] = []
        statistics_and_router["upload_speed"] = []
        statistics_and_router["download_speed"] = []
        statistics = Statistics.objects.filter(ipv6_router=router.ipv6)
        # statistics = statistics.reverse()
        for stat in statistics:
            statistics_and_router["time"].append("{}:{}".format(stat.time.hour, stat.time.minute))
            statistics_and_router["active_users"].append(stat.active_users)
            statistics_and_router["memory_used"].append(stat.memory_used)
            statistics_and_router["memory_free"].append(stat.memory_free)
            statistics_and_router["upload_speed"].append(stat.upload_speed)
            statistics_and_router["download_speed"].append(stat.download_speed)
        routers.append(statistics_and_router)
    return routers


def write_config_file(router_id, ipv6):
    config = (
        """
        server {
            listen 8080 ssl http2;
            ssl_certificate /etc/letsencrypt/live/ternex.ru-0002/fullchain.pem;
            ssl_certificate_key /etc/letsencrypt/live/ternex.ru-0002/privkey.pem;
            include /etc/letsencrypt/options-ssl-nginx.conf;
            ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
            server_name router"""
        + str(router_id)
        + """.ternex.ru;

            client_max_body_size 30M;

            location / {
                proxy_pass http://["""
        + ipv6
        + """]:8080;
            }
        }

        server {
            listen 8888 ssl http2;
            ssl_certificate /etc/letsencrypt/live/ternex.ru-0002/fullchain.pem;
            ssl_certificate_key /etc/letsencrypt/live/ternex.ru-0002/privkey.pem;
            include /etc/letsencrypt/options-ssl-nginx.conf;
            ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
            server_name router"""
        + str(router_id)
        + """.ternex.ru;

            client_max_body_size 30M;

            location / {
                proxy_pass http://["""
        + ipv6
        + """]:8888;
            }
        }
    """
    )
    name = "router{}.ternex.ru".format(router_id)
    with open("/etc/nginx/sites-enabled/" + name, "w") as f:
        f.write(config)
    return 1


def systemctl_reload_nginx():
    try:
        child = pexpect.spawn("su")
        child.expect("[Pp]assword:")
        child.sendline(os.getenv("ROOTPASS"))
        child.expect("[>#$]?")
        child.sendline("/var/www/ternexEnv/ternex/portal/scriptByat")
        child.expect("[>#$]?")
        child.close()
    except pexpect.ExceptionPexpect:
        return HttpResponse("Произошла ошибка в функции systemctl_reload_nginx")
    return 1


@require_http_methods(["GET", "POST"])
@login_required
def portal_index(request: HttpRequest):
    """Функционал index.html"""
    if not check_license(request):
        return redirect("/payment-expired/")
    is_adding_router = False
    is_adding_ipv6 = "null"
    if request.session.get("data_router"):
        data_router = request.session["data_router"]
        is_adding_ipv6 = data_router["ipv6"]
        is_adding_router = True
        if not Router.objects.filter(ipv6=data_router["ipv6"]) and not Router.objects.filter(
            public_key=data_router["public_key"]
        ):
            router = Router(
                user=request.user.email,
                brand=data_router["brand"],
                version=data_router["version"],
                model=data_router["model"],
                memory=data_router["memory"],
                cpu=data_router["cpu"],
                ipv6=data_router["ipv6"],
                public_key=data_router["public_key"],
                activity=True,
            )
            router.save()  # Добавление в базу нового роутера
            router.url = "router{}.ternex.ru".format(router.id)
            router.save()
            certification(router.id, router.ipv6)
            if data_router["mac"]:
                router.mac = data_router["mac"]
                router.save()
        request.session["data_router"] = None
    if request.method == "POST":
        if (
            request.POST.get("correct-lat") and request.POST.get("correct-lon") and request.POST.get("router_ipv6")
        ):  # узнаем координаты и сохраняем
            router = Router.objects.get(ipv6=request.POST.get("router_ipv6"))
            router.lat = request.POST.get("correct-lat")
            router.lon = request.POST.get("correct-lon")
            router.save()

        # изменение названия роутера
        if request.POST.get("new-name") and request.POST.get("id"):
            router = Router.objects.filter(id=request.POST.get("id"))
            if router[0].user == request.user.email:
                router.update(name=request.POST.get("new-name"))
            return redirect("/portal/")
    routers = create_data_statistic(request.user.email)
    return render(
        request,
        "index.html",
        {"routers": routers, "is_adding_router": is_adding_router, "is_adding_ipv6": is_adding_ipv6},
    )


def sms_check(request: HttpRequest):
    if not (request.session.get("code") and request.session.get("formReg") and request.session.get("number")):
        return redirect("/portal/")
    formSms = SMSForm()
    if request.method == "GET":
        return render(request, "sms-check.html", {"formSms": formSms})

    formSms = SMSForm(request.POST)
    if formSms.is_valid():
        if str(formSms.cleaned_data["code"]) == request.session["code"]:
            formReg = UserRegisterForm(request.session["formReg"])
            formReg.save()
            user = authenticate(
                email=request.session["formReg"]["email"], password=request.session["formReg"]["password1"]
            )
            create_license(user)
            if user is not None and user.is_active:
                if request.session.get("ipv6") and request.session.get("mac"):
                    ipv6 = request.session.get("ipv6")
                    mac = request.session.get("mac")
                    mac_creation(name=ipv6, mac=mac)
                    scp("/var/www/ternexEnv/ternex/macFiles/{0}".format(ipv6), ipv6, "www")
                    requests.post("http://[" + ipv6 + "]/cgi-bin/permit-client-by-mac", data={"filename": ipv6})
                    login(request, user)
                    return redirect("/ad/")
                login(request, user)
                return redirect("/portal/")
            return HttpResponseRedirect("/login")
    return render(request, "sms-check.html", {"formSms": formSms})


@require_GET
def register(request: HttpRequest):
    """Форма регистрации"""
    form = UserRegisterForm()
    return render(request, "register.html", {"form": form})


@require_POST
def register_user(request: HttpRequest):
    """Пост запрос на регистрацию"""
    form = UserRegisterForm(request.POST)
    if not form.is_valid():
        return render(request, "register.html", {"form": form})

    login = os.getenv("SMSLOGIN")
    psw = os.getenv("SMSPASS")
    phone = str(form.cleaned_data["number"])
    code = str(random.randint(10000, 99999))
    log("register_user", "code-{},login-{},pass-{}".format(code, login, psw), "NONE TYPE?")
    requests.post(
        "https://smsc.ru/sys/send.php?login="
        + login
        + "&psw="
        + psw
        + "&phones="
        + phone
        + "&mes=Код подтверждения "
        + code
        + "&sender=TERNEX"
    )
    request.session["code"] = code
    request.session["formReg"] = form.data
    request.session["number"] = phone

    return HttpResponseRedirect("/sms_check")


@require_http_methods(["GET", "POST"])
@csrf_exempt  # отключение csrf
def user_login(request: HttpRequest):
    if request.user.is_authenticated:
        return redirect("/portal/")

    if request.method == "GET":
        form = LoginForm()
        return render(request, "login.html", {"form": form})

    form = LoginForm(request.POST)
    if form.is_valid():
        user = authenticate(email=form.cleaned_data["email"], password=form.cleaned_data["password"])
        if user is not None and user.is_active:
            login(request, user)
            return redirect("/portal/")
    return render(request, "login.html", {"form": form, "context": "Неверный email или пароль"})


@require_GET
@csrf_exempt
def add_new_router(request: HttpRequest):
    """Получаем данные для добавления нового роутера на портал"""
    if not check_license(request):
        return redirect("/payment-expired/")
    try:
        request.session["data_router"] = {
            "brand": request.GET["brand"],
            "model": request.GET["model"],
            "version": request.GET["version"],
            "memory": request.GET["memory"],
            "cpu": request.GET["cpu"],
            "ipv6": request.GET["ipv6"],
            "public_key": request.GET["public_key"],
        }
    except ObjectDoesNotExist:
        return redirect("/portal/")
    if not request.user.is_authenticated:
        return redirect("/login/")
    return redirect("/portal/")


@csrf_exempt
def mac_creation(name, mac):
    with open("/var/www/ternexEnv/ternex/macFiles/" + name, "w") as f:
        f.write(mac)


def delete_server_file(name_file):
    command = "rm" + name_file
    os.system(command)


@csrf_exempt
def scp(name_files, path, dirs):
    """
    Отправка по SSH (более универсальная)
    name_file -> должен быть полным путем например: /var/www/ternexEnv/ternex/networkFiles/
    path -> ipv4,ipv6
    dirs -> в какую папку будет отправлен файл
    """
    command = "scp {0} config@[{1}]:/{2}".format(name_files, path, dirs)
    child = pexpect.spawn(command)
    i = child.expect([pexpect.TIMEOUT, pexpect.EOF, "Are you sure you want to continue connecting", "[P|p]assword:"])
    if i in (0, 1):
        log(scp.__name__, "Timeout or EOF", comment="")
        return
    if i == 2:
        child.sendline("yes")
        i = child.expect([pexpect.TIMEOUT, pexpect.EOF, "[P|p]assword:"])
        if i in (0, 1):
            log(scp.__name__, "Timeout or EOF", comment="")
            return
    child.sendline(os.getenv("KEY"))
    child.expect(pexpect.EOF)
    return


def certification(router_id, ipv6):
    write_config_file(router_id, ipv6)
    systemctl_reload_nginx()
    scp("/var/www/ternexEnv/ternex/certs/fullchain.pem /var/www/ternexEnv/ternex/certs/privkey.pem", ipv6, "www")
    requests.get("http://[{}]/cgi-bin/update-certs".format(ipv6), params={"id": router_id})
    return 1


# @require_GET
@csrf_exempt
def show_advertising(request: HttpRequest):
    """Показывает 'рекламу'"""
    if not (request.session.get("ipv6")):
        return redirect("/portal/")
    ipv6 = request.session["ipv6"]
    router = Router.objects.get(ipv6=ipv6)
    user_router = Profile.objects.get(email=router.user)
    advertisements = Advertisement.objects.filter(user=user_router).filter(activity=True)
    if not advertisements:
        return render(
            request, "ad-zero.html", {"img": "../../static/portal/img/dinosaurs/{}.png".format(random.randint(1, 17))}
        )
    # Показ случайной рекламы из выбранных
    length = advertisements.count()
    advertisements = advertisements[random.randint(0, length - 1)]
    advertisements.count_views += 1
    advertisements.save()
    return render(request, "ad.html", {"advertisement": advertisements})


def test(request: HttpRequest):
    advertisements = Advertisement.objects.filter(activity=True)
    if not advertisements:
        return render(
            request, "ad-zero.html", {"img": "../../static/portal/img/dinosaurs/{}.png".format(random.randint(1, 17))}
        )
    length = advertisements.count()
    advertisements = advertisements[random.randint(0, length - 1)]
    advertisements.count_views += 1
    advertisements.save()
    return render(request, "ad.html", {"advertisement": advertisements})


@require_http_methods(["GET", "POST"])
def login_wifi_users(request: HttpRequest):
    """Логин для использования wifi"""
    if not ("mac" in request.GET or "ipv6" in request.GET):
        return redirect("/portal/")
    ipv6 = request.GET["ipv6"]
    mac = request.GET["mac"]
    request.session["mac"] = mac
    request.session["ipv6"] = ipv6
    if request.user.is_authenticated:
        mac_creation(name=ipv6, mac=mac)
        scp("/var/www/ternexEnv/ternex/macFiles/{0}".format(ipv6), ipv6, "www")
        requests.post("http://[" + ipv6 + "]/cgi-bin/permit-client-by-mac", data={"filename": ipv6})
        return redirect("/ad/")
    if request.method == "GET":
        return render(request, "index-captive.html", {"form": WifiUsersLoginForm()})
    form = WifiUsersLoginForm(request.POST)
    if form.is_valid():
        email = form.cleaned_data["email"]
        user = authenticate(email=email, password=form.cleaned_data["password"])
        if user is not None and user.is_active:
            login(request, user)
            mac_creation(name=ipv6, mac=mac)
            scp("/var/www/ternexEnv/ternex/macFiles/{0}".format(ipv6), ipv6, "www")
            requests.post("http://[" + ipv6 + "]/cgi-bin/permit-client-by-mac", data={"filename": ipv6})
            return redirect("/ad/")
    return render(request, "index-captive.html", {"form": form, "context": "Неверный email или пароль"})


@require_POST
@csrf_exempt
def router_status(request: HttpRequest):
    """Получение json файла от роутера и обработка"""
    body_str = request.body.decode("utf-8")
    received_json_data = json.loads(body_str)
    logging.basicConfig(level=logging.DEBUG)
    stats = Statistics(
        ipv6_router=received_json_data["ipv6"],
        memory_used=received_json_data["memory_used"],
        memory_free=received_json_data["memory_free"],
        cpu_idle=received_json_data["cpu_idle"],
        active_users=received_json_data["active_users"],
        openwrt_version=received_json_data["openwrt_version"],
        upload_speed=received_json_data["tx_speed_now"],
        download_speed=received_json_data["rx_speed_now"],
        usb_all_memory=received_json_data["usb_all"] if received_json_data["usb_all"] else 0,
        usb_available_memory=received_json_data["usb_available"] if received_json_data["usb_all"] else 0,
        channel=received_json_data["channel"],
    )
    stats.save()
    router = Router.objects.get(ipv6=received_json_data["ipv6"])
    if "mesh_info" in received_json_data:
        logging.info(received_json_data["mesh_info"])
        router.mesh_info = received_json_data["mesh_info"]
        router.save()
    for user in received_json_data["users"]:
        userStats = Users_now_Stats(
            mac_user=user["mac"],
            router=router,
            owner_router=router.user,
            rx=user["rx_bytes"],
            tx=user["tx_bytes"],
            session_duration=int(user["connected_secs"]),
        )
        userStats.save()
    return HttpResponse("OK")


def handle_uploaded_file(f, name):
    """Сохранение фотографии"""
    extension = f.name.split(".")[1]
    try:
        img = Image.open(f)
        path = "/var/www/ternexEnv/ternex/static/portal/uploadedImg/" + name + "." + extension
        img.save(path, optimize=True, quality=85)
    except OSError as err:
        return (0, err)
    return name + "." + extension


@require_GET
@login_required
def user_profile(request: HttpRequest):
    """Страница настроек профиля"""
    return render(
        request,
        "user-profile.html",
        {
            "form": ChangeDataForm(
                initial={
                    "first_name": request.user.first_name,
                    "last_name": request.user.last_name,
                    "email": request.user.email,
                    "phone": request.user.number,
                    "sex": request.user.sex,
                }
            ),
            "formPass": ChangePasswordForm(),
            "formImg": UploadFileForm(),
        },
    )


@require_POST
@login_required
def change_user_data(request: HttpRequest):
    """Изменение настроек пользователя в профиле"""
    user = get_user(request)
    Form = ChangeDataForm(
        request.POST,
        initial={
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "email": request.user.email,
            "phone": request.user.number,
            "sex": request.user.sex,
        },
    )
    if Form.is_valid() and Form.has_changed():
        user.first_name = Form.cleaned_data["first_name"]
        user.last_name = Form.cleaned_data["last_name"]
        user.sex = Form.cleaned_data["sex"]
        user.save()
    return redirect("/user-profile/")


@require_POST
@login_required
def change_user_password(request: HttpRequest):
    """Изменение пароля пользователя в профиле"""
    user = get_user(request)
    FormPass = ChangePasswordForm(request.POST)
    if FormPass.is_valid() and user.check_password(FormPass.cleaned_data["password"]):
        user.set_password(FormPass.cleaned_data["new_password"])
        user.save()
    return redirect("/user-profile/")


@require_POST
@login_required
def change_user_image(request: HttpRequest):
    """Изменение картинки пользователя в профиле"""
    user = get_user(request)
    FormImg = UploadFileForm(request.POST, request.FILES)
    if FormImg.is_valid():
        name_image = handle_uploaded_file(request.FILES["image"], request.user.number)
        user.photo = "/static/portal/uploadedImg/" + name_image
        user.save()
    return redirect("/user-profile/")


def log(name_fun, out, comment=""):
    """Запись в лог файл"""
    with open("/var/www/ternexEnv/ternex/myDjangolog/Log", "a") as f:
        f.write(name_fun + ": " + out + " " + comment + ".\n")


@require_POST
@login_required
def delete_router(request: HttpRequest):
    """Удаление роутера"""
    if not check_license(request):
        return redirect("/payment-expired/")
    if not request.POST.get("id"):
        return HttpResponse("OK")
    try:
        router_id = request.POST.get("id")
        Router.objects.filter(id=router_id).delete()
        return redirect("/portal/")
    except Router.DoesNotExist:
        return HttpResponseNotFound("<h2>Router not found</h2>")


@csrf_exempt
def create_config_wifi_network(router, name_wifi, password=None, encryption="psk2"):
    """Создание конфигурации для роутера"""
    network = "lan"
    if router.model == "RE650":
        network = "wlan"
    if password:
        config = """
config wifi-iface '{1}'
    option device 'radio0'
    option mode 'ap'
    option encryption '{2}'
    option key '{0}'
    option network '{3}'
    option ssid '{1}'
        """.format(
            password, name_wifi, encryption, network
        )
        return config
    config = """
config wifi-iface '{0}'
    option device 'radio0'
    option mode 'ap'
    option encryption 'none'
    option network '{1}'
    option ssid '{0}'
    """.format(
        name_wifi, network
    )
    return config


@csrf_exempt
def create_file_wifi_network(config):
    """Создание файла из конфигураций"""
    name = str(random.randint(10000, 99999))
    with open("/var/www/ternexEnv/ternex/networkFiles/" + name, "w") as f:
        f.write(config)
    return name


@require_POST
@login_required
def change_notification_status(request: HttpRequest):
    user = get_user(request)
    if request.POST.get("status") == "True":
        user.notification = True
        user.save()
        return redirect("/user-profile/")
    user.notification = False
    user.save()
    return redirect("/user-profile/")


@require_POST
@login_required
def change_mailing_status(request: HttpRequest):
    user = get_user(request)
    if request.POST.get("status") == "True":
        user.mailing = True
        user.save()
        return redirect("/user-profile/")
    user.mailing = False
    user.save()
    return redirect("/user-profile/")


@require_POST
@login_required
def change_sending_data_status(request: HttpRequest):
    user = get_user(request)
    if request.POST.get("status") == "True":
        user.sending_data = True
        user.save()
        return redirect("/user-profile/")
    user.sending_data = False
    user.save()
    return redirect("/user-profile/")


@require_GET
@login_required
def router_settings(request: HttpRequest, id_router):
    """Страница настроек роутера"""
    if not check_license(request):
        return redirect("/payment-expired/")
    try:
        router = Router.objects.get(id=id_router)
    except ObjectDoesNotExist:
        return redirect("/portal/")

    user_routers = Router.objects.filter(user=request.user.email)
    if router not in user_routers:
        return redirect("/portal/")

    current_time = datetime.datetime.now()
    online_days = (current_time.date() - router.state_change_date).days
    statistics = Statistics.objects.filter(ipv6_router=router.ipv6)
    graph_stats = {
        "time": [],
        "active_users": [],
        "memory_used": [],
        "memory_free": [],
        "upload_speed": [],
        "download_speed": [],
    }
    for stat in statistics:
        graph_stats["time"].append("{:02}:{:02}".format(stat.time.hour, stat.time.minute))
        graph_stats["active_users"].append(stat.active_users)
        graph_stats["memory_used"].append(stat.memory_used)
        graph_stats["memory_free"].append(stat.memory_free)
        graph_stats["upload_speed"].append(stat.upload_speed)
        graph_stats["download_speed"].append(stat.download_speed)
    last_statistic = Statistics.objects.filter(ipv6_router=router.ipv6).last()
    response = requests.post("http://[" + str(router) + "]/cgi-bin/get-all-hotspots/", data={"id": id_router})
    received_json_data = response.json()

    return render(
        request,
        "router_settings.html",
        {
            "last_statistic": last_statistic,
            "statistics": graph_stats,
            "router": router,
            "hotspots": received_json_data["hotspots"],
            "id_router": id_router,
            "myerr": "",
            "online_days": online_days,
            "apps": App_and_Profile.objects.filter(email_user=request.user.email).filter(router=router),
        },
    )


@require_POST
@login_required
def change_wifi_channel(request: HttpRequest, id_router):
    """Изменение wifi канала на роутере. TODO А если каннал не пришел?"""
    if not check_license(request):
        return redirect("/payment-expired/")
    try:
        router = Router.objects.get(id=id_router)
    except ObjectDoesNotExist:
        return redirect("/portal/")

    requests.get("http://[" + str(router) + "]/cgi-bin/change-wifi-channel", params={"c": request.POST.get("channel")})
    return redirect("/router/{}/settings/".format(id_router))


@require_POST
@login_required
def add_wifi_network(request: HttpRequest, id_router):
    """Добавление wifi сети"""
    if not check_license(request):
        return redirect("/payment-expired/")
    try:
        router = Router.objects.get(id=id_router)
        password = request.POST.get("password")
        if password:
            if not (password == request.POST.get("password_check")):
                return redirect("/router/{}/settings/?err=Пароли не совпадают".format(id_router))
            if len(password) < 8 or not password:
                return redirect("/router/{}/settings/?err=Пароль менее 8 символов".format(id_router))

        config = create_config_wifi_network(router, request.POST.get("wifi_name"), password)
        filename = create_file_wifi_network(config)
        scp("/var/www/ternexEnv/ternex/networkFiles/" + filename, str(router), "www/configs")
        requests.post(
            "http://[" + str(router) + "]/cgi-bin/add-configs",
            data={"filename": filename, "config_file": "wireless"},
        )
        network_bd_obj = RouterConfiguration(ipv6_router=str(router), config=config)
        network_bd_obj.save()
        return redirect("/router/{}/settings/".format(id_router))
    except ObjectDoesNotExist:
        return redirect("/portal/")


@require_POST
@login_required
def edit_wifi_network(request: HttpRequest, id_router):
    """Изменение wifi сети"""
    if not check_license(request):
        return redirect("/payment-expired/")
    try:
        router = Router.objects.get(id=id_router)
        password = request.POST.get("password")
        if password:
            if not (password == request.POST.get("password_check")):
                return redirect("/router/{}/settings/?err=Пароли не совпадают".format(id_router))
            if len(password) < 8 or not password:
                return redirect("/router/{}/settings/?err=Пароль менее 8 сивмолов".format(id_router))

        config = create_config_wifi_network(router, request.POST.get("wifi_name"), password)
        filename = create_file_wifi_network(config)
        scp("/var/www/ternexEnv/ternex/networkFiles/" + filename, str(router), "www/configs")
        requests.post(
            "http://[" + str(router) + "]/cgi-bin/edit-configs",
            data={"ssid": request.POST.get("ssid"), "filename": filename, "config_file": "wireless"},
        )
        network_bd_obj = RouterConfiguration(ipv6_router=str(router), config=config)
        network_bd_obj.save()
        return redirect("/router/{}/settings/".format(id_router))
    except ObjectDoesNotExist:
        return redirect("/portal/")


@require_POST
@login_required
def delete_wifi_network(request: HttpRequest, id_router):
    """Удаление wifi сети"""
    if not check_license(request):
        return redirect("/payment-expired/")
    try:
        router = Router.objects.get(id=id_router)
    except ObjectDoesNotExist:
        return redirect("/portal/")

    requests.post(
        "http://[" + str(router) + "]/cgi-bin/delete-configs",
        data={"ssid": request.POST.get("ssid"), "config_file": "wireless"},
    )
    return redirect("/router/{}/settings/".format(id_router))


@login_required
def advertisement_board(request: HttpRequest):
    """Доска объявлений и создание объявлений"""
    if not check_license(request):
        return redirect("/payment-expired/")
    user = get_user(request)
    if request.method == "POST":
        if request.POST.get("advertisement_id") and request.POST.get("advertisement_activity"):

            advertisement = Advertisement.objects.get(id=request.POST.get("advertisement_id"))

            advertisement.activity = False
            if request.POST.get("advertisement_activity") == "True":
                advertisement.activity = True

            advertisement.save()
        if request.POST.get("advertisement_delete_id"):
            Advertisement.objects.filter(id=request.POST.get("advertisement_delete_id")).delete()
    advertisements = Advertisement.objects.filter(user=user)
    return render(request, "advertisement-board.html", {"advertisements": advertisements})


@require_GET
@login_required
def advertisement_view(request, id_advertisement):
    """Страница одного объявления"""
    if not check_license(request):
        return redirect("/payment-expired/")
    user = get_user(request)
    user_advertisements = Advertisement.objects.filter(user=user)
    try:
        advertisement = Advertisement.objects.get(id=id_advertisement)
    except ObjectDoesNotExist:
        return redirect("/portal/")
    if advertisement not in user_advertisements:
        return redirect("/portal/")
    return render(request, "advertisement_view.html", {"advertisement": advertisement})


@login_required
def advertisement_create(request: HttpRequest):
    """Страница создания объявления"""
    if not check_license(request):
        return redirect("/payment-expired/")
    user = get_user(request)
    if request.POST.get("advertisement_header") and request.POST.get("advertisement_message"):
        advertisements = Advertisement(
            user=user,
            header=request.POST.get("advertisement_header"),
            message=request.POST.get("advertisement_message"),
        )
        advertisements.save()
        return redirect("/advertisement-board/")
    return render(request, "advertisement-create.html")


@require_GET
@login_required
def notifications(request: HttpRequest):
    """Список уведомлений"""
    return render(
        request,
        "notifications.html",
        {"notifications": NotificationCenter.objects.filter(userBd=get_user(request)).order_by("-date")},
    )


@require_GET
@login_required
def notification_view(request, id_notification):
    """Страница одного уведомления"""
    user = get_user(request)
    user_notifications = NotificationCenter.objects.filter(userBd=user)
    try:
        notification = NotificationCenter.objects.get(id=id_notification)
    except ObjectDoesNotExist:
        return redirect("/portal/")

    if notification not in user_notifications:
        return redirect("/portal/")
    if notification.new:
        notification.new = False
        notification.save()
    return render(request, "notification_view.html", {"notification": notification})


@require_POST
@login_required
def delete_notification(request: HttpRequest):
    """Удаление уведомления"""

    if not request.POST.get("id_notification"):
        return HttpResponse("OK")
    try:
        NotificationCenter.objects.get(id=request.POST.get("id_notification")).delete()
    except ObjectDoesNotExist:
        return HttpResponseNotFound("<h2>Notification not found</h2>")
    return redirect("/notifications/")


def Redirect(request: HttpRequest):
    if not (request.GET.get("id") and request.GET.get("url")):
        return redirect("/portal/")
    id = request.GET.get("id")
    url = request.GET.get("url")
    advertisement = Advertisement.objects.get(id=id)
    advertisement.count_transition += 1
    advertisement.save()
    advertisement_log = AdvertisementLog(advertisement=advertisement, url=url)
    advertisement_log.save()
    return HttpResponseRedirect(url)


@require_POST
@csrf_exempt
def notification_count(request: HttpRequest):
    body = json.loads(request.body)
    email = body["email"]
    try:
        user = Profile.objects.get(email=email)
        count = NotificationCenter.objects.filter(userBd=user).filter(new=True).count()
        return HttpResponse(str(count))
    except ObjectDoesNotExist:
        return HttpResponse("<h2>ошибка в питоне</h2> email=" + str(email))


@require_GET
@login_required
def applications(request: HttpRequest):
    """Страница центра приложений"""
    if not check_license(request):
        return redirect("/payment-expired/")
    confirmed_app = App.objects.filter(confirmed=True)
    developer_app = App.objects.filter(developer=request.user.email)
    apps = confirmed_app.union(developer_app).order_by("-date_of_creation")

    return render(request, "apps.html", {"apps": apps})


@require_POST
@login_required
def add_application(request: HttpRequest):
    """Добавление приложения"""
    if not check_license(request):
        return redirect("/payment-expired/")
    dt = datetime.datetime.now()
    app = App(
        name=request.POST.get("name"),
        short_description=request.POST.get("short_description"),
        full_description=request.POST.get("full_description"),
        developer=request.user.email,
        logo=request.FILES["logo"],
        screenshots1=request.FILES["screenshot1"],
        screenshots2=request.FILES["screenshot2"],
        screenshots3=request.FILES["screenshot3"],
        script=request.FILES["script"],
        app=request.FILES["app"],
        date_of_creation=dt.date(),
        time_of_creation=dt.time(),
    )
    app.save()
    return redirect("/applications/")


@require_GET
@login_required
def single_application(request: HttpRequest, id_app):
    """Страница приложения"""
    if not check_license(request):
        return redirect("/payment-expired/")
    try:
        app = App.objects.get(id=id_app)
    except ObjectDoesNotExist:
        return redirect("/portal/")
    is_installed = App_and_Profile.objects.filter(email_user=request.user.email).filter(id_app=app.id)
    routers = Router.objects.filter(user=request.user.email)
    return render(
        request,
        "single-app.html",
        {"app": app, "routers": routers, "installed": is_installed[0].installed if is_installed else False},
    )


@require_POST
@login_required
def install_application(request: HttpRequest, id_app):
    """Установка приложения на точку"""
    if not check_license(request):
        return redirect("/payment-expired/")
    try:
        app = App.objects.get(id=id_app)
    except ObjectDoesNotExist:
        return redirect("/portal/")

    router_id = request.POST.get("router_id")
    router = Router.objects.get(id=router_id)

    files = str(app.app.path) + " " + str(app.script.path)
    i = scp(files, str(router), "/tmp/apps")
    if i != 1:
        scp(files, str(router), "/tmp/apps")
    r = requests.get("http://[" + str(router) + "]/cgi-bin/install-app", params={"app": app.name})
    if r.status_code == 200:
        app_and_profile = App_and_Profile(
            id_app=app.id, name_app=app.name, router=router, email_user=request.user.email, installed=True
        )
        app_and_profile.save()
    return redirect("/app/" + str(id_app) + "/")


@require_POST
@login_required
def delete_application(request: HttpRequest):
    if not check_license(request):
        return redirect("/payment-expired/")
    app_id = request.POST.get("id_app")
    router_id = request.POST.get("router_id")
    try:
        app = App.objects.get(id=app_id)
    except ObjectDoesNotExist:
        return redirect("/portal/")
    router = Router.objects.get(id=router_id)

    r = requests.get("http://[" + str(router) + "]/cgi-bin/uninstall-app/", params={"app": app.name})
    if r.status_code == 200:
        App_and_Profile.objects.filter(router=router).filter(email_user=request.user.email).filter(
            id_app=app.id
        ).delete()
    return redirect("/router/{}/settings/".format(router.id))


@login_required
def usb(request: HttpRequest, id_router):
    if not check_license(request):
        return redirect("/payment-expired/")
    router = Router.objects.get(id=id_router)
    statistics = Statistics.objects.filter(ipv6_router=router.ipv6).last()
    usb_info = None
    if statistics:
        usb_info = {"all_memory": statistics.usb_all_memory, "available_memory": statistics.usb_available_memory}
    else:
        usb_info = {"all_memory": "Статистика еще не получена", "available_memory": "Статистика еще не получена"}
    cached_files = Url_Filename_Router.objects.filter(router=router)
    if request.method == "POST":
        FormFile = UploadUsbFileForm(request.POST, request.FILES)
        if FormFile.is_valid():
            name = FormFile.cleaned_data["filename"]
            with open(
                "/var/www/ternexEnv/ternex/uploadUsbFile/" + request.user.email + "_" + name, "wb+"
            ) as destination:
                for chunk in request.FILES["file"].chunks():
                    destination.write(chunk)
            scp(
                "/var/www/ternexEnv/ternex/uploadUsbFile/" + request.user.email + "_" + name,
                str(router),
                "mnt/sda1/" + name,
            )
            delete_server_file("/var/www/ternexEnv/ternex/uploadUsbFile/" + request.user.email + "_" + name)
        return redirect("/router/" + str(id_router) + "/usb/")
    FormFile = UploadUsbFileForm()
    return render(
        request,
        "usb.html",
        {"usb_info": usb_info, "FormFile": FormFile, "router": router, "cached_files": cached_files},
    )


@csrf_exempt
def UpdateSingleUser(request: HttpRequest):
    if not check_license(request):
        return redirect("/payment-expired/")
    if request.method == "GET":
        return redirect("/portal/")
    os.system("python3 /var/www/ternexEnv/ternex/updateSingleUser.py" + " " + request.user.email)
    return redirect("/portal/")


@csrf_exempt
def cleanNotifications(request: HttpRequest):
    if request.method == "GET":
        return redirect("/portal/")
    user = get_user(request)
    try:
        NotificationCenter.objects.filter(userBd=user).delete()
        return redirect("/notifications/")
    except NotificationCenter.DoesNotExist:
        return HttpResponseNotFound("<h2>Notification not found</h2>")
    return redirect("/notifications/")


def api_get_cache_location(request: HttpRequest):
    if not request.GET.get("url"):
        return redirect("/portal/")
    url = request.GET.get("url")
    if not Url_Filename_Router.objects.filter(url=url):
        return HttpResponse("No such url")
    url_filename_router = Url_Filename_Router.objects.get(url=url)
    router = url_filename_router.router
    return HttpResponse("https://{0}:8080/cache/{1}".format(router.url, url_filename_router.filename))


def hashsha256(in_str: str):
    h = hashlib.sha256(bytes(in_str, "utf-8")).hexdigest()
    return h


def hashsha1(in_str: str):
    h = hashlib.sha1(bytes(in_str, "utf-8")).hexdigest()
    return h


def create_hashed_file(file, name):
    """Создание файла на сервере"""
    salt = str(random.randint(10000, 99999))
    filename = name + salt
    extension = name.split(".")[-1]
    hashed_filename = hashsha1(filename) + "." + extension
    with open("/var/www/ternexEnv/ternex/cacheFile/" + hashed_filename, "wb+") as f:
        for chunk in file.chunks():
            f.write(chunk)
    return hashed_filename


@require_POST
def upload_file_cache(request: HttpRequest, router_id):
    filename = request.POST.get("cache_filename")
    file = request.FILES["cache_file"]
    url = request.POST.get("cache_url")
    router = Router.objects.get(id=router_id)
    hashed_filename = create_hashed_file(file, filename)
    url_filename_router = Url_Filename_Router(url=url, filename=hashed_filename, router=router)
    url_filename_router.save()
    scp(
        "/var/www/ternexEnv/ternex/cacheFile/" + hashed_filename,
        str(router),
        "mnt/sda1/cache/" + hashed_filename,
    )
    delete_server_file("/var/www/ternexEnv/ternex/cacheFile/" + hashed_filename)
    return redirect("/router/{}/usb/".format(router_id))


def write_user_tracking_into_log(request: HttpRequest):
    us = Users_now_Stats.objects.filter(owner_router=request.user.email).order_by("date", "time")
    with open("/var/www/ternexEnv/ternex/static/portal/userTrecking/" + request.user.email + ".txt", "w") as f:
        for record in us:
            f.write(
                record.date.strftime("%d.%b.%Y")
                + ", "
                + record.time.strftime("%H:%M:%S")
                + ", IPV6="
                + str(record.router.ipv6)
                + ", MAC="
                + record.mac_user
                + ", Session Duration="
                + str(record.session_duration)
                + ", TX="
                + str(record.tx)
                + ", RX="
                + str(record.rx)
                + "\n"
            )
    return redirect("/static/portal/userTrecking/" + request.user.email + ".txt")


@login_required
def payment(request: HttpRequest):
    return render(
        request,
        "payment.html",
    )


@csrf_exempt
def payment_result(request: HttpRequest):
    if request.method != "POST":
        return HttpResponse("bad sign\n")
    data = {
        "OutSum": request.POST.get("OutSum"),
        "InvId": request.POST.get("InvId"),
        "pass": os.getenv("RKPASS2"),
    }
    SignatureValue = request.POST.get("SignatureValue")
    my_signature = generate_signature(data)
    if SignatureValue != my_signature:
        return HttpResponse("signature is not equal\n")
    user = Payment.objects.get(id=data["InvId"]).email_buyer  # возможно так нельзя
    create_license(user)
    return HttpResponse("OK{}".format(data["InvId"]))


@csrf_exempt
@require_POST
def payment_out(request: HttpRequest):
    if not (request.POST.get("product") and request.POST.get("email")):
        return HttpResponse("no such item")
    product = Product.objects.filter(name=request.POST.get("product"))
    user = Profile.objects.filter(email=request.POST.get("email"))
    if not (product and user):
        return HttpResponse("no such item")
    try:
        rk_json = SettingsFiscalization.objects.get(product=product[0]).get_json()
    except ObjectDoesNotExist:
        return HttpResponse("no such item")  # 404
    payment = Payment(
        product=product[0],
        order_description=product[0].description,
        sum_of_order=product[0].price,
        code_of_goods=product[0].id,
        email_buyer=user[0],
    )
    payment.save()

    data = {
        # MerchantLogin:OutSum:InvId:Receipt:Пароль#1.
        "login": os.getenv("RKLOGIN"),
        "sum_of_order": str(product[0].price),
        "number_of_order": payment.id,
        "receipt": parse.quote(rk_json),
        "pass": os.getenv("RKPASS"),
    }
    signature = generate_signature(data)
    del data["pass"]
    data["signature"] = signature
    data["order_description"] = product[0].description
    data["language"] = "ru"
    data["encoding"] = "utf-8"
    data["email_buyer"] = user[0].email
    return JsonResponse(data)


def generate_signature(data: dict):
    data_str = ""
    for key, val in data.items():
        if key.lower().startswith("shp_"):
            data_str += "{0}={1}:".format(key, val)
            continue
        data_str += "{0}:".format(val)
    return hashsha256(data_str[:-1])
    # data_str = ":".join("{0}".format(val) for key, val in data.items())


@login_required
def payment_expired(request: HttpRequest):
    return render(request, "payment-expired.html")


@csrf_exempt
@login_required
def payment_success(request: HttpRequest):
    return render(
        request,
        "payment-success.html",
    )


def show_map(request: HttpRequest):
    routers = Router.objects.filter(user=request.user.email)
    return render(request, "map.html", {"routers": routers, "test": routers[0].mesh_info})

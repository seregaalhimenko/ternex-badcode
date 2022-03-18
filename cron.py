import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ternex.settings")
import django

django.setup()
import sys
import requests

sys.path.append(r"/var/www/ternexEnv/ternex")
from portal.models import *
from portal.views import create_notification
from django.core.mail import send_mail


def sending_message(recipient, name_router, time, date, ac):
    message = (
        "Ваш роутер, "
        + name_router
        + " изменил свой статус активности.\n "
        + name_router
        + ""
        + ac
        + ".\nПроверка проведена  "
        + time.strftime("%H:%M")
        + " "
        + date.strftime("%d, %B %Y")
    )
    send_mail(
        "Изменение активности вашего роутера",
        message,
        "info@ternex.ru",
        [recipient],
    )
    return message


def scp(user, password, address, path1, path2):
    """
    user - пользователь удаленного устройства
    address - ipv6,ipv4
    path1 - деректория на удаленом устройстве
    path2 - деректория этого устройства
    """
    command = "scp {user}@[{address}]:{path1} {path2}".format(user, address, path1, path2)
    with pexpect.spawn(command) as child:
        try:
            i = child.expect(["Are you sure you want to continue connecting (yes/no)?", "assword:"], timeout=7)
            if i == 0:
                child.sendline("yes")
                child.expect("Password:", timeout=7)
                child.sendline(password)
                child.expect(pexpect.EOF)
            elif i == 1:
                child.sendline(password)
                i = child.expect([pexpect.EOF, "No such file or directory", " Could not"])
                if i == 0:
                    return 1
                if i == 1:
                    return 0
                if i == 2:
                    return 0
        except pexpect.EOF:
            log(scp.__name__, "EOF", comment="")  
            return 0
        except pexpect.TIMEOUT:

            log(scp.__name__, "TIMEOUT", comment="")  
            return 0
    return 1


Routers = Router.objects.all()
for router in Routers:
    if not Profile.objects.filter(email=router.user)[0].sending_data:
        continue
    try:
        r = requests.get("http://[" + str(router) + "]/cgi-bin/status", timeout=24)
        if not router.activity:
            router.activity = True
            router.save()
            message = ""
            if Profile.objects.filter(email=router.user)[0].mailing:
                message = sending_message(
                    recipient=router.user, 
                    name_router=router.name,
                    time=router.state_change_time,
                    date=router.state_change_date,
                    ac=" включен",
                )
                second_emails = SecondEmails.objects.filter(user_main_email=router.user)
                for email in second_emails:
                    sending_message(
                        recipient=email.user_main_email,
                        name_router=router.name,
                        time=router.state_change_time,
                        date=router.state_change_date,
                        ac=" включен",
                    )
            create_notification(router.user, "Изменение активности вашего роутера", message)
    except requests.exceptions.RequestException:
        if router.activity:
            router.activity = False
            router.save()
            message = ""
            if Profile.objects.filter(email=router.user)[0].mailing:
                message = sending_message(
                    recipient=router.user,
                    name_router=router.name,
                    time=router.state_change_time,
                    date=router.state_change_date,
                    ac=" выключен",
                )
                second_emails = SecondEmails.objects.filter(user_main_email=router.user)
                for email in second_emails:
                    sending_message(
                        recipient=email.user_main_email,
                        name_router=router.name,
                        time=router.state_change_time,
                        date=router.state_change_date,
                        ac=" включен",
                    )
            create_notification(router.user, "Изменение активности вашего роутера", message)
    continue

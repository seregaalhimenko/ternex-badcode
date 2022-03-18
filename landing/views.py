from django.shortcuts import render, redirect
from portal.models import Router
from django.core.mail import send_mail


def index(request):
    routers = Router.objects.all()
    return render(request, "landing/index.html", {"routers": routers})


def hotels(request):
    return render(request, "landing/hotels.html")


def franchise(request):
    return render(request, "landing/franchise.html")

def consumers(request):
    return render(request, "landing/consumers.html")


def landing_form(request):
    send_mail(
        "ternex:Заказ",
        (
            "email:{}\n".format(request.POST["email"])
            + "phone:{}\n".format(request.POST["phone"])
            + "text:{}\n".format(request.POST["text"])
        ),
        "info@ternex.ru",
        ["info@ternex.ru"],
    )
    return redirect("https://www.ternex.ru/")

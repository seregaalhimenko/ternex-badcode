import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ternex.settings")
import django

django.setup()
import sys
import requests

sys.path.append(r"/var/www/ternexEnv/ternex")
from portal.models import *


user = sys.argv[1]
Routers = Router.objects.filter(user=user)
for router in Routers:
    try:
        r = requests.get("http://[" + str(router) + "]/cgi-bin/status", timeout=24)
        if not router.activity:
            router.activity = True
            router.save()
    except requests.exceptions.RequestException:
        if router.activity:
            router.activity = False
            router.save()
    continue

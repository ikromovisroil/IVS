"""
Joriy so'rovni bajarayotgan xodimni thread-local orqali saqlaydi, shunda
signal handlerlar (post_save/post_delete) request obyektiga to'g'ridan-to'g'ri
kira olmasa ham, kim haqiqatda amal qilayotganini bilishi mumkin - modelning
sender/receiver/employee kabi maydonlarini taxmin qilishga hojat qolmaydi.
"""
from asgiref.local import Local

# asgiref.local.Local - Django ning o'zi ham ichida ishlatadigan xavfsiz
# thread/async-local. Oddiy threading.local() dan farqi: sync (WSGI) serverda
# ham, async (ASGI) serverda ham to'g'ri ishlaydi.
_state = Local()


def set_current_employee(employee):
    _state.employee = employee
    _state.signal_logged = False


def get_current_employee():
    return getattr(_state, "employee", None)


def mark_signal_logged():
    _state.signal_logged = True


def was_signal_logged():
    return getattr(_state, "signal_logged", False)


def clear():
    _state.employee = None
    _state.signal_logged = False


def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

"""
Joriy so'rovni bajarayotgan xodimni thread-local orqali saqlaydi, shunda
signal handlerlar (post_save/post_delete) request obyektiga to'g'ridan-to'g'ri
kira olmasa ham, kim haqiqatda amal qilayotganini bilishi mumkin - modelning
sender/receiver/employee kabi maydonlarini taxmin qilishga hojat qolmaydi.
"""
import ipaddress

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


def set_current_request(request):
    """So'rov IP, usul va yo'lini saqlaydi: signal yozuvlari (Order/Deed) ham shularni jurnalga yozadi."""
    ip = get_client_ip(request)
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        ip = None  # soxta/noto'g'ri sarlavha: inet ustuniga yozilsa tranzaksiyani buzadi
    _state.request_info = {
        "ip": ip,
        "method": request.method,
        "path": request.path[:255],
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300],
    }


def get_current_request_info():
    return getattr(_state, "request_info", None) or {}


def mark_signal_logged():
    _state.signal_logged = True


def was_signal_logged():
    return getattr(_state, "signal_logged", False)


def clear():
    _state.employee = None
    _state.signal_logged = False
    _state.request_info = None


def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

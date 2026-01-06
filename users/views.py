from django.contrib.auth import logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages


def login_view(request):
    if request.method == "POST":

        username = request.POST.get("username", "")

        # 🔹 username'ni katta-kichik harfdan mustaqil qidiramiz
        try:
            user_obj = User.objects.get(username__iexact=username)

            # POST ni yozib bo‘ladigan qilib nusxalaymiz
            request.POST = request.POST.copy()

            # 🔹 formaga real username'ni joylaymiz
            request.POST["username"] = user_obj.username

        except User.DoesNotExist:
            pass

        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect(reverse("profil"))
        else:
            messages.error(request, "Foydalanuvchi nomi yoki parol noto‘g‘ri!")
    else:
        form = AuthenticationForm()

    return render(request, "users/login.html", {"form": form})





def logout_view(request):
    auth_logout(request)
    return redirect("login")


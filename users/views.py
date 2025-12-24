from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.forms import AuthenticationForm

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect(reverse("profil"))
        else:
            messages.error(request,"Foydalanuvchi nomi yoki parol noto‘g‘ri!")
    else:
        form = AuthenticationForm()
    return render(request, "users/login.html", {"form": form})




def logout_view(request):
    auth_logout(request)
    return redirect("login")


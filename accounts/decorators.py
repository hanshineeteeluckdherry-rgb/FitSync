from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import User


def role_required(*allowed_roles):
    """Small readable role check for protected FitSync pages."""

    def decorator(view_function):
        @wraps(view_function)
        @login_required
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_active:
                logout(request)
                messages.error(request, "Your account is inactive.")
                return redirect("accounts:login")

            # Django superusers are always treated as FitSync administrators.
            if request.user.is_superuser or request.user.role in allowed_roles:
                return view_function(request, *args, **kwargs)

            return render(request, "accounts/access_denied.html", status=403)

        return wrapped_view

    return decorator


admin_required = role_required(User.Role.ADMIN)
member_required = role_required(User.Role.MEMBER)
staff_required = role_required(User.Role.STAFF, User.Role.ADMIN)
coach_required = role_required(User.Role.COACH)

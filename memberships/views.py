from datetime import date, timedelta

from django.contrib import messages
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, Sum, Value, When
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import admin_required, member_required

from .forms import MembershipPackageForm, SimulatedPaymentForm
from .models import Membership, MembershipPackage, Payment


def _active_packages():
    # Keep the Figma plan order instead of sorting by price.
    return MembershipPackage.objects.filter(is_active=True).annotate(
        plan_order=Case(
            When(slug="starter", then=Value(1)),
            When(slug="premium", then=Value(2)),
            When(slug="elite", then=Value(3)),
            When(slug="student", then=Value(4)),
            default=Value(99),
            output_field=IntegerField(),
        )
    ).order_by("plan_order", "name")


def _current_for(user):
    membership = (
        Membership.objects.filter(member=user, status=Membership.Status.ACTIVE)
        .select_related("package")
        .order_by("-end_date")
        .first()
    )
    if membership and membership.end_date < date.today():
        membership.status = Membership.Status.EXPIRED
        membership.save(update_fields=["status"])
        return None
    return membership


def public_packages(request):
    return render(request, "memberships/public_packages.html", {"packages": _active_packages()})


def public_package_detail(request, slug):
    package = get_object_or_404(MembershipPackage, slug=slug, is_active=True)
    return render(request, "memberships/public_package_detail.html", {"package": package})


def auth_required(request, package_id):
    package = get_object_or_404(MembershipPackage, pk=package_id, is_active=True)
    if request.user.is_authenticated:
        return redirect("memberships:checkout", package_id=package.pk)

    next_url = f"/memberships/member/checkout/{package.pk}/"
    return render(
        request,
        "memberships/auth_required.html",
        {"package": package, "next_url": next_url},
    )


@member_required
def member_packages(request):
    return render(
        request,
        "memberships/member_packages.html",
        {
            "packages": _active_packages(),
            "current_membership": _current_for(request.user),
            "active_sidebar": "membership",
            "membership_tab": "plans",
        },
    )


@member_required
def current_membership(request):
    membership = _current_for(request.user)
    return render(
        request,
        "memberships/current_membership.html",
        {
            "membership": membership,
            "active_sidebar": "membership",
            "membership_tab": "current",
        },
    )


@member_required
def membership_history(request):
    memberships = Membership.objects.filter(member=request.user).select_related("package")
    return render(
        request,
        "memberships/membership_history.html",
        {
            "memberships": memberships,
            "active_sidebar": "membership",
            "membership_tab": "history",
        },
    )


@member_required
def payment_history(request):
    payments = Payment.objects.filter(member=request.user).select_related("package", "membership")
    return render(
        request,
        "memberships/payment_history.html",
        {"payments": payments, "active_sidebar": "payments"},
    )


@member_required
@transaction.atomic
def checkout(request, package_id):
    package = get_object_or_404(MembershipPackage, pk=package_id, is_active=True)
    form = SimulatedPaymentForm(request.POST or None, initial={"payer_name": request.user.get_full_name()})

    if request.method == "POST" and form.is_valid():
        failed = form.cleaned_data["simulate_failure"]
        payment = Payment.objects.create(
            member=request.user,
            package=package,
            amount=package.price,
            payment_method=form.cleaned_data["payment_method"],
            status=Payment.Status.FAILED if failed else Payment.Status.SUCCESS,
        )

        if failed:
            messages.error(request, "The simulated payment failed. No membership was activated.")
            return redirect("memberships:payment_failed", payment_id=payment.pk)

        old_membership = _current_for(request.user)
        if old_membership:
            old_membership.status = Membership.Status.CANCELLED
            old_membership.save(update_fields=["status"])

        start_date = date.today()
        membership = Membership.objects.create(
            member=request.user,
            package=package,
            start_date=start_date,
            end_date=start_date + timedelta(days=30 * package.duration_months),
            status=Membership.Status.ACTIVE,
        )
        payment.membership = membership
        payment.save(update_fields=["membership"])
        messages.success(request, "Payment successful. Your membership is now active.")
        return redirect("memberships:payment_success", payment_id=payment.pk)

    return render(
        request,
        "memberships/checkout.html",
        {"package": package, "form": form, "active_sidebar": "membership"},
    )


@member_required
def renew_membership(request, membership_id):
    membership = get_object_or_404(Membership, pk=membership_id, member=request.user)
    if request.method != "POST":
        return redirect("memberships:current_membership")
    return redirect("memberships:checkout", package_id=membership.package_id)


@member_required
def payment_success(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related("package", "membership"),
        pk=payment_id,
        member=request.user,
        status=Payment.Status.SUCCESS,
    )
    return render(
        request,
        "memberships/payment_success.html",
        {"payment": payment, "active_sidebar": "membership"},
    )


@member_required
def payment_failed(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related("package"),
        pk=payment_id,
        member=request.user,
        status=Payment.Status.FAILED,
    )
    return render(
        request,
        "memberships/payment_failed.html",
        {"payment": payment, "active_sidebar": "membership"},
    )


@member_required
def receipt(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related("package", "membership"),
        pk=payment_id,
        member=request.user,
        status=Payment.Status.SUCCESS,
    )
    return render(request, "memberships/receipt.html", {"payment": payment})


@admin_required
def admin_package_list(request):
    packages = MembershipPackage.objects.all()
    return render(
        request,
        "memberships/admin/package_list.html",
        {"packages": packages, "active_sidebar": "memberships"},
    )


@admin_required
def admin_package_create(request):
    form = MembershipPackageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Membership package created.")
        return redirect("memberships:admin_package_list")
    return render(
        request,
        "memberships/admin/package_form.html",
        {"form": form, "page_name": "Create Package", "active_sidebar": "memberships"},
    )


@admin_required
def admin_package_edit(request, package_id):
    package = get_object_or_404(MembershipPackage, pk=package_id)
    form = MembershipPackageForm(request.POST or None, instance=package)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Membership package updated.")
        return redirect("memberships:admin_package_list")
    return render(
        request,
        "memberships/admin/package_form.html",
        {"form": form, "page_name": "Edit Package", "active_sidebar": "memberships"},
    )


@admin_required
def admin_package_toggle(request, package_id):
    package = get_object_or_404(MembershipPackage, pk=package_id)
    if request.method == "POST":
        package.is_active = not package.is_active
        package.save(update_fields=["is_active"])
        messages.success(request, "Package availability updated.")
    return redirect("memberships:admin_package_list")


@admin_required
def admin_membership_list(request):
    memberships = Membership.objects.select_related("member", "package")
    status = request.GET.get("status", "")
    if status:
        memberships = memberships.filter(status=status)
    query = request.GET.get("q", "").strip()
    if query:
        memberships = memberships.filter(
            Q(member__first_name__icontains=query)
            | Q(member__last_name__icontains=query)
            | Q(member__email__icontains=query)
        )
    return render(
        request,
        "memberships/admin/membership_list.html",
        {
            "memberships": memberships,
            "status_filter": status,
            "query": query,
            "status_choices": Membership.Status.choices,
            "active_sidebar": "memberships",
        },
    )


@admin_required
def admin_payment_list(request):
    payments = Payment.objects.select_related("member", "package")
    status = request.GET.get("status", "")
    if status:
        payments = payments.filter(status=status)
    return render(
        request,
        "memberships/admin/payment_list.html",
        {
            "payments": payments,
            "status_filter": status,
            "status_choices": Payment.Status.choices,
            "active_sidebar": "payments",
        },
    )


@admin_required
def admin_payment_detail(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related("member", "package", "membership"),
        pk=payment_id,
    )
    return render(
        request,
        "memberships/admin/payment_detail.html",
        {"payment": payment, "active_sidebar": "payments"},
    )


@admin_required
def admin_membership_report(request):
    active_count = Membership.objects.filter(status=Membership.Status.ACTIVE).count()
    expired_count = Membership.objects.filter(status=Membership.Status.EXPIRED).count()
    cancelled_count = Membership.objects.filter(status=Membership.Status.CANCELLED).count()
    successful = Payment.objects.filter(status=Payment.Status.SUCCESS)
    package_counts = (
        Membership.objects.values("package__name")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    context = {
        "active_count": active_count,
        "expired_count": expired_count,
        "cancelled_count": cancelled_count,
        "successful_payments": successful.count(),
        "payment_total": successful.aggregate(total=Sum("amount"))["total"] or 0,
        "package_counts": package_counts,
        "active_sidebar": "reports",
    }
    return render(request, "memberships/admin/report.html", context)

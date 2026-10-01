from django.shortcuts import render

# Create your views here.
def ourteam(request):
    return render(request, "ourteam/ourteam.html")
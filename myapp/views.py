from django.shortcuts import render,HttpResponse

# Create your views here.
def index(request):
    return render(request, 'index.html')
    return HttpResponse("This is the homepage.")
    

def about(request):
    return HttpResponse("This is the About Us Page.")   


def services(request):
    return HttpResponse("These are our Services.")    

def contacts(request):
    return HttpResponse("Contact us for further query.")    
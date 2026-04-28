import io
from django.shortcuts import render
import pandas as pd

def index(request):
    context = {}
    if request.method == 'POST':
        csv_file = request.FILES['csv_file'].read()
        csv_file = pd.read_csv(io.BytesIO(csv_file))
        numeri = csv_file.to_dict()
        context = {'numeri': numeri}
    return render(request, "calcolatore/index.html", context)
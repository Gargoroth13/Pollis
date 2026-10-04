from django.contrib import admin

from .models import City, Lot, Neighborhood, ResourceDeposit, State

for model in (State, City, Neighborhood, Lot, ResourceDeposit):
    admin.site.register(model)

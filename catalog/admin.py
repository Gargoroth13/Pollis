from django.contrib import admin

from .models import FoodProfile, Product, Recipe, RecipeInput

for model in (Product, Recipe, RecipeInput, FoodProfile):
    admin.site.register(model)

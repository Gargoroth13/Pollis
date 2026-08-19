from django import forms

from .models import Cargo, Empresa


class CriarEmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ["nome", "setor"]


class CriarCargoForm(forms.ModelForm):
    class Meta:
        model = Cargo
        fields = ["titulo", "categoria_habilidade", "nivel_minimo", "salario"]

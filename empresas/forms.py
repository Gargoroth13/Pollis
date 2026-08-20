from django import forms

from .models import Cargo, Empresa


class CriarEmpresaForm(forms.ModelForm):
    """
    Os 3 campos de classificação (terreno, tipo_industria,
    especializacao_servico) ficam todos como opcionais aqui — o
    `Empresa.clean()` no model é quem garante que só o certo pro `tipo`
    escolhido foi preenchido. O template usa um pouco de JS pra mostrar
    só o campo relevante, mas a validação de verdade é sempre no model.
    """

    class Meta:
        model = Empresa
        fields = ["nome", "tipo", "terreno", "tipo_industria", "especializacao_servico"]

    def clean(self):
        cleaned_data = super().clean()
        # Roda a validação do model aqui pra erro de classificação errada
        # aparecer como erro de formulário, não como 500.
        instancia_temporaria = Empresa(
            tipo=cleaned_data.get("tipo"),
            terreno=cleaned_data.get("terreno"),
            tipo_industria=cleaned_data.get("tipo_industria"),
            especializacao_servico=cleaned_data.get("especializacao_servico"),
        )
        try:
            instancia_temporaria.clean()
        except forms.ValidationError as erro:
            if hasattr(erro, "error_dict"):
                for campo, erros in erro.error_dict.items():
                    for e in erros:
                        self.add_error(campo, e)
            else:
                raise
        return cleaned_data


class CriarCargoForm(forms.ModelForm):
    class Meta:
        model = Cargo
        fields = ["titulo", "skill_relevante", "nivel_minimo", "salario"]

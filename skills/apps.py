from django.apps import AppConfig


class SkillsConfig(AppConfig):
    name = "skills"

    def ready(self):
        from players import hooks
        from . import services, tick_handlers  # noqa: F401  (registra o handler diário)

        # Skills reage às ações do players DENTRO de perform_action: nenhum caminho paralelo.
        hooks.register_action_hook("skills", services.on_action)
        hooks.register_player_created_hook("skills", services.on_player_created)

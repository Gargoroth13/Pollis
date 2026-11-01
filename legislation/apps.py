from django.apps import AppConfig


class LegislationConfig(AppConfig):
    name = "legislation"

    def ready(self):
        from . import process, registration

        registration.register()      # ações no Action Registry
        process.register_tick()      # avanço do calendário legislativo (design/07 §07.6, §07.16)

from history.audit import audit_history
from history.views import clear_ref_resolvers


class AuditMixin:
    """Ao fim de TODO teste o histórico está íntegro (a menos que o teste adultere de propósito)."""

    audit_history_at_end = True

    def setUp(self):
        super().setUp()
        self.addCleanup(clear_ref_resolvers)
        self.addCleanup(self._audit_history)

    def _audit_history(self):
        if self.audit_history_at_end:
            report = audit_history()
            self.assertTrue(report.ok, report.findings)

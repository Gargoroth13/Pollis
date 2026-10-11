from django.test import TestCase

from catalog.loader import sync_catalog


class CatalogTestCase(TestCase):
    """Banco com o catálogo do 22 carregado (uma vez por classe)."""

    @classmethod
    def setUpTestData(cls):
        sync_catalog()

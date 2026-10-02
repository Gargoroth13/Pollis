from django.db import IntegrityError, transaction

from skills import services
from skills.constants import LABELS, SKILLS, Skill
from skills.models import PlayerSkill

from .base import D, INT, PHY, CHA, SkillTestCase


class ThreeSkillsTests(SkillTestCase):
    def test_exactly_three_skills(self):
        self.assertEqual([s.value for s in SKILLS], ["intelligence", "physical", "charisma"])
        self.assertEqual(set(LABELS.values()), {"Inteligência", "Físico", "Carisma"})

    def test_new_player_has_exactly_three_skill_rows(self):
        rows = PlayerSkill.objects.filter(player=self.player)
        self.assertEqual(sorted(rows.values_list("skill", flat=True)), ["charisma", "intelligence", "physical"])

    def test_initial_level_is_neutral_zero_until_the_birth_context_exists(self):
        """01 §1: o nível inicial vem do contexto de nascimento (sistema ainda inexistente)."""
        self.assertEqual(self.levels(), {INT: 0, PHY: 0, CHA: 0})

    def test_a_fourth_skill_cannot_exist(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlayerSkill.objects.create(player=self.player, skill="industry", level=0)

    def test_one_row_per_player_and_skill(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlayerSkill.objects.create(player=self.player, skill="physical", level=1)

    def test_level_cannot_be_negative(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlayerSkill.objects.filter(player=self.player, skill="physical").update(level=-1)

    def test_initial_levels_come_from_providers_added_to_the_baseline(self):
        services.register_initial_level_provider("birth", lambda p: {"physical": D(10), "charisma": D("2.5")})
        other = self.new_player("born_rich")
        self.assertEqual(self.levels(other), {INT: 0, PHY: 10, CHA: D("2.5")})
        self.assertEqual(self.levels(), {INT: 0, PHY: 0, CHA: 0})   # quem nasceu antes não muda

    def test_provider_names_are_unique(self):
        services.register_initial_level_provider("birth", lambda p: {})
        with self.assertRaises(ValueError):
            services.register_initial_level_provider("birth", lambda p: {})

    def test_missing_rows_are_repaired_on_read(self):
        PlayerSkill.objects.filter(player=self.player, skill="charisma").delete()
        self.assertEqual(set(self.levels()), {INT, PHY, CHA})

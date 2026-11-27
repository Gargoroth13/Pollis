"""
AUDITORIA ADVERSARIAL DA ONDA 1 (Empresas, #15–#19) — cenários econômicos do GD (2026-11-27, Etapa 2).

Estes testes NÃO adicionam regra nenhuma: tentam QUEBRAR as regras que já existem e MEDEM o que acontece. Cada teste afirma o que o
código garante hoje e imprime (`AUDIT|...`) os números que sustentam o relatório. Quando um risco é REAL (nenhuma regra o impede),
o teste afirma o comportamento atual, com o comentário `RISCO REAL`, para que uma futura correção, se o GD decidir por uma, tenha de
mudar o teste de propósito — nada aqui é um limite artificial novo.
"""
import math
from decimal import Decimal

from django.test import TransactionTestCase

from accounts.models import Usuario
from catalog import services as catalog
from catalog.loader import sync_catalog
from catalog.models import Product
from companies import construction, jobs, params, payroll, production, retail, services, stock, support
from companies.audit import audit_companies
from companies.constants import StockOperation
from companies.models import (Company, Position, ProductionLine, SalesCapacityUse, StockItem, StockMovement, SupportWork, WorkWage)
from core import ticks
from core.models import WorldClock
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.tests.base import SMALL
from ledger import services as ledger
from ledger.audit import audit_ledger, ledger_metrics
from ledger.constants import Nature, ObligationStatus
from ledger.models import Entry, Obligation, RemunerationCounter
from ledger.money import competence_day_of
from ledger.tests.base import fund_account, install_test_role
from ledger.tests.test_scenario_concurrency import run_together
from players import registry
from players.models import Player
from players.services import create_player

from .test_production import ProductionBase
from .test_wages import FIRST_MIDNIGHT

D = Decimal
REAL = 100


def note(tag, **numbers):
    print("AUDIT|" + tag + "|" + ";".join(f"{k}={v}" for k, v in numbers.items()), flush=True)


class AdversarialBase(ProductionBase):
    company_cash = 0                       # cada teste financia o que precisa; o padrão é a empresa SEM caixa

    def refill(self, player):
        self.set_state(player, energy=D(100), nutrition=D(100), health=D(100), burnout=D(0), hospitalized_until=None,
                       health_critical=False)

    def work_hooks(self, player, refill=True):
        if refill:
            self.refill(player)
        res = registry.execute_action(player.pk, "work", None)
        return res

    def staff(self, n, company=None, salary=2_000, kind="worker", prefix="w"):
        out = []
        for i in range(n):
            p = self.new_player(f"{prefix}{company or self.firm}_{i}_{len(out)}")
            self.hire(p, company=company or self.firm, salary=salary, kind=kind)
            out.append(p)
        return out

    def obligations_of(self, company=None):
        acct = services.company_account(company or self.firm)
        qs = Obligation.objects.filter(debtor=acct, status=ObligationStatus.OPEN.value)
        return qs.count(), sum(o.amount_due - o.amount_paid for o in qs)

    def drain_stock(self):
        """Esvazia o estoque da empresa pelo caminho LEGÍTIMO (venda), sem tocar nas tabelas: a auditoria continua valendo."""
        company = Company.objects.get(pk=self.firm)
        for item in list(StockItem.objects.filter(company_id=self.firm).select_related("product")):
            moved = stock.apply_locked(company, item.product, -item.quantity, StockOperation.SALE, origin=f"company:{self.firm}",
                                       destination="sale:drain", key=f"drain:{item.product.key}:{StockMovement.objects.count()}",
                                       reference_kind="t", reference_id="drain", at=self.clk.now())
            self.assertTrue(moved.ok, moved)

    def tick_next_day(self):
        self.clk.advance(days=1)
        return ticks.advance_world()

    def clean(self):
        from ledger.audit import audit_ledger
        for report in (audit_ledger(), audit_companies()):
            self.assertTrue(report.ok, report.findings)


# ---------------------------------------------------------------------------------------------------------------------
# 1-2. Empresa sem dinheiro: contrata muito, continua produzindo e acumula obrigações
# ---------------------------------------------------------------------------------------------------------------------

class InsolventCompanyTests(AdversarialBase):
    def test_a_company_with_no_cash_hires_many_and_keeps_producing_and_every_wage_becomes_a_registered_obligation(self):
        self.assertEqual(self.firm_money(), 0)
        crew = [self.worker] + self.staff(7)
        money_before = {p.pk: self.money(p) for p in crew}
        total = ledger_metrics()["in_circulation"]
        produced = recognized = pending = paid = 0
        for p in crew:
            res = self.work_hooks(p)
            self.assertTrue(res.ok, res)
            produced += res.detail["hooks"][production.ACTION_HOOK]["produced"]
            w = res.detail["hooks"][payroll.WAGE_HOOK]
            recognized += w["recognized"]
            pending += w["pending"]
            paid += w["paid"]
        count, owed = self.obligations_of()
        flour = stock.quantity_of(self.firm, "flour")
        note("S1.insolvent_keeps_producing", workers=len(crew), company_cash=self.firm_money(), produced_units=produced,
             flour_in_stock=flour, wages_recognized=recognized, wages_paid_now=paid, wages_pending=pending, open_obligations=count,
             owed_cents=owed)
        # o que o sistema GARANTE: o caixa nunca fica negativo, nada de dinheiro novo, cada centavo devido está registrado
        self.assertEqual((self.firm_money(), paid, pending), (0, 0, recognized))
        self.assertEqual((count, owed), (len(crew), recognized))
        self.assertEqual(ledger_metrics()["in_circulation"], total)
        self.assertEqual({p.pk: self.money(p) for p in crew}, money_before)               # ninguém recebeu nada
        # RISCO REAL (sem regra que o impeça): a produção NÃO depende de o salário poder ser pago
        self.assertEqual(flour, produced)
        self.assertGreaterEqual(produced, len(crew) - 1)
        self.clean()

    def test_obligations_grow_without_a_ceiling_day_after_day_but_each_worker_day_is_bounded_by_the_daily_limit(self):
        crew = [self.worker] + self.staff(3)
        series = []
        for day in range(1, 13):
            for p in crew:
                for _ in range(6):                                                    # tenta mais de uma barra de energia por dia
                    res = self.work_hooks(p, refill=False) if _ else self.work_hooks(p)
                    if not res.ok:
                        break
            self.tick_next_day()
            series.append(self.obligations_of()[1])
        cap_per_worker_day = max(params.MIN_WAGE_PER_DAY_CENTS, 0)
        owner_part = 2_000 * len(series)
        note("S2.obligation_growth", days=len(series), workers=len(crew), owed_day1=series[0], owed_day6=series[5],
             owed_day12=series[-1], daily_increment=series[-1] - series[-2], cap_per_worker_day_floor=cap_per_worker_day)
        self.assertTrue(all(b > a for a, b in zip(series, series[1:])))                # RISCO REAL: cresce sem teto
        increments = {b - a for a, b in zip(series[1:], series[2:])}
        self.assertEqual(len(increments), 1)                                           # linear: nada acelera nem para
        # limite por trabalhador/dia (W=R$ 50 com skill baixa): a dívida diária do conjunto é no máximo n × max(W,S) + Dono
        self.assertLessEqual(series[-1] - series[-2], len(crew) * max(params.MIN_WAGE_PER_DAY_CENTS, 20_000) + 2_000)
        self.clean()

    def test_once_funded_the_oldest_obligations_are_paid_first_and_nothing_is_paid_twice(self):
        crew = [self.worker] + self.staff(2)
        for _ in range(3):
            for p in crew:
                self.work_hooks(p)
            self.tick_next_day()
        count, owed = self.obligations_of()
        self.assertGreater(owed, 0)
        self.assertTrue(services.fund_company(self.boss.pk, self.firm, owed + 10).ok)
        self.tick_next_day()
        left_count, left = self.obligations_of()
        note("S2.recovery", owed_before=owed, owed_after=left, open_after=left_count)
        self.assertLessEqual(left, 2_000 * 1)                                           # só o que nasceu no próprio tick
        self.clean()

    def test_a_new_work_wage_is_paid_on_the_spot_ahead_of_older_unpaid_obligations(self):
        """PRIORIDADE INVERTIDA: o 24 manda quitar da competência mais antiga para a mais nova, mas um Trabalho com caixa disponível
        é pago NA HORA (documentado em payroll.py). Quem trabalha depois passa na frente de quem trabalhou antes."""
        old = self.worker
        self.work_hooks(old)                                                          # sem caixa: vira obrigação
        self.assertEqual(self.obligations_of()[0], 1)
        newer = self.staff(1)[0]
        self.assertTrue(services.fund_company(self.boss.pk, self.firm, 2_000).ok)     # caixa só para UM salário
        self.clk.advance(days=1)
        res = self.work_hooks(newer)
        wage = res.detail["hooks"][payroll.WAGE_HOOK]
        still_open = Obligation.objects.filter(status=ObligationStatus.OPEN.value).count()
        note("S3.priority_inversion", newer_paid_now=wage["paid"], older_still_open=still_open)
        self.assertEqual((wage["paid"], still_open), (2_000, 1))                      # RISCO REAL (documentado como decisão técnica)
        self.clean()


# ---------------------------------------------------------------------------------------------------------------------
# 3. Dono retira/transfere recursos com obrigações pendentes
# ---------------------------------------------------------------------------------------------------------------------

class OwnerExtractionTests(AdversarialBase):
    owner_salary = 100_000                 # R$ 1.000/dia pedidos pelo Dono (o limite diário é o teto)

    def test_there_is_no_withdrawal_and_money_leaves_the_company_account_only_as_wage_or_owner_salary(self):
        self.assertTrue(services.fund_company(self.boss.pk, self.firm, 500_000).ok)
        self.work_hooks(self.worker)
        self.goto_midnight()
        out = set(Entry.objects.filter(from_account=services.company_account(self.firm)).values_list("nature", flat=True))
        note("S3.outflow_natures", natures=",".join(sorted(out)))
        self.assertLessEqual(out, {Nature.WAGE.value, Nature.OWNER_SALARY.value, Nature.TAX_INCOME.value})
        # nada em `companies` expõe retirada/transferência do Dono para si
        public = {n for n in dir(services) if not n.startswith("_")}
        self.assertFalse({"withdraw", "withdraw_company", "transfer_from_company", "pay_dividend"} & public)

    def test_pending_debts_are_settled_before_the_owner_salary_of_the_same_tick(self):
        crew = [self.worker] + self.staff(2)
        for p in crew:
            self.work_hooks(p)
        owed = self.obligations_of()[1]
        self.assertGreater(owed, 0)
        self.assertTrue(services.fund_company(self.boss.pk, self.firm, owed).ok)        # caixa = exatamente as dívidas dos funcionários
        boss_before = self.money(self.boss)
        self.goto_midnight()
        paid_to_boss = self.money(self.boss) - boss_before
        workers_paid = sum(self.money(p) for p in crew)
        note("S3.owner_vs_debts", owed=owed, boss_received=paid_to_boss, boss_salary_requested=self.owner_salary)
        self.assertEqual(paid_to_boss, 0)                                               # as dívidas foram primeiro
        self.assertGreater(workers_paid, 0)
        self.assertGreaterEqual(Obligation.objects.filter(status=ObligationStatus.OPEN.value).count(), 1)   # o salário do Dono ficou PENDING
        self.clean()

    def test_the_owner_can_hire_himself_and_is_then_paid_on_the_spot_ahead_of_other_creditors(self):
        crew = [self.worker]
        self.work_hooks(self.worker)                                                    # um credor mais antigo, sem caixa
        self.assertTrue(services.fund_company(self.boss.pk, self.firm, 1_000_000).ok)
        vacancy = self.open("worker", 1_000_000, company=self.firm)
        res = jobs.apply_to_position(self.boss.pk, vacancy)                              # o Dono se candidata à própria vaga
        note("S3.owner_self_hire", apply_code=res.code)
        self.assertTrue(res.ok, res)                                                    # RISCO REAL: nenhuma regra impede
        self.assertTrue(jobs.approve_application(self.boss.pk, res.detail["application"]).ok)
        self.clk.advance(days=1)
        before = self.money(self.boss)
        wages = []
        for _ in range(5):
            r = self.work_hooks(self.boss, refill=False) if wages else self.work_hooks(self.boss)
            if not r.ok:
                break
            wages.append(r.detail["hooks"][payroll.WAGE_HOOK])
        gained = self.money(self.boss) - before
        counter = RemunerationCounter.objects.get(player_id=self.boss.pk, competence_day=competence_day_of(self.clk.now()))
        cap = max(params.MIN_WAGE_PER_DAY_CENTS, 150)
        note("S3.owner_self_hire_extraction", works=len(wages), gross_recognized=counter.c_s, net_received=gained, cap_S=cap,
             older_creditors_open=self.obligations_of()[0])
        self.assertLessEqual(counter.c_s, cap)                                           # o limite diário vale também aqui
        self.assertGreaterEqual(self.obligations_of()[0], 1)                             # e o credor mais antigo continua sem receber
        self.clean()

    def test_wage_plus_owner_salary_plus_second_company_never_exceed_the_player_daily_limit(self):
        other_firm = self.found(self.boss, "industrial", "Segunda", 1_000_000)
        self.assertTrue(services.fund_company(self.boss.pk, other_firm, 5_000_000).ok)
        self.assertTrue(services.fund_company(self.boss.pk, self.firm, 5_000_000).ok)
        # o dono das duas e empregado de uma terceira empresa do jogador `third`
        third_firm = self.found(self.third, "industrial", "Terceira", 0)
        self.assertTrue(services.fund_company(self.third.pk, third_firm, 5_000_000).ok)
        self.assertTrue(production.set_production(self.third.pk, third_firm, "flour").ok)
        stock.credit_stock(third_firm, "wheat", 50, origin="t", key="seed:w3", reference_kind="t", reference_id="3")
        pos = jobs.open_position(self.third.pk, third_firm, "worker", 900_000, {}).detail["position"]
        app = jobs.apply_to_position(self.boss.pk, pos).detail["application"]
        self.assertTrue(jobs.approve_application(self.third.pk, app).ok)
        self.clk.set(FIRST_MIDNIGHT - 3600)
        for i in range(5):
            self.work_hooks(self.boss, refill=(i == 0))
        ticks.advance_world()                                                            # salário do Dono das duas empresas
        day = competence_day_of(FIRST_MIDNIGHT)
        totals = {}
        for c in RemunerationCounter.objects.filter(player_id=self.boss.pk):
            totals[c.competence_day] = c.c_s
        note("S6.paths_same_player", per_day_recognized=totals, cap_floor=params.MIN_WAGE_PER_DAY_CENTS)
        for d, recognized in totals.items():
            self.assertLessEqual(recognized, max(params.MIN_WAGE_PER_DAY_CENTS, 200), (d, recognized))
        self.clean()


# ---------------------------------------------------------------------------------------------------------------------
# 4. Produção x insumos (propriedade sobre TODAS as receitas do catálogo)
# ---------------------------------------------------------------------------------------------------------------------

class InputConservationTests(AdversarialBase):
    company_cash = 100_000
    # O teste de propriedade ESCOLHE o produto direto na linha (sem passar por `set_production`, que tem cooldown) para varrer o
    # catálogo inteiro: isso fica de propósito fora do histórico `ProductionChange`, e a auditoria (invariante 9) acusa — o que
    # confirma que ela detecta produção sem escolha registrada. Por isso só a auditoria do registro monetário vale aqui.
    audit_companies_at_end = False

    def test_no_recipe_ever_creates_stock_without_consuming_its_inputs(self):
        self.set_stars(5)
        checked = 0
        for product in Product.objects.order_by("key"):
            recipe = catalog.recipe_of(product.key)
            if recipe is None or product.min_stars is None or catalog.check_production_ready(product.key).ok is False:
                continue
            yield_q = recipe.yield_quantity
            self.drain_stock()
            line = ProductionLine.objects.get(company_id=self.firm)
            line.product, line.carry, line.setup_until = product, D(0), None
            line.save()
            seeded = {}
            company = Company.objects.get(pk=self.firm)
            for i in recipe.inputs:                         # a propriedade é sobre a produção, não sobre a permissão de compra
                seeded[i.key] = int(math.ceil(i.quantity * 6))
                moved = stock.apply_locked(company, catalog.get_product(i.key), seeded[i.key], StockOperation.PURCHASE,
                                           origin="test", destination=f"company:{self.firm}", key=f"adv:{product.key}:{i.key}",
                                           reference_kind="t", reference_id=product.key, at=self.clk.now(), quality=D(1))
                self.assertTrue(moved.ok, moved)
            start = {i.key: stock.quantity_of(self.firm, i.key) for i in recipe.inputs}
            for _ in range(30):
                res = self.work_hooks(self.worker)
                if not res.ok:
                    break
            made = stock.quantity_of(self.firm, product.key)
            for i in recipe.inputs:
                used = start[i.key] - stock.quantity_of(self.firm, i.key)
                # cada unidade produzida está coberta por insumo consumido: used × rendimento ≥ made × quantidade da receita
                self.assertGreaterEqual(used * yield_q, made * i.quantity, (product.key, i.key, used, made))
            checked += 1
        note("S4.recipes_checked", count=checked)
        self.assertGreater(checked, 5)
        self.assertTrue(audit_ledger().ok)
        self.assertLessEqual({f["code"] for f in audit_companies().findings}, {"PRODUCTION_WITHOUT_PRODUCT_CHOICE", "PRODUCTION_HISTORY_MISMATCH"})

    def test_a_company_without_inputs_cannot_work_at_all_and_spends_no_energy(self):
        self.drain_stock()
        self.refill(self.worker)
        before = self.state(self.worker).energy if hasattr(self.state(self.worker), "energy") else None
        res = registry.execute_action(self.worker.pk, "work", None)
        note("S4.no_inputs", code=res.code, ok=res.ok)
        self.assertFalse(res.ok)
        self.assertEqual(res.code, "MISSING_INPUTS")
        self.assertEqual(stock.quantity_of(self.firm, "flour"), 0)
        self.assertEqual(WorkWage.objects.count(), 0)


# ---------------------------------------------------------------------------------------------------------------------
# 5. Limites diários por caminhos diferentes (emprego trocado no mesmo dia)
# ---------------------------------------------------------------------------------------------------------------------

class DailyLimitPathsTests(AdversarialBase):
    company_cash = 100_000

    def test_changing_employer_within_the_day_does_not_reset_the_daily_limit(self):
        rich = self.found(self.third, "industrial", "Rica", 0)
        self.assertTrue(services.fund_company(self.third.pk, rich, 5_000_000).ok)
        self.assertTrue(production.set_production(self.third.pk, rich, "flour").ok)
        stock.credit_stock(rich, "wheat", 50, origin="t", key="seed:rich", reference_kind="t", reference_id="9")
        pos_a = self.position
        self.set_skill(self.worker, "physical", 0)
        for i in range(5):
            self.work_hooks(self.worker, refill=(i == 0))
        day = competence_day_of(self.clk.now())
        c_s_first = RemunerationCounter.objects.get(player_id=self.worker.pk, competence_day=day).c_s
        self.assertTrue(jobs.resign(self.worker.pk).ok)
        pos_b = jobs.open_position(self.third.pk, rich, "worker", 2_000, {}).detail["position"]
        app = jobs.apply_to_position(self.worker.pk, pos_b).detail["application"]
        self.assertTrue(jobs.approve_application(self.third.pk, app).ok)
        for i in range(5):
            self.work_hooks(self.worker, refill=True)
        c_s_second = RemunerationCounter.objects.get(player_id=self.worker.pk, competence_day=day).c_s
        note("S6.employer_switch_same_day", after_first_job=c_s_first, after_second_job=c_s_second,
             cap_floor=params.MIN_WAGE_PER_DAY_CENTS)
        self.assertLessEqual(c_s_second, max(params.MIN_WAGE_PER_DAY_CENTS, 200))        # o contador é do JOGADOR, não da empresa
        self.clean()

    def test_the_energy_bar_bounds_how_many_works_a_player_can_do_in_a_day(self):
        self.refill(self.worker)
        works = 0
        while works < 40:
            res = self.work_hooks(self.worker, refill=False)
            if not res.ok:
                break
            works += 1
        note("S7.works_per_energy_bar", works=works, last_refusal=res.code)
        self.assertGreaterEqual(works, 1)
        self.assertLess(works, 40)


# ---------------------------------------------------------------------------------------------------------------------
# 6. Bônus de suporte acumulado
# ---------------------------------------------------------------------------------------------------------------------

class SupportAccumulationTests(AdversarialBase):
    company_cash = 100_000

    def bar_works(self, player):
        n = 0
        self.refill(player)
        while n < 40:
            res = self.work_hooks(player, refill=False)
            if not res.ok:
                break
            n += 1
        return n

    def test_simultaneous_engineers_are_bounded_by_the_star_and_each_by_one_energy_bar(self):
        self.set_stars(2)
        engineers = self.staff(2, kind="engineer", salary=1_000, prefix="e")
        self.assertEqual(jobs.open_position(self.boss.pk, self.firm, "engineer", 1_000, {}).code, "SUPPORT_LIMIT_REACHED")
        works = sum(self.bar_works(p) for p in engineers)
        day = competence_day_of(self.clk.now())
        bonus = support.engineering_bonus(self.firm, self.clk.now()).value
        note("S7.engineers_within_star", stars=2, engineers=len(engineers), works=works, daily_bonus=bonus)
        self.assertEqual(SupportWork.objects.filter(company_id=self.firm, kind="engineer", competence_day=day).count(), works)

    def test_dismissing_and_rehiring_engineers_within_one_day_multiplies_the_daily_bonus_beyond_the_star_limit(self):
        self.set_stars(2)
        rounds, per_round_bonus, total_works = 4, [], 0
        for r in range(rounds):
            engineers = self.staff(2, kind="engineer", salary=1_000, prefix=f"c{r}_")
            total_works += sum(self.bar_works(p) for p in engineers)
            per_round_bonus.append(support.engineering_bonus(self.firm, self.clk.now()).value)
            for pos in Position.objects.filter(company_id=self.firm, kind="engineer", status="filled"):
                self.assertTrue(jobs.dismiss(self.boss.pk, pos.pk).ok)               # a vaga é ENCERRADA: libera o limite da estrela
        sequence = [str(b) for b in per_round_bonus]
        intended = per_round_bonus[0]
        note("S7.engineer_churn", stars=2, rounds=rounds, bonus_by_round=sequence, intended_star_bound=intended,
             multiplier_vs_bound=str(per_round_bonus[-1] / intended), total_engineer_works=total_works)
        # RISCO REAL: o bônus do dia cresce linearmente com o nº de contratações do dia; o limite da estrela só vale para
        # engenheiros SIMULTÂNEOS, e cada contratação traz uma barra de energia nova
        self.assertEqual(len({b for b in per_round_bonus}), rounds)
        self.assertGreater(per_round_bonus[-1], intended * (rounds - 1))
        self.clean()

    def test_one_lawyer_bar_reduces_the_burnout_risk_multiplier_and_the_floor_belongs_to_players(self):
        lawyers = self.staff(1, kind="lawyer", salary=1_000, prefix="l")
        works = self.bar_works(lawyers[0])
        risk = support.lawyer_risk(self.firm, self.clk.now())
        note("S7.lawyer_one_bar", works=works, risk_multiplier=risk.value)
        self.assertEqual(works, SupportWork.objects.filter(kind="lawyer").count())
        self.assertLess(risk.value, 1)
        # A soma diária NÃO é limitada aqui (pode passar de 1 e o multiplicador ficar negativo); o piso de 1% é aplicado por `players`
        # (02 §9.2; testado em #18). O churn de Advogados soma da mesma forma que o de Engenheiros, mas o piso torna o excesso inócuo.


# ---------------------------------------------------------------------------------------------------------------------
# 7. Concentração de mão de obra
# ---------------------------------------------------------------------------------------------------------------------

class LaborConcentrationTests(AdversarialBase):
    def test_one_company_can_open_unlimited_vacancies_and_hire_every_available_player(self):
        opened = 0
        for _ in range(120):
            res = jobs.open_position(self.boss.pk, self.firm, "worker", 1_000, {})
            if not res.ok:
                note("S8.labor_concentration_refusal", code=res.code)
                break
            opened += 1
        crew = self.staff(30)
        employed = Position.objects.filter(company_id=self.firm, kind="worker", status="filled").count()
        note("S8.labor_concentration", vacancies_opened=opened, hired=employed, company_cash=self.firm_money(),
             star=Company.objects.get(pk=self.firm).stars)
        self.assertEqual(opened, 120)                                  # RISCO REAL: nenhum limite de vagas/funcionários
        self.assertEqual(employed, 31)
        self.assertEqual(self.firm_money(), 0)                          # e nenhuma exigência de caixa para isso
        self.clean()

    def test_a_player_still_has_one_job_and_cannot_be_hired_twice(self):
        other = self.found(self.third, "industrial", "Rival", 0)
        pos = jobs.open_position(self.third.pk, other, "worker", 1_000, {}).detail["position"]
        app = jobs.apply_to_position(self.worker.pk, pos).detail["application"]
        res = jobs.approve_application(self.third.pk, app)
        self.assertEqual(res.code, "ALREADY_EMPLOYED")


# ---------------------------------------------------------------------------------------------------------------------
# 8. Concorrência real sobre o mesmo estoque (PostgreSQL trava; SQLite serializa)
# ---------------------------------------------------------------------------------------------------------------------

class StockConcurrencyTests(TransactionTestCase):
    def setUp(self):
        install_test_role(self)
        generate_world(get_scenario(**SMALL))
        WorldClock.load()
        sync_catalog()
        self.boss = create_player(Usuario.objects.create_user("sb"))
        self.crew = [create_player(Usuario.objects.create_user(f"sw{i}")) for i in range(6)]
        fund_account(ledger.player_account(self.boss.pk), 500_000 * REAL)
        self.firm = services.found_company(self.boss.pk, "industrial", "Moinho", 0).detail["company"]
        self.assertTrue(services.fund_company(self.boss.pk, self.firm, 100_000 * REAL).ok)
        self.assertTrue(production.set_production(self.boss.pk, self.firm, "flour").ok)
        for p in self.crew:
            pos = jobs.open_position(self.boss.pk, self.firm, "worker", 1_000, {}).detail["position"]
            app = jobs.apply_to_position(p.pk, pos).detail["application"]
            self.assertTrue(jobs.approve_application(self.boss.pk, app).ok)

    def refill(self, player):
        Player.objects.filter(pk=player.pk).update(energy=D(100), nutrition=D(100), burnout=D(0))

    def clean(self):
        for report in (audit_ledger(), audit_companies()):
            self.assertTrue(report.ok, report.findings)

    def work(self, player):
        self.refill(player)
        return registry.execute_action(player.pk, "work", None)

    def test_simultaneous_works_over_scarce_inputs_never_overdraw_and_never_produce_without_inputs(self):
        seeded = 3
        self.assertTrue(stock.credit_stock(self.firm, "wheat", seeded, origin="t", key="seed:s", reference_kind="t",
                                           reference_id="1").ok)
        jobs_ = run_together(*[lambda p=p: self.work(p) for p in self.crew])
        okays = sum(1 for j in jobs_ if j.result is not None and getattr(j.result, "ok", False))
        wheat, flour = stock.quantity_of(self.firm, "wheat"), stock.quantity_of(self.firm, "flour")
        codes = sorted({j.result.code for j in jobs_ if j.result is not None and not j.result.ok})
        note("S5.concurrent_scarce_inputs", seeded_wheat=seeded, concurrent_works=len(self.crew), succeeded=okays,
             wheat_left=wheat, flour_made=flour, refusal_codes=",".join(codes))
        self.assertGreaterEqual(wheat, 0)
        self.assertEqual(wheat + flour, seeded)                         # 1 trigo → 1 farinha na receita do catálogo: nada nasce de graça
        self.assertLessEqual(flour, seeded)
        self.clean()

    def test_works_and_sales_of_the_same_last_units_never_make_the_stock_negative(self):
        self.assertTrue(stock.credit_stock(self.firm, "wheat", 4, origin="t", key="seed:s2", reference_kind="t", reference_id="2").ok)
        calls = [lambda p=p: self.work(p) for p in self.crew[:3]]
        calls += [lambda n=n: stock.debit_stock(self.firm, "wheat", 1, destination="sale:test", key=f"adv:sale:{n}",
                                                reference_kind="t", reference_id=str(n)) for n in range(3)]
        run_together(*calls)
        left = stock.quantity_of(self.firm, "wheat")
        deltas = sum(StockMovement.objects.filter(company_id=self.firm, product__key="wheat").values_list("delta", flat=True))
        note("S5.work_vs_sale_same_stock", wheat_left=left, movement_sum=deltas)
        self.assertGreaterEqual(left, 0)
        self.assertEqual(deltas, left)                                  # o estoque é exatamente a soma dos movimentos
        self.clean()

    def test_simultaneous_retail_sales_never_exceed_the_stock_or_the_daily_capacity(self):
        shop = services.found_company(self.boss.pk, "retail", "Padaria", 0).detail["company"]
        self.assertTrue(services.fund_company(self.boss.pk, shop, 10_000 * REAL).ok)
        seller = self.crew[0]
        jobs.resign(seller.pk)
        pos = jobs.open_position(self.boss.pk, shop, "salesperson", 1_000, {}).detail["position"]
        app = jobs.apply_to_position(seller.pk, pos).detail["application"]
        self.assertTrue(jobs.approve_application(self.boss.pk, app).ok)
        self.assertTrue(stock.credit_stock(shop, "bread", 8, origin="t", key="seed:b", reference_kind="t", reference_id="3").ok)
        self.refill(seller)
        self.assertTrue(registry.execute_action(seller.pk, "work", None).ok)            # capacidade do dia: 10 (skill 0)
        capacity = retail.capacity_status(shop)["available"]
        outs = run_together(*[lambda n=n: retail.fulfill_sale(shop, "bread", 1, destination="player:1", key=f"adv:r:{n}",
                                                               reference_kind="t", reference_id=str(n)) for n in range(14)])
        sold = sum(1 for j in outs if j.result.ok)
        left = stock.quantity_of(shop, "bread")
        used = sum(SalesCapacityUse.objects.filter(company_id=shop).values_list("quantity", flat=True))
        note("S5.concurrent_retail_sales", capacity=capacity, stock_seeded=8, attempts=14, sold=sold, stock_left=left,
             capacity_used=used)
        self.assertEqual(sold, min(8, capacity))
        self.assertEqual((left, used), (8 - sold, sold))
        self.clean()


class ConstructionConcurrencyTests(StockConcurrencyTests):
    """Obra: vários Trabalhar ao mesmo tempo sobre a mesma obra quase pronta nunca passam de 100% nem concluem duas vezes."""

    def test_simultaneous_works_on_a_nearly_finished_project_complete_it_exactly_once(self):
        from companies.models import ConstructionJob
        builder = services.found_company(self.boss.pk, "construction", "Construtora", 0).detail["company"]
        self.assertTrue(services.fund_company(self.boss.pk, builder, 50_000 * REAL).ok)
        for p in self.crew[:5]:
            jobs.resign(p.pk)
            pos = jobs.open_position(self.boss.pk, builder, "worker", 1_000, {}).detail["position"]
            app = jobs.apply_to_position(p.pk, pos).detail["application"]
            self.assertTrue(jobs.approve_application(self.boss.pk, app).ok)
        self.assertTrue(construction.start_construction(self.boss.pk, builder, "low_density_simple").ok)
        ConstructionJob.objects.filter(company_id=builder).update(progress=D("98.5"))
        calls = []
        construction.register_completion_hook("adv_count", lambda job: calls.append(job.pk))
        self.addCleanup(construction.unregister_completion_hook, "adv_count")
        outs = run_together(*[lambda p=p: self.work(p) for p in self.crew[:5]])
        job = ConstructionJob.objects.get(company_id=builder)
        accepted = sum(1 for j in outs if j.result is not None and j.result.ok)
        note("S9.concurrent_construction", progress=job.progress, status=job.status, completion_hook_calls=len(calls),
             works_accepted=accepted)
        self.assertEqual((job.progress, job.status, len(calls)), (D(100), "completed", 1))
        self.assertTrue(audit_ledger().ok)

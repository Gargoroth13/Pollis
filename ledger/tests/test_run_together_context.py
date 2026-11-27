"""
Regressão: `Job`/`run_together` propagam o contexto do chamador (em especial o RELÓGIO DE TESTE) para as threads.

Defeito que isto cobre: uma thread nova do Python começa com `contextvars` VAZIO. `core.clock.use_clock` guarda o relógio num
`ContextVar`; logo, dentro de uma thread criada "na mão" o relógio ativo voltava a ser o REAL, e um teste que fixa o tempo
com `ManualClock` passava a depender da data de hoje. O efeito aparece ao atravessar fronteiras de período: quem calcula
"o período de hoje" na thread obtém o período REAL, não o do teste, e o teste quebra no dia em que o relógio real entra em
outro período de 30 dias (09 §8). Este módulo NÃO depende do app `budget`: reproduz a mesma aritmética de período (30 dias
contados da época do jogo, `[PROV]`) só para provar que o instante visto pela thread é o do chamador em vários períodos.

Não usa banco de dados: o relógio de teste (`ManualClock`) não consulta o `WorldClock`.
"""
import contextvars
import threading
from unittest import TestCase

from core import clock as game_clock
from core.clock import ManualClock, use_clock
from core.timeline import SECONDS_PER_DAY
from ledger.money import competence_day_of
from ledger.tests.test_scenario_concurrency import Job, run_together

PERIOD_DAYS = 30                                   # espelha budget.params.PERIOD_DAYS [PROV] (09 §8)
EPOCH_DAY = competence_day_of(0)
T0 = 1_791_212_400                                 # 2026-10-05, o instante usado pelos testes de orçamento


def period_at(t: int) -> int:
    return (competence_day_of(t) - EPOCH_DAY) // PERIOD_DAYS


class RunTogetherClockPropagationTests(TestCase):
    def test_a_raw_thread_does_not_inherit_the_clock_which_is_the_original_defect(self):
        """Documenta a causa: thread "crua" não enxerga `use_clock` do chamador (cai no relógio padrão = real)."""
        seen = {}
        with use_clock(ManualClock(T0)):
            raw = threading.Thread(target=lambda: seen.update(clock=game_clock.get_clock()))
            raw.start()
            raw.join()
            self.assertIsNot(seen["clock"], game_clock.get_clock())
            self.assertIs(seen["clock"], game_clock._default)           # o relógio REAL: depende da data de hoje

    def test_threads_of_run_together_see_the_test_clock_in_every_budget_period(self):
        """Atravessa 6 períodos de 30 dias: em cada um, TODAS as threads veem o instante e o período do teste."""
        for k in range(6):
            t = T0 + k * PERIOD_DAYS * SECONDS_PER_DAY
            with self.subTest(period=period_at(t)), use_clock(ManualClock(t)):
                jobs = run_together(lambda: (game_clock.now(), period_at(game_clock.now())),
                                    lambda: (game_clock.now(), period_at(game_clock.now())),
                                    lambda: (game_clock.now(), period_at(game_clock.now())))
                self.assertEqual({j.result for j in jobs}, {(t, period_at(t))})
        self.assertEqual(period_at(T0 + 5 * PERIOD_DAYS * SECONDS_PER_DAY) - period_at(T0), 5)

    def test_each_thread_gets_an_independent_copy_of_the_context(self):
        """Mudar o relógio (ou qualquer variável) dentro de uma thread não vaza para a chamadora nem para as irmãs."""
        marker = contextvars.ContextVar("marker", default="original")
        both_inside = threading.Barrier(2)

        def changes_clock(t, label):
            def run():
                with use_clock(ManualClock(t)):
                    marker.set(label)
                    both_inside.wait(timeout=5)                          # as duas estão DENTRO ao mesmo tempo
                    return game_clock.now(), marker.get()
            return run

        with use_clock(ManualClock(T0)):
            marker.set("caller")
            a, b = run_together(changes_clock(T0 + 100, "a"), changes_clock(T0 + 200, "b"))
            self.assertEqual(a.result, (T0 + 100, "a"))
            self.assertEqual(b.result, (T0 + 200, "b"))
            self.assertEqual(game_clock.now(), T0)                      # a chamadora não foi afetada
            self.assertEqual(marker.get(), "caller")

    def test_the_contexts_are_distinct_objects_per_job(self):
        """Um `Context` não pode ser executado por duas threads ao mesmo tempo: compartilhá-lo serializaria ou quebraria."""
        with use_clock(ManualClock(T0)):
            j1, j2 = Job(lambda: None), Job(lambda: None)
            self.assertIsNot(j1._context, j2._context)
            self.assertEqual(j1._context.run(game_clock.now), T0)
            self.assertEqual(j2._context.run(game_clock.now), T0)

    def test_real_concurrency_is_preserved(self):
        """As threads estão vivas ao mesmo tempo: cada uma só termina depois que TODAS chegaram a um ponto comum."""
        n = 4
        meeting = threading.Barrier(n)
        with use_clock(ManualClock(T0)):
            jobs = run_together(*[(lambda: (meeting.wait(timeout=5), game_clock.now())[1]) for _ in range(n)])
        self.assertEqual([j.result for j in jobs], [T0] * n)
        self.assertEqual(len({j.thread.ident for j in jobs}), n)
        self.assertEqual(len(jobs), n)
        starts, ends = [j.started for j in jobs], [j.ended for j in jobs]
        self.assertLess(max(starts), min(ends))                           # todas começaram antes de qualquer uma acabar

    def test_without_a_test_clock_the_threads_keep_the_default_clock(self):
        """Sem `use_clock` no chamador nada muda: a thread usa o relógio padrão, como antes."""
        job = run_together(lambda: game_clock.get_clock())[0]
        self.assertIs(job.result, game_clock._default)

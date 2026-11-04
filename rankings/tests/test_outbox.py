"""
Outbox durável da atividade (decisão do GD, 2026-11-04). Nos testes (TestCase) `on_commit` não roda sozinho:
`captureOnCommitCallbacks(execute=True)` o executa quando o teste quer o caminho imediato; `outbox.process_pending()` é o worker.
"""
from unittest import mock

from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.test import TransactionTestCase  # noqa: F401  (a concorrência real fica em test_concurrency)

from core import ticks
from core.timeline import Tick, TickKind
from players import registry
from players.models import Player
from rankings import activity, audit, outbox, params, wiring
from rankings.models import ActivityEvent, ActivityStreak

from .base import DAY, HOUR, T0, RankingsTestCase


def act(player, action="leisure"):
    """Uma ação VÁLIDA pelo registro, com energia garantida (o teste não é sobre Energia)."""
    Player.objects.filter(pk=player.pk).update(energy=100)
    res = registry.execute_action(player.pk, action)
    assert res.ok, res
    return res


def seed_events(player, instants, action="leisure", ids_reversed=False):
    """Eventos pendentes diretos (para testar ordem e recuperação sem depender de Energia)."""
    seq = list(instants)[::-1] if ids_reversed else list(instants)
    return [ActivityEvent.objects.create(player_id=player.pk, action_id=action, at=at) for at in seq]


class RecordingInTheActionTransactionTests(RankingsTestCase):
    def test_successful_action_writes_exactly_one_event_with_player_action_instant_and_id(self):
        act(self.player)
        ev = ActivityEvent.objects.get()
        self.assertEqual((ev.player_id, ev.action_id, ev.at, ev.processed_at, ev.attempts), (self.player.pk, "leisure", T0, None, 0))
        self.assertIsNotNone(ev.pk)

    def test_refused_actions_write_no_event(self):
        Player.objects.filter(pk=self.player.pk).update(energy=0)
        self.assertFalse(registry.execute_action(self.player.pk, "leisure").ok)         # requisito não cumprido
        self.assertFalse(registry.execute_action(self.player.pk, "fly").ok)             # ação inexistente
        self.assertFalse(registry.execute_action(self.player.pk, "leisure", None, bogus=1).ok)   # parâmetro inválido
        self.assertEqual(ActivityEvent.objects.count(), 0)

    def test_failure_to_write_the_event_prevents_the_action_from_committing(self):
        before = Player.objects.get(pk=self.player.pk).energy
        with mock.patch.object(outbox, "ActivityEvent") as fake:
            fake.objects.create.side_effect = DatabaseError("falha ao gravar o evento")
            with self.assertRaises(DatabaseError):
                registry.execute_action(self.player.pk, "leisure")
        self.assertEqual(ActivityEvent.objects.count(), 0)
        self.assertEqual(Player.objects.get(pk=self.player.pk).energy, before)          # nenhum efeito da ação sobrou

    def test_the_failed_action_can_be_retried_and_then_counts_once(self):
        with mock.patch.object(outbox, "ActivityEvent") as fake:
            fake.objects.create.side_effect = DatabaseError("x")
            with self.assertRaises(DatabaseError):
                registry.execute_action(self.player.pk, "leisure")
        act(self.player)
        self.assertEqual(ActivityEvent.objects.count(), 1)

    def test_event_and_action_roll_back_together_with_an_enclosing_transaction(self):
        before = Player.objects.get(pk=self.player.pk).energy
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                Player.objects.filter(pk=self.player.pk).update(energy=100)
                self.assertTrue(registry.execute_action(self.player.pk, "leisure").ok)
                self.assertEqual(ActivityEvent.objects.count(), 1)
                raise RuntimeError("falha posterior na mesma transação")
        self.assertEqual(ActivityEvent.objects.count(), 0)
        self.assertEqual(Player.objects.get(pk=self.player.pk).energy, before)

    def test_recorder_is_part_of_the_registry_for_every_player_alike(self):
        """Jogadores humanos e bots usam o MESMO Action Registry (sem caminho privilegiado): o evento não distingue origem."""
        other = self.new_player("bot-like")
        act(self.player)
        act(other)
        a, b = ActivityEvent.objects.order_by("id")
        self.assertEqual((a.action_id, a.at, a.attempts), (b.action_id, b.at, b.attempts))
        self.assertEqual({f.name for f in ActivityEvent._meta.get_fields()},
                         {"id", "player", "action_id", "at", "processed_at", "attempts", "last_error", "last_attempt_at"})
        self.assertIn(wiring.RECORDER_ACTIVITY, registry.action_recorder_names())

    def test_login_and_page_views_do_not_write_events(self):
        self.client.get("/rankings/")
        self.assertEqual(ActivityEvent.objects.count(), 0)

    def test_duplicate_recorder_name_is_refused(self):
        with self.assertRaises(ValueError):
            registry.register_action_recorder(wiring.RECORDER_ACTIVITY, lambda *a: None)


class ProcessingTests(RankingsTestCase):
    def test_processing_updates_the_streak_and_marks_the_event_processed(self):
        act(self.player)
        s = outbox.process_pending()
        self.assertEqual((s.events_processed, s.events_failed, s.pending_before, s.pending_after), (1, 0, 1, 0))
        ev = ActivityEvent.objects.get()
        self.assertEqual((ev.processed_at, ev.attempts, ev.last_error), (T0, 0, ""))
        st = ActivityStreak.objects.get(player=self.player)
        self.assertEqual((st.current_start, st.last_action_at), (T0, T0))

    def test_second_run_has_nothing_to_do(self):
        act(self.player)
        outbox.process_pending()
        s = outbox.process_pending()
        self.assertEqual((s.players, s.events_processed, s.queries > 0), (0, 0, True))

    def test_valid_action_then_processing_failure_then_retry(self):
        energy_after = None
        act(self.player)
        energy_after = Player.objects.get(pk=self.player.pk).energy
        with mock.patch.object(activity, "record_action", side_effect=RuntimeError("falha do processador")):
            with self.assertLogs("rankings.outbox", level="WARNING"):
                s = outbox.process_pending()
        self.assertEqual((s.events_processed, s.events_failed, s.pending_after), (0, 1, 1))
        ev = ActivityEvent.objects.get()
        self.assertEqual((ev.processed_at, ev.attempts), (None, 1))
        self.assertIn("falha do processador", ev.last_error)
        self.assertIsNotNone(ev.last_attempt_at)
        self.assertFalse(ActivityStreak.objects.exists())
        self.assertEqual(Player.objects.get(pk=self.player.pk).energy, energy_after)     # a ação confirmada não foi desfeita
        self.clk.advance(seconds=600)
        s = outbox.process_pending()                                                      # retry posterior
        self.assertEqual((s.events_processed, s.events_failed, s.pending_after), (1, 0, 0))
        ev.refresh_from_db()
        self.assertEqual((ev.attempts, ev.last_error), (1, ""))                           # histórico de tentativas preservado
        self.assertIsNotNone(ev.processed_at)
        self.assertEqual(ActivityStreak.objects.get(player=self.player).last_action_at, T0)

    def test_failure_inside_the_savepoint_leaves_neither_streak_nor_mark(self):
        """Atomicidade: se a marcação falha DEPOIS de atualizar a sequência, a sequência também volta."""
        seed_events(self.player, [T0])
        original = activity.record_action

        def record_then_break(pid, at=None):
            original(pid, at)
            raise RuntimeError("depois de atualizar a sequência")
        with mock.patch.object(activity, "record_action", record_then_break):
            with self.assertLogs("rankings.outbox", level="WARNING"):
                outbox.process_pending()
        self.assertFalse(ActivityStreak.objects.exists())                                 # savepoint desfeito
        self.assertEqual(ActivityEvent.objects.get().processed_at, None)
        outbox.process_pending()
        self.assertEqual(ActivityStreak.objects.get().last_action_at, T0)

    def test_process_killed_in_the_middle_of_an_event_leaves_it_pending_and_untouched(self):
        """Morte do processo (BaseException) no meio do evento: a transação desfaz tudo; o próximo processo recomeça dali."""
        seed_events(self.player, [T0 - 2 * HOUR, T0 - HOUR])
        original = activity.record_action

        def die_on_second(pid, at=None):
            original(pid, at)
            if at == T0 - HOUR:
                raise KeyboardInterrupt()
        with mock.patch.object(activity, "record_action", die_on_second):
            with self.assertRaises(KeyboardInterrupt):
                outbox.process_pending()
        # a passada do jogador é UMA transação: a morte desfez inclusive o primeiro evento (nada pela metade)
        self.assertEqual(ActivityEvent.objects.filter(processed_at__isnull=True).count(), 2)
        self.assertFalse(ActivityStreak.objects.exists())
        self.assertEqual(ActivityEvent.objects.filter(attempts__gt=0).count(), 0)
        outbox.process_pending()
        self.assertEqual(ActivityStreak.objects.get().last_action_at, T0 - HOUR)

    def test_restart_with_pending_events_recovers_everything(self):
        """Nada vive em memória: eventos pendentes de um processo anterior são retomados por um processo novo (worker)."""
        a, b = self.new_player("a"), self.new_player("b")
        for p in (a, b):
            seed_events(p, [T0 - 2 * HOUR, T0 - HOUR])
        self.assertFalse(ActivityStreak.objects.exists())
        call_command("process_activity_outbox", stdout=mock.MagicMock())
        self.assertEqual(ActivityEvent.objects.filter(processed_at__isnull=True).count(), 0)
        for p in (a, b):
            st = ActivityStreak.objects.get(player=p)
            self.assertEqual((st.current_start, st.last_action_at, st.best_length), (T0 - 2 * HOUR, T0 - HOUR, HOUR))

    def test_worker_command_prints_a_structured_summary(self):
        import io
        import json
        seed_events(self.player, [T0])
        out = io.StringIO()
        call_command("process_activity_outbox", "--json", stdout=out)
        d = json.loads(out.getvalue())
        self.assertEqual((d["events_processed"], d["pending_before"], d["pending_after"]), (1, 1, 0))
        self.assertIn("queries", d)

    def test_reprocessing_the_same_event_does_not_duplicate_or_move_the_streak(self):
        seed_events(self.player, [T0 - 2 * HOUR, T0 - HOUR])
        outbox.process_pending()
        before = ActivityStreak.objects.values().get()
        ActivityEvent.objects.update(processed_at=None)                                   # força o reprocessamento
        outbox.process_pending()
        self.assertEqual(ActivityStreak.objects.values().get(), before)
        self.assertEqual(ActivityStreak.objects.count(), 1)

    def test_a_processed_event_is_never_picked_again(self):
        seed_events(self.player, [T0])
        outbox.process_pending()
        with mock.patch.object(activity, "record_action") as rec:
            outbox.process_pending()
        rec.assert_not_called()

    def test_events_of_one_player_are_processed_in_chronological_order_with_stable_tiebreak(self):
        evs = seed_events(self.player, [T0 - 3 * HOUR, T0 - 2 * HOUR, T0 - 2 * HOUR, T0 - HOUR], ids_reversed=True)
        calls = []
        original = activity.record_action
        with mock.patch.object(activity, "record_action", lambda pid, at=None: (calls.append(at), original(pid, at))[1]):
            outbox.process_pending()
        self.assertEqual(calls, sorted(calls))                                            # (at, id) crescente
        self.assertEqual(calls, [T0 - 3 * HOUR, T0 - 2 * HOUR, T0 - 2 * HOUR, T0 - HOUR])
        st = ActivityStreak.objects.get()
        self.assertEqual((st.current_start, st.last_action_at), (T0 - 3 * HOUR, T0 - HOUR))
        ids_in_processing_order = list(ActivityEvent.objects.order_by("processed_at", "at", "id").values_list("id", flat=True))
        self.assertEqual(set(ids_in_processing_order), {e.pk for e in evs})

    def test_same_instant_ties_use_the_event_id(self):
        first, second = seed_events(self.player, [T0, T0])
        with mock.patch.object(activity, "record_action", side_effect=RuntimeError("falha no primeiro")):
            with self.assertLogs("rankings.outbox", level="WARNING"):
                outbox.process_pending()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.attempts, second.attempts), (1, 0))                       # o de menor id é tentado primeiro
        self.assertEqual((first.processed_at, second.processed_at), (None, None))         # e segura o seguinte
        outbox.process_pending()
        self.assertEqual(ActivityEvent.objects.filter(processed_at__isnull=True).count(), 0)

    def test_the_pending_query_orders_by_instant_then_id_regardless_of_the_physical_order(self):
        """O desempate pelo id precisa estar NA CONSULTA (a ordem física das linhas não é garantia de nada)."""
        seed_events(self.player, [T0, T0])
        with CaptureQueriesContext(connection) as ctx:
            outbox.process_player(self.player.pk)
        sql = [q["sql"] for q in ctx.captured_queries if 'FROM "rankings_activityevent"' in q["sql"] and "ORDER BY" in q["sql"]]
        self.assertEqual(len(sql), 1)
        order = sql[0].split("ORDER BY", 1)[1]
        self.assertRegex(order, r'"rankings_activityevent"\."at" ASC, "rankings_activityevent"\."id" ASC')

    def test_a_failing_event_blocks_later_events_of_that_player_but_not_other_players(self):
        other = self.new_player("other")
        seed_events(self.player, [T0 - 3 * HOUR, T0 - 2 * HOUR, T0 - HOUR])
        seed_events(other, [T0 - HOUR])
        original = activity.record_action

        def flaky(pid, at=None):
            if pid == self.player.pk and at == T0 - 2 * HOUR:
                raise RuntimeError("evento envenenado")
            return original(pid, at)
        with mock.patch.object(activity, "record_action", flaky):
            with self.assertLogs("rankings.outbox", level="WARNING"):
                s = outbox.process_pending()
        self.assertEqual((s.events_processed, s.events_failed, s.players_with_failures), (2, 1, 1))
        st = ActivityStreak.objects.get(player=self.player)
        self.assertEqual(st.last_action_at, T0 - 3 * HOUR)                                # só o anterior à falha
        pend = list(ActivityEvent.objects.filter(player=self.player, processed_at__isnull=True).order_by("at"))
        self.assertEqual([e.at for e in pend], [T0 - 2 * HOUR, T0 - HOUR])                # o posterior NÃO foi pulado
        self.assertEqual([e.attempts for e in pend], [1, 0])
        self.assertTrue(ActivityStreak.objects.filter(player=other).exists())
        outbox.process_pending()                                                          # a falha some: tudo é retomado em ordem
        self.assertEqual(ActivityStreak.objects.get(player=self.player).last_action_at, T0 - HOUR)

    def test_player_batch_limit_leaves_the_rest_pending_in_order(self):
        seed_events(self.player, [T0 - 5 * HOUR + i * HOUR for i in range(5)])
        r = outbox.process_player(self.player.pk, limit=2)
        self.assertEqual((r.processed, r.remaining), (2, 3))
        self.assertEqual(ActivityStreak.objects.get().last_action_at, T0 - 4 * HOUR)
        outbox.process_player(self.player.pk)
        self.assertEqual(ActivityStreak.objects.get().last_action_at, T0 - HOUR)

    def test_consecutive_real_actions_extend_the_streak_in_order(self):
        act(self.player)
        self.clk.advance(hours=30)
        self.set_state(self.player, energy=100)
        act(self.player)
        outbox.process_pending()
        st = ActivityStreak.objects.get()
        self.assertEqual((st.current_start, st.last_action_at, st.best_length), (T0, T0 + 30 * HOUR, 30 * HOUR))

    def test_unknown_player_is_ignored(self):
        self.assertEqual(outbox.process_player(10**9).processed, 0)


class ImmediatePassAndTickTests(RankingsTestCase):
    def test_after_commit_the_acting_player_is_processed_immediately(self):
        with self.captureOnCommitCallbacks(execute=True):
            act(self.player)
        self.assertEqual(ActivityEvent.objects.get().processed_at, T0)
        self.assertEqual(ActivityStreak.objects.get().last_action_at, T0)

    def test_inline_processing_can_be_turned_off_and_the_worker_still_recovers(self):
        with mock.patch.object(params, "ACTIVITY_INLINE_PROCESSING", False):
            with self.captureOnCommitCallbacks(execute=True):
                act(self.player)
        self.assertIsNone(ActivityEvent.objects.get().processed_at)
        outbox.process_pending()
        self.assertTrue(ActivityStreak.objects.exists())

    def test_failure_of_the_immediate_pass_does_not_revoke_the_action_and_leaves_the_event_pending(self):
        with mock.patch.object(activity, "record_action", side_effect=RuntimeError("x")):
            with self.assertLogs("rankings.outbox", level="WARNING"):
                with self.captureOnCommitCallbacks(execute=True):
                    act(self.player)
        self.assertEqual(ActivityEvent.objects.filter(processed_at__isnull=True).count(), 1)
        self.assertLess(Player.objects.get(pk=self.player.pk).energy, 100)
        outbox.process_pending()
        self.assertTrue(ActivityStreak.objects.exists())

    def test_even_an_exception_escaping_the_pass_is_contained(self):
        with mock.patch.object(outbox, "process_player", side_effect=RuntimeError("inesperado")):
            with self.assertLogs("rankings.outbox", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    act(self.player)
        self.assertEqual(ActivityEvent.objects.filter(processed_at__isnull=True).count(), 1)

    def test_world_tick_drains_pending_events_after_the_world_commit(self):
        seed_events(self.player, [T0])
        tick = Tick(kind=TickKind.TEN_MINUTES, at=T0 + 600) if "kind" in Tick.__dataclass_fields__ else None
        with self.captureOnCommitCallbacks(execute=True):
            wiring.outbox_tick(tick or mock.Mock(at=T0 + 600), None)
        self.assertEqual(ActivityEvent.objects.filter(processed_at__isnull=True).count(), 0)

    def test_tick_is_registered_on_the_world_ten_minute_tick(self):
        names = [r.name for r in ticks.registry.handlers_for(ticks.WORLD, TickKind.TEN_MINUTES)]
        self.assertIn(wiring.TICK_OUTBOX, names)

    def test_tick_failure_is_contained(self):
        seed_events(self.player, [T0])
        with mock.patch.object(outbox, "process_pending", side_effect=RuntimeError("x")):
            with self.assertLogs("rankings.wiring", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    wiring.outbox_tick(mock.Mock(at=T0), None)


class OutboxAuditTests(RankingsTestCase):
    def test_clean_when_empty_and_when_everything_is_processed(self):
        r = audit.audit_rankings()
        self.assertTrue(r["ok"])
        self.assertEqual(r["stats"]["activity_outbox"], {"pending": 0, "with_errors": 0, "oldest_pending_id": None,
                                                          "oldest_pending_at": None, "oldest_pending_age_seconds": None})
        act(self.player)
        outbox.process_pending()
        self.assertTrue(audit.audit_rankings()["ok"])

    def test_recent_pending_events_are_reported_in_stats_without_a_finding(self):
        evs = seed_events(self.player, [T0 - 600, T0 - 300])
        r = audit.audit_rankings(at=T0)
        self.assertTrue(r["ok"], r["findings"])
        st = r["stats"]["activity_outbox"]
        self.assertEqual((st["pending"], st["oldest_pending_id"], st["oldest_pending_at"], st["oldest_pending_age_seconds"]),
                         (2, evs[0].pk, T0 - 600, 600))

    def test_old_pending_event_is_an_overdue_finding_with_the_oldest_event(self):
        evs = seed_events(self.player, [T0 - 2 * HOUR, T0 - HOUR])
        r = audit.audit_rankings(at=T0)
        f = [x for x in r["findings"] if x["code"] == "ACTIVITY_OUTBOX_OVERDUE"]
        self.assertEqual(len(f), 1)
        self.assertEqual((f[0]["oldest_event_id"], f[0]["age_seconds"], f[0]["pending"]), (evs[0].pk, 2 * HOUR, 2))

    def test_events_with_errors_are_listed_with_their_error(self):
        seed_events(self.player, [T0 - 600])
        with mock.patch.object(activity, "record_action", side_effect=RuntimeError("quebrou")):
            with self.assertLogs("rankings.outbox", level="WARNING"):
                outbox.process_pending()
        r = audit.audit_rankings(at=T0)
        f = [x for x in r["findings"] if x["code"] == "ACTIVITY_EVENT_ERROR"]
        self.assertEqual(len(f), 1)
        self.assertEqual((f[0]["attempts"], f[0]["player_id"]), (1, self.player.pk))
        self.assertIn("quebrou", f[0]["last_error"])
        self.assertEqual(r["stats"]["activity_outbox"]["with_errors"], 1)

    def test_processed_event_not_reflected_in_the_streak_is_a_finding(self):
        ActivityEvent.objects.create(player=self.player, action_id="leisure", at=T0, processed_at=T0)
        r = audit.audit_rankings(at=T0)
        self.assertIn("ACTIVITY_PROCESSED_NOT_REFLECTED", [x["code"] for x in r["findings"]])

    def test_audit_command_json_exposes_the_outbox(self):
        import io
        import json
        seed_events(self.player, [T0])
        out = io.StringIO()
        try:
            call_command("audit_rankings", "--json", stdout=out)
        except Exception:      # noqa: BLE001 - pode sair com erro por achado; o JSON é o que interessa
            pass
        self.assertEqual(json.loads(out.getvalue())["stats"]["activity_outbox"]["pending"], 1)

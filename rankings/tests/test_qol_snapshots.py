"""
Melhor QoL pessoal (14.3.4): snapshots periódicas com referência de tempo comum (decisão do GD, 2026-11-03).
COMPLETE só com todos os elegíveis no mesmo `reference_at`; nunca mistura instantes; a última COMPLETE é preservada.
"""
from decimal import Decimal
from unittest import mock

from django.db import IntegrityError, transaction

from core import ticks
from core.models import WorldClock
from core.timeline import TickKind
from players import hooks as player_hooks, qol, registry
from players.actions import Action
from players.models import Player, QolEffect
from players.services import EffectSpec, perform_action, sync_player
from rankings import live, params, qol_snapshots as snaps, wiring
from rankings.constants import Cat
from rankings.models import QolSnapshot, QolSnapshotEntry

from .base import DAY, HOUR, T0, RankingsTestCase

D = Decimal


class QolSnapshotBase(RankingsTestCase):
    def setUp(self):
        super().setUp()
        self.neutral_qol("1")                              # QoL estrutural 1,00 para todos
        self.ref1 = T0 + HOUR

    def entry(self, player, ref):
        return QolSnapshotEntry.objects.get(snapshot__reference_at=ref, player=player)

    def snap(self, ref):
        return QolSnapshot.objects.get(reference_at=ref)


class ReferenceGridTests(QolSnapshotBase):
    def test_reference_instants_are_multiples_of_the_interval_and_of_the_10_minute_cycle(self):
        self.assertEqual(snaps.reference_for(T0 + 59 * 60), T0)
        self.assertEqual(snaps.next_reference_after(T0), T0 + HOUR)
        self.assertEqual(snaps.next_reference_after(T0 + 1), T0 + HOUR)
        self.assertEqual(T0 % 600, 0)

    def test_interval_is_parameterised_and_validated(self):
        with mock.patch.object(params, "QOL_SNAPSHOT_INTERVAL_SECONDS", 1800):
            self.assertEqual(snaps.next_reference_after(T0), T0 + 1800)
        for bad in (0, 599, 700, -600, 3600.0, True):
            with mock.patch.object(params, "QOL_SNAPSHOT_INTERVAL_SECONDS", bad):
                with self.assertRaises(ValueError):
                    snaps.interval()

    def test_ensure_open_creates_the_next_reference_once(self):
        a = snaps.ensure_open(T0)
        b = snaps.ensure_open(T0 + 10)
        self.assertEqual((a.reference_at, a.pk, a.status), (self.ref1, b.pk, "open"))
        self.assertEqual(QolSnapshot.objects.count(), 1)


class CaptureAtAdvanceTests(QolSnapshotBase):
    def test_player_acting_after_the_reference_is_captured_with_the_state_AT_the_reference(self):
        """Exatidão: o efeito de Lazer aplicado 30 min DEPOIS da referência não aparece no valor da referência."""
        snaps.ensure_open(T0)
        self.clk.advance(seconds=HOUR + 30 * 60)
        self.assertTrue(perform_action(self.player.pk, Action.LEISURE, effect=EffectSpec("leisure:t", D("0.2"), 3 * HOUR)).ok)
        e = self.entry(self.player, self.ref1)
        self.assertEqual((e.qol, e.source), (D("1"), "advance"))
        now_qol = qol.qol_current(Player.objects.get(pk=self.player.pk), self.clk.now()).value
        self.assertEqual(now_qol, D("1.2"))                                    # o estado atual já mudou; a referência não
        self.assertEqual(e.explained["value"], "1.0")
        self.assertEqual(e.explained["computed_at"], self.ref1)

    def test_effect_replaced_after_the_reference_is_still_captured_as_it_was(self):
        """Um efeito da MESMA categoria substitui o anterior (04 §4.4): o valor da referência só existe se capturado antes."""
        self.assertTrue(perform_action(self.player.pk, Action.LEISURE, effect=EffectSpec("leisure:a", D("0.3"), 5 * HOUR)).ok)
        snaps.ensure_open(T0)
        self.clk.advance(seconds=HOUR + 10 * 60)
        self.assertTrue(perform_action(self.player.pk, Action.LEISURE, effect=EffectSpec("leisure:b", D("0.1"), HOUR)).ok)
        self.assertEqual(self.entry(self.player, self.ref1).qol, D("1.3"))      # o efeito "a" ainda valia na referência
        self.assertEqual(QolEffect.objects.get(player=self.player).source, "leisure:b")

    def test_burnout_flag_at_the_reference_is_captured_before_later_changes(self):
        self.set_state(burnout_active=True)
        snaps.ensure_open(T0)
        self.clk.advance(seconds=HOUR + 5 * 60)
        sync_player(self.player.pk)
        e = self.entry(self.player, self.ref1)
        self.assertEqual(e.qol, D("1") - D("0.1"))                              # penalidade de Burnout Ativo (04 §7.3)

    def test_only_open_snapshots_capture_and_each_player_has_one_entry(self):
        self.clk.advance(seconds=HOUR + 60)
        sync_player(self.player.pk)                                            # o provedor abre a referência que faltava
        self.assertEqual(QolSnapshotEntry.objects.filter(player=self.player).count(), 1)
        sync_player(self.player.pk)
        self.assertEqual(QolSnapshotEntry.objects.filter(player=self.player).count(), 1)
        QolSnapshot.objects.filter(reference_at=self.ref1).update(status="incomplete", eligible=1, represented=0, missing=1,
                                                                  finalized_at=T0)
        QolSnapshotEntry.objects.all().delete()
        self.clk.advance(seconds=HOUR)
        sync_player(self.player.pk)                                            # ref1 já finalizada: não captura; ref2 é nova
        self.assertEqual(sorted(QolSnapshotEntry.objects.values_list("snapshot__reference_at", flat=True)), [T0 + 2 * HOUR])

    def test_no_query_when_no_reference_is_crossed(self):
        p = Player.objects.get(pk=self.player.pk)
        with self.assertNumQueries(0):
            self.assertEqual(snaps._provider(p, T0 + 60, T0 + 30 * 60), [])

    def test_player_created_after_the_reference_is_not_captured_for_it(self):
        snaps.ensure_open(T0)
        self.clk.advance(seconds=HOUR + 60)
        late = self.new_player("late")
        self.clk.advance(seconds=HOUR)
        sync_player(late.pk)
        self.assertFalse(QolSnapshotEntry.objects.filter(player=late, snapshot__reference_at=self.ref1).exists())


class CatchUpSplitEquivalenceTests(RankingsTestCase):
    def test_splitting_the_catch_up_at_checkpoints_changes_nothing(self):
        """Dois jogadores idênticos: um catch-up dividido em vários instantes, outro em uma passada. Estado final igual."""
        twin = self.make_player("twin")
        self.neutral_qol("1")
        for p in (self.player, twin):
            Player.objects.filter(pk=p.pk).update(energy=D("40"), nutrition=D("55"), burnout=D("30"), health=D("80"))
        seen = []
        player_hooks.register_checkpoint("probe", lambda pl, s, e: [T0 + 1234, T0 + 7200, T0 + 9000] if pl.pk == self.player.pk else [],
                                         lambda pl, t, bal: seen.append(t))
        self.addCleanup(player_hooks.unregister_checkpoint, "probe")
        self.clk.advance(hours=30)
        a, b = sync_player(self.player.pk), sync_player(twin.pk)
        self.assertEqual(seen, [T0 + 1234, T0 + 7200, T0 + 9000])
        for f in ("energy", "health", "nutrition", "burnout", "burnout_active", "health_critical", "processed_until",
                  "hospitalized_until", "last_work_at"):
            self.assertEqual(getattr(a, f), getattr(b, f), f)

    def test_checkpoints_are_ordered_deduplicated_and_clipped_to_the_interval(self):
        seen = []
        player_hooks.register_checkpoint("a", lambda pl, s, e: [T0 + 900, T0 + 300, T0 - 5, T0 + 10 ** 9],
                                         lambda pl, t, bal: seen.append(("a", t)))
        player_hooks.register_checkpoint("b", lambda pl, s, e: [T0 + 300], lambda pl, t, bal: seen.append(("b", t)))
        self.addCleanup(player_hooks.unregister_checkpoint, "a")
        self.addCleanup(player_hooks.unregister_checkpoint, "b")
        self.clk.advance(hours=1)
        sync_player(self.player.pk)
        self.assertEqual(seen, [("a", T0 + 300), ("b", T0 + 300), ("a", T0 + 900)])
        with self.assertRaises(ValueError):
            player_hooks.register_checkpoint("a", lambda *x: [], lambda *x: None)

    def test_callback_sees_the_player_processed_exactly_to_the_checkpoint(self):
        marks = []
        player_hooks.register_checkpoint("probe", lambda pl, s, e: [T0 + 3000],
                                         lambda pl, t, bal: marks.append((pl.processed_until, t)))
        self.addCleanup(player_hooks.unregister_checkpoint, "probe")
        self.clk.advance(hours=2)
        sync_player(self.player.pk)
        self.assertEqual(marks, [(T0 + 3000, T0 + 3000)])

    def test_sync_player_until_never_goes_past_and_rejects_the_future(self):
        from players.services import sync_player_until
        self.clk.advance(hours=3)
        p = sync_player_until(self.player.pk, T0 + HOUR)
        self.assertEqual(p.processed_until, T0 + HOUR)
        p = sync_player_until(self.player.pk, T0 + 600)                         # já além: não altera
        self.assertEqual(p.processed_until, T0 + HOUR)
        with self.assertRaises(ValueError):
            sync_player_until(self.player.pk, self.clk.now() + 1)


class FinalizeTests(QolSnapshotBase):
    def setUp(self):
        super().setUp()
        self.p2 = self.make_player("p2")
        self.p3 = self.make_player("p3")

    def test_idle_players_are_swept_to_the_reference_and_the_snapshot_is_complete(self):
        snaps.ensure_open(T0)
        self.clk.advance(hours=3)                                              # ninguém agiu: o sweep leva todos à referência
        snap = snaps.finalize(self.ref1)
        self.assertEqual((snap.status, snap.eligible, snap.represented, snap.missing), ("complete", 3, 3, 0))
        for p in (self.player, self.p2, self.p3):
            e = self.entry(p, self.ref1)
            self.assertEqual((e.qol, e.source), (D("1"), "sweep"))
        for p in (self.player, self.p2, self.p3):                              # o sweep processou só até a referência
            self.assertEqual(Player.objects.get(pk=p.pk).processed_until, self.ref1)

    def test_mixed_active_and_idle_players_all_land_on_the_same_reference(self):
        snaps.ensure_open(T0)
        self.clk.advance(seconds=HOUR + 20 * 60)
        self.assertTrue(perform_action(self.p2.pk, Action.LEISURE, effect=EffectSpec("leisure:t", D("0.5"), 3 * HOUR)).ok)
        snap = snaps.finalize(self.ref1)
        self.assertEqual(snap.status, "complete")
        self.assertEqual({e.player_id: (e.qol, e.source) for e in snap.entries.all()},
                         {self.player.pk: (D("1"), "sweep"), self.p2.pk: (D("1"), "advance"), self.p3.pk: (D("1"), "sweep")})
        self.assertEqual({e.explained["computed_at"] for e in snap.entries.all()}, {self.ref1})      # MESMO instante para todos

    def test_player_processed_beyond_the_reference_without_capture_makes_it_incomplete_and_never_mixes_instants(self):
        snaps.ensure_open(T0)
        self.clk.advance(seconds=HOUR + 20 * 60)
        player_hooks.unregister_checkpoint(snaps.CHECKPOINT_NAME)             # simula o valor perdido (sem captura no avanço)
        self.addCleanup(snaps.connect)
        sync_player(self.p2.pk)                                                # p2 vai além da referência sem capturar
        snaps.connect()
        snap = snaps.finalize(self.ref1)
        self.assertEqual((snap.status, snap.eligible, snap.represented, snap.missing), ("incomplete", 3, 2, 1))
        self.assertFalse(QolSnapshotEntry.objects.filter(snapshot=snap, player=self.p2).exists())
        self.assertEqual(live.qol_rows(), [])                                  # nada incompleto aparece como comparável

    def test_incomplete_snapshot_preserves_the_last_complete_one_for_the_public_page(self):
        snaps.ensure_open(T0)
        self.clk.advance(hours=1)
        self.assertEqual(snaps.finalize(self.ref1).status, "complete")
        ref2 = T0 + 2 * HOUR
        snaps.ensure_open(self.clk.now())
        self.clk.advance(seconds=HOUR + 600)
        player_hooks.unregister_checkpoint(snaps.CHECKPOINT_NAME)
        self.addCleanup(snaps.connect)
        sync_player(self.p3.pk)
        snaps.connect()
        self.assertEqual(snaps.finalize(ref2).status, "incomplete")
        r = live.live_ranking(Cat.QOL)
        self.assertEqual(r["snapshot"]["reference_at"], self.ref1)             # a última COMPLETA continua valendo
        self.assertEqual(r["as_of"], self.ref1)
        self.assertEqual(len(r["entries"]), 3)

    def test_finalize_is_idempotent_resumable_and_refuses_the_future(self):
        snaps.ensure_open(T0)
        with self.assertRaises(ValueError):
            snaps.finalize(self.ref1)                                          # a referência ainda não aconteceu
        self.clk.advance(hours=2)
        real = snaps.sync_player_until
        calls = {"n": 0}

        def flaky(pk, until):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("queda no meio da varredura")
            return real(pk, until)
        with mock.patch.object(snaps, "sync_player_until", flaky):
            with self.assertRaises(RuntimeError):
                snaps.finalize(self.ref1)
        self.assertEqual(self.snap(self.ref1).status, "open")
        self.assertEqual(QolSnapshotEntry.objects.filter(snapshot__reference_at=self.ref1).count(), 1)     # o que já foi fica
        snap = snaps.finalize(self.ref1)                                       # retoma
        self.assertEqual((snap.status, snap.represented), ("complete", 3))
        before = list(QolSnapshotEntry.objects.values())
        again = snaps.finalize(self.ref1)
        self.assertEqual((again.pk, again.status, list(QolSnapshotEntry.objects.values())), (snap.pk, "complete", before))

    def test_eligibility_is_created_at_or_before_the_reference(self):
        snaps.ensure_open(T0)
        self.clk.advance(seconds=HOUR)
        at_ref = self.new_player("atref")                                       # criado exatamente na referência: elegível
        self.clk.advance(seconds=60)
        late = self.new_player("late")                                          # criado DEPOIS da referência
        snap = snaps.finalize(self.ref1)
        self.assertEqual((snap.status, snap.eligible), ("complete", 4))
        self.assertTrue(QolSnapshotEntry.objects.filter(snapshot=snap, player=at_ref).exists())
        self.assertFalse(QolSnapshotEntry.objects.filter(snapshot=snap, player=late).exists())

    def test_values_are_exact_per_player_and_ordered_by_the_page(self):
        qol.clear_qol_base_providers()
        qol.register_qol_base_provider("per_player", lambda p, at: D(p.pk) / D(1000))     # QoL distinta por jogador
        snaps.ensure_open(T0)
        self.clk.advance(hours=2)
        snaps.finalize(self.ref1)
        r = live.live_ranking(Cat.QOL)
        self.assertEqual([e["name"] for e in r["entries"]], ["p3", "p2", "p1"])
        self.assertEqual(r["entries"][0]["value"], D("0.5") + D(self.p3.pk) / D(1000))
        self.assertEqual([e["rank"] for e in r["entries"]], [1, 2, 3])
        self.assertEqual(r["entries"][0]["detail"]["reference_at"], self.ref1)
        self.assertEqual(r["entries"][0]["detail"]["explained"]["steps"][0]["key"], "qol_base_effective")

    def test_ties_share_position_and_limit(self):
        snaps.ensure_open(T0)
        self.clk.advance(hours=2)
        snaps.finalize(self.ref1)
        r = live.live_ranking(Cat.QOL, limit=2)
        self.assertEqual([e["rank"] for e in r["entries"]], [1, 1])
        self.assertEqual(r["entries"][0]["display"], "1,0000")

    def test_metrics_are_recorded(self):
        snaps.ensure_open(T0)
        self.clk.advance(seconds=HOUR + 600)
        perform_action(self.p2.pk, Action.LEISURE)
        snap = snaps.finalize(self.ref1)
        m = snap.metrics
        self.assertEqual(m["entries_by_source"], {"advance": 1, "sweep": 2})
        self.assertGreater(m["queries"], 0)
        self.assertGreaterEqual(m["duration_ms"], 0)
        self.assertEqual((m["lag_seconds"], snap.finalized_at), (600, self.clk.now()))

    def test_database_refuses_a_complete_snapshot_with_missing_players(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QolSnapshot.objects.create(reference_at=T0 + 10 * HOUR, status="complete", opened_at=T0, finalized_at=T0,
                                           eligible=3, represented=2, missing=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QolSnapshot.objects.create(reference_at=T0 + 11 * HOUR, status="incomplete", opened_at=T0)   # sem contagens

    def test_qol_exactness_guard(self):
        with self.assertRaises(ValueError):
            snaps._exact(D("0.1234567890123"))
        self.assertEqual(snaps._exact(D("1.5")), D("1.500000000000"))


class PublicQolRankingTests(QolSnapshotBase):
    def test_without_a_complete_snapshot_nothing_comparable_is_shown(self):
        r = live.live_ranking(Cat.QOL)
        self.assertEqual((r["available"], r["entries"], r["snapshot"]), (True, [], None))
        self.assertEqual(live.historical_ranking(Cat.NET_WORTH_RECORD)["category"], "net_worth_record")

    def test_page_and_json_show_the_reference_instant(self):
        snaps.ensure_open(T0)
        self.clk.advance(hours=2)
        snaps.finalize(self.ref1)
        d = self.client.get("/rankings/qol/").json()
        self.assertEqual((d["snapshot"]["reference_at"], d["entries"][0]["value"]), (self.ref1, "1.000000000000"))
        html = self.client.get("/rankings/").content.decode()
        self.assertIn("1,0000", html)

    def test_reading_the_page_never_recalculates_players(self):
        snaps.ensure_open(T0)
        self.clk.advance(hours=2)
        snaps.finalize(self.ref1)
        before = list(Player.objects.values())
        with mock.patch.object(qol, "qol_current", side_effect=AssertionError("recalculou no acesso")):
            self.client.get("/rankings/")
            self.client.get("/rankings/data/")
        self.assertEqual(list(Player.objects.values()), before)


class LifecycleAndRetentionTests(QolSnapshotBase):
    def test_process_due_finalizes_opens_next_and_prunes(self):
        snaps.ensure_open(T0)
        self.clk.advance(seconds=HOUR + 30)
        done = snaps.process_due()
        self.assertEqual([(s.reference_at, s.status) for s in done], [(self.ref1, "complete")])
        self.assertEqual(self.snap(T0 + 2 * HOUR).status, "open")               # a próxima já está aberta ANTES de qualquer cruzamento

    def test_retention_keeps_the_last_24_complete_by_default_and_drops_older_ones_with_entries(self):
        self.assertEqual(params.QOL_SNAPSHOT_RETAIN_COMPLETE, 24)
        with mock.patch.object(params, "QOL_SNAPSHOT_RETAIN_COMPLETE", 3):
            for i in range(1, 7):
                QolSnapshot.objects.create(reference_at=T0 + i * HOUR, status="complete", opened_at=T0, finalized_at=T0,
                                           eligible=1, represented=1, missing=0)
            QolSnapshot.objects.create(reference_at=T0 + 3 * HOUR + 1, status="incomplete", opened_at=T0, finalized_at=T0,
                                       eligible=1, represented=0, missing=1)      # anterior à mais antiga mantida (T0+4h)
            QolSnapshot.objects.create(reference_at=T0 + 5 * HOUR + 1, status="incomplete", opened_at=T0, finalized_at=T0,
                                       eligible=1, represented=0, missing=1)      # mais nova que a mais antiga mantida: fica
            QolSnapshot.objects.create(reference_at=T0 + 9 * HOUR, status="open", opened_at=T0)
            QolSnapshotEntry.objects.create(snapshot=self.snap(T0 + HOUR), player=self.player, qol=1, source="sweep")
            deleted = snaps.prune()
        left = sorted(QolSnapshot.objects.values_list("reference_at", flat=True))
        self.assertEqual(left, [T0 + 4 * HOUR, T0 + 5 * HOUR, T0 + 5 * HOUR + 1, T0 + 6 * HOUR, T0 + 9 * HOUR])
        self.assertEqual(deleted, 4)                                            # (T0+1h, +2h, +3h, +3h+1) com a entrada em cascata
        self.assertFalse(QolSnapshotEntry.objects.exists())

    def test_prune_does_nothing_until_there_are_n_complete_snapshots(self):
        QolSnapshot.objects.create(reference_at=T0 + HOUR, status="incomplete", opened_at=T0, finalized_at=T0, eligible=1,
                                   represented=0, missing=1)
        self.assertEqual(snaps.prune(), 0)
        with self.assertRaises(ValueError):
            snaps.prune(0)

    def test_world_tick_opens_the_next_reference_and_finalizes_after_commit(self):
        names = [r.name for r in ticks.registry.handlers_for(ticks.WORLD, TickKind.TEN_MINUTES)]
        self.assertIn(wiring.TICK_QOL, names)
        WorldClock.load()
        WorldClock.objects.filter(pk=1).update(world_processed_until=T0)
        self.clk.advance(seconds=HOUR + 600)
        with self.captureOnCommitCallbacks(execute=True):
            ticks.advance_world()
        self.assertEqual(self.snap(self.ref1).status, "complete")
        self.assertEqual(self.snap(T0 + 2 * HOUR).status, "open")
        self.assertEqual(self.snap(self.ref1).represented, 1)

    def test_world_tick_does_no_heavy_work_inside_the_world_transaction(self):
        snaps.ensure_open(T0)
        self.clk.advance(hours=2)
        with mock.patch.object(snaps, "process_due") as heavy:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                snaps.world_tick(mock.Mock(at=self.clk.now()), None)
        heavy.assert_not_called()                                               # só agendado para depois do commit
        self.assertEqual(len(callbacks), 1)

    def test_wiring_is_idempotent(self):
        wiring.connect()
        wiring.connect()
        self.assertEqual(player_hooks.checkpoint_names().count(snaps.CHECKPOINT_NAME), 1)
        names = [r.name for r in ticks.registry.handlers_for(ticks.WORLD, TickKind.TEN_MINUTES)]
        self.assertEqual(names.count(wiring.TICK_QOL), 1)


class QolAuditTests(QolSnapshotBase):
    def test_audit_is_clean_for_a_healthy_complete_snapshot_and_reports_stats(self):
        from rankings import audit
        snaps.ensure_open(T0)
        self.clk.advance(hours=2)
        snaps.finalize(self.ref1)
        rep = audit.audit_rankings()
        self.assertTrue(rep["ok"], rep["findings"])
        self.assertEqual((rep["stats"]["qol_latest_complete"], rep["stats"]["qol_incomplete"]), (self.ref1, 0))

    def test_audit_reports_inconsistent_complete_and_overdue_open_snapshots(self):
        from rankings import audit
        snaps.ensure_open(T0)
        self.clk.advance(hours=2)
        snaps.finalize(self.ref1)
        QolSnapshotEntry.objects.filter(snapshot__reference_at=self.ref1).first().delete()
        QolSnapshot.objects.create(reference_at=T0 - 600, status="open", opened_at=T0)            # vencida há mais de 2 intervalos
        codes = sorted(f["code"] for f in audit.audit_rankings()["findings"])
        self.assertEqual(codes, ["QOL_SNAPSHOT_INCONSISTENT", "QOL_SNAPSHOT_OVERDUE"])


class CheckpointCostTests(QolSnapshotBase):
    """O custo do checkpoint de QoL no catch-up (medido aqui; o teste de custo do registro o isola de propósito)."""

    def _sync_queries(self, hours, with_checkpoint=True):
        from core.instrument import QueryCounter
        from players.services import sync_player
        p = self.new_player(f"cost-{hours}-{with_checkpoint}")
        base = snaps.reference_for(self.clk.now())
        for h in range(1, 14):                                      # linhas abertas de antemão: custo simétrico entre jogadores
            snaps._open(base + h * HOUR, self.clk.now())
        self.clk.advance(seconds=hours * HOUR)
        saved = dict(player_hooks._checkpoints)
        if not with_checkpoint:
            player_hooks._checkpoints.clear()
        try:
            with QueryCounter() as q:
                sync_player(p.pk)
        finally:
            player_hooks._checkpoints.clear()
            player_hooks._checkpoints.update(saved)
        return q.count

    def test_cost_is_zero_extra_without_a_reference_and_bounded_per_reference_crossed(self):
        def extra(hours):
            return self._sync_queries(hours, True) - self._sync_queries(hours, False)
        # 10 min: nenhuma referência atravessada (T0 já é uma): o checkpoint não consulta o banco
        self.clk.advance(seconds=600)
        e0 = extra(0)
        self.assertEqual(e0, 0)
        e1, e2, e8 = extra(1), extra(2), extra(8)
        e11 = extra(11)
        self.assertGreater(e1, 0)
        # limitado às duas últimas referências: não cresce com a ausência (medido: 8 consultas a mais com 1 referência, 14 com 2+)
        self.assertLessEqual(e8, e2 + 2)
        self.assertLessEqual(abs(e11 - e8), 2)
        self.assertLessEqual(max(e2, e8, e11), 16)
        self.assertLessEqual(e2, 2 * e1)
        self.assertLessEqual(e1, 10)

"""End-to-end contracts for unique staff, economy, expeditions and migration."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from orion import balance, specialists as s, news, statistics
from orion.model import GameState, RuleError, SaveError, new_game, ConstructionProject
from orion.storage import Storage, SAVE_VERSION
from orion.empire import summarize_empire
from orion.buildings import BUILDINGS


class SpecialistFixtures:
    def setUp(self):
        previous, configured = balance.active_profile(), balance._configured_path
        balance._configured_path = None
        balance.activate(balance.default_profile())
        self.addCleanup(lambda: balance.activate(previous))
        self.addCleanup(lambda: setattr(balance, "_configured_path", configured))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def game(self, **kwargs):
        return new_game(seed=kwargs.pop("seed", 2408), with_ai=kwargs.pop("with_ai", False),
                        with_guardians=False, with_tombs=False, with_black_holes=False,
                        random_starts=False, **kwargs)

    def hub(self, game, owner="player"):
        system, planet = game.headquarters(owner)
        if "space_hub" not in planet.buildings:
            planet.buildings.append("space_hub")
        return system, planet

    def recruit(self, game, identifier, owner="player"):
        # Controlled visitor fixture; hiring and assignment always use real rules.
        system, planet = self.hub(game, owner)
        game._empire(owner).credits = 1000
        p = s.person(game, identifier)
        p.visitor, p.system_id, p.planet_id, p.expires = owner, system.id, planet.id, game.turn+6
        return s.hire(game, identifier, owner)

    def colony(self, game, sid=0, pid=3, owner="player"):
        planet = game.planet_at(sid, pid)
        planet.colonized, planet.owner, planet.population = True, owner, 4
        planet.farmers = planet.miners = planet.scientists = 0
        return planet


class SpecialistTests(SpecialistFixtures, unittest.TestCase):
    def test_hub_uses_normal_construction_and_only_one_per_planet(self):
        game = self.game()
        game.resources = game.credits = 1000
        planet = game.planet_at(0, 2)
        before = planet.free_slots
        game.queue_building(0, 2, "space_hub")
        self.assertEqual(planet.free_slots, before-1)
        with self.assertRaises(RuleError): game.queue_building(0, 2, "space_hub")
        game.buy_construction(0, 2)
        self.assertIn((0, 2), s.hubs(game))
        with self.assertRaises(RuleError): game.queue_building(0, 2, "space_hub")
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_no_visitors_without_an_operational_hub(self):
        game = self.game()
        s.advance_visitors(game)
        self.assertFalse(s.visitors(game))
        _, planet = self.hub(game)
        planet.disabled_buildings = [planet.buildings.index("space_hub")]
        s.advance_visitors(game)
        self.assertFalse(s.visitors(game))
        planet.disabled_buildings = []
        s.advance_visitors(game)
        self.assertEqual({p.spec.role for p in s.visitors(game)}, {"leader", "explorer"})

    def test_names_profiles_and_galaxy_records_are_unique(self):
        game = self.game(with_ai=True, rival_count=3)
        self.assertEqual(len({p.spec.name for p in game.specialists.people}), len(s.SPECIALISTS))
        self.assertEqual(len({tuple(p.skills.items()) for p in game.specialists.people}), len(s.SPECIALISTS))
        for owner in game.owners: self.hub(game, owner)
        s.advance_visitors(game)
        all_visitors = [p for owner in game.owners for p in s.visitors(game, owner)]
        self.assertEqual(len(all_visitors), len({p.id for p in all_visitors}))
        state = game.to_dict()
        s.advance_visitors(game)
        self.assertEqual(game.to_dict(), state)  # Opening/checking twice does not reroll.
        twin = GameState.from_dict(state)
        for _ in range(20):
            for target in (game, twin):
                target.turn += 1; target.year += 1
                s.advance_visitors(target)
                self.assertTrue(all(len(s.visitors(target, owner)) <= s.MAX_VISITORS for owner in target.owners))
        self.assertEqual(game.specialists, twin.specialists)

    def test_extra_hubs_do_not_multiply_arrival_rate(self):
        a, b = self.game(), self.game()
        self.hub(a); self.hub(b)
        self.colony(b).buildings.append("space_hub")
        for _ in range(30):
            for game in (a, b):
                s.advance_visitors(game)
                game.turn += 1; game.year += 1
            self.assertEqual(len(s.visitors(a)), len(s.visitors(b)))
        b.race_id = "concord"
        self.assertEqual(s.visit_chance(b, "player"), s.SOCIAL_VISIT_CHANCE)
        b.race_id = "remnant"
        self.assertLess(s.visit_chance(b, "player"), s.visit_chance(a, "player"))

    def test_visitors_expire_and_cannot_be_hired_after_departure(self):
        game = self.game()
        self.hub(game); s.advance_visitors(game)
        p = s.visitors(game)[0]
        game.turn = p.expires; game.year = 2299+game.turn
        self.assertNotIn(p, s.visitors(game))
        with self.assertRaises(RuleError): s.hire(game, p.id)
        s.normalize(game)
        self.assertIsNone(p.visitor)
        self.assertGreater(p.available_after, game.turn)

    def test_fee_is_atomic_and_duplicate_or_enemy_hires_rejected(self):
        game = self.game(with_ai=True)
        self.hub(game); s.advance_visitors(game)
        p = s.visitors(game)[0]
        game.credits = p.spec.hiring_fee-1
        before = deepcopy(game.specialists)
        with self.assertRaises(RuleError): s.hire(game, p.id)
        self.assertEqual(before, game.specialists)
        with self.assertRaises(RuleError): s.hire(game, p.id, "rival")
        game.credits = p.spec.hiring_fee
        s.hire(game, p.id)
        self.assertEqual(game.credits, 0)
        with self.assertRaises(RuleError): s.hire(game, p.id)
        self.assertEqual(game.credits, 0)

    def test_salaries_paid_once_in_turn_reports_summary_and_statistics(self):
        game = self.game(with_ai=True)
        leader = self.recruit(game, "mara_voss")
        rival = self.recruit(game, "ilyra_senn", "rival")
        s.assign(game, leader.id, 0, 2)
        home, planet = game.headquarters("rival")
        s.assign(game, rival.id, home.id, planet.id, "rival")
        for owner in game.owners:
            summary = summarize_empire(game, owner=owner)
            self.assertEqual(summary.income, summary.gross_income-summary.maintenance)
            self.assertEqual(summary.income, game.empire_rates_for(owner)[0])
            self.assertEqual(summary.income, statistics.sample(game, owner)[-1])
        rates = {o: game.empire_rates_for(o)[0] for o in game.owners}
        banks = {o: game._empire(o).credits for o in game.owners}
        with patch("orion.ai.run_ai", return_value=[]): report = game.advance_turn()
        self.assertEqual(report.income, rates["player"])
        for owner in game.owners:
            self.assertEqual(game._empire(owner).credits-banks[owner], rates[owner])

    def test_salaries_can_create_normal_treasury_debt(self):
        game = self.game()
        self.recruit(game, "civic_seven")
        planet = game.planet_at(0, 2)
        planet.population = 1
        planet.farmers = planet.miners = planet.scientists = 0
        game.credits = 0
        expected = game.empire_rates[0]
        self.assertLess(expected, 0)
        game.advance_turn()
        self.assertEqual(game.credits, expected)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_xp_in_reserve_levels_known_skills_only_and_salary_stays_fixed(self):
        game = self.game()
        p = self.recruit(game, "kaia_ren")
        cost = p.spec.salary
        for _ in range(5): game.advance_turn()
        self.assertEqual((p.xp, p.level, p.skill("hacking")), (5, 2, 4))
        self.assertEqual(p.skill("archaeology"), 0)
        self.assertEqual(p.spec.salary, cost)
        free = s.person(game, "echo_nine")
        self.assertEqual(free.xp, 0)
        p.xp = s.level_xp(s.MAX_LEVEL)
        game.advance_turn()
        self.assertEqual(p.xp, s.level_xp(s.MAX_LEVEL))

    def test_leader_effects_are_local_and_work_in_real_construction(self):
        game = self.game()
        p = self.recruit(game, "mara_voss")
        earth = game.planet_at(0, 2)
        mars = self.colony(game)
        original = game.planet_yields(earth)[0]
        other = game.planet_yields(mars)
        mining = game.planet_resources(earth)
        s.assign(game, p.id, 0, 2)
        self.assertEqual(game.planet_yields(earth)[0], original+4)
        self.assertEqual(game.planet_resources(earth), mining+1)
        self.assertEqual(game.planet_yields(mars), other)
        game.queue_building(0, 2, "factory")
        expected = game.planet_yields(earth)[0]
        game.advance_turn()
        self.assertEqual(earth.construction_queue[0].progress, expected)
        s.assign(game, p.id, 0, 3)
        self.assertEqual(game.planet_yields(earth)[0], original)
        self.assertEqual(game.planet_yields(mars)[0], other[0]+4)

    def test_food_science_income_and_mining_leaders_have_real_effects(self):
        for identifier, field in (("veya_tal", "food"), ("ilyra_senn", "research"), ("tarek_sol", "income"), ("doran_kesh", "mining")):
            with self.subTest(skill=field):
                game = self.game()
                p = self.recruit(game, identifier)
                earth = game.planet_at(0, 2)
                def output():
                    return game.population_report(earth).produced if field == "food" else game.planet_resources(earth) if field == "mining" else game.planet_yields(earth)[2 if field == "research" else 1]
                before = output()
                s.assign(game, p.id, 0, 2)
                self.assertEqual(output()-before, p.skill(field))

    def test_assignments_enforce_ownership_capacity_and_one_per_colony(self):
        game = self.game(with_ai=True)
        a = self.recruit(game, "mara_voss")
        b = self.recruit(game, "ilyra_senn")
        s.assign(game, a.id, 0, 2)
        with self.assertRaises(RuleError): s.assign(game, b.id, 0, 2)
        home, world = game.headquarters("rival")
        with self.assertRaises(RuleError): s.assign(game, b.id, home.id, world.id)
        with self.assertRaises(RuleError): s.assign(game, b.id, True, 2)
        with self.assertRaises(RuleError): s.assign(game, "veya_tal", 0, 2, owner=None)
        for identifier in ("veya_tal", "doran_kesh"): self.recruit(game, identifier)
        self.hub(game)
        p = s.person(game, "tarek_sol")
        p.visitor, p.system_id, p.planet_id, p.expires = "player", 0, 2, game.turn+6
        with self.assertRaises(RuleError): s.hire(game, p.id)

    def test_dismiss_and_rehire_preserve_identity_and_xp(self):
        game = self.game()
        p = self.recruit(game, "mara_voss")
        p.xp = 15
        s.assign(game, p.id, 0, 2)
        bank = game.credits
        s.dismiss(game, p.id)
        self.assertEqual(game.credits, bank)
        self.assertEqual(s.salaries(game), 0)
        self.assertEqual((p.xp, p.system_id, p.owner), (15, None, None))
        self.recruit(game, p.id)
        self.assertEqual((p.xp, p.level), (15, 3))

    def test_hub_closure_stops_visitors_but_not_hired_work(self):
        game = self.game()
        self.hub(game); s.advance_visitors(game)
        p = next(p for p in s.visitors(game) if p.spec.role == "leader")
        game.credits = 1000
        s.hire(game, p.id); s.assign(game, p.id, 0, 2)
        before = game.planet_yields(game.planet_at(0, 2))
        game.toggle_building(0, 2, 0)
        self.assertFalse(s.visitors(game))
        s.normalize(game)
        self.assertEqual(p.owner, "player")
        self.assertEqual(game.planet_yields(game.planet_at(0, 2)), before)

    def test_lost_colony_returns_leader_to_reserve_without_transfer(self):
        game = self.game(with_ai=True)
        self.colony(game)
        p = self.recruit(game, "mara_voss")
        s.assign(game, p.id, 0, 2)
        game.planet_at(0, 2).owner = "rival"
        self.assertFalse(s.colony_effects(game, game.planet_at(0, 2)))
        restored = GameState.from_dict(game.to_dict())  # Saving immediately after conquest is valid.
        s.normalize(restored)
        copy = s.person(restored, p.id)
        self.assertEqual(copy.owner, "player")
        self.assertIsNone(copy.system_id)

    def test_expedition_has_two_stages_and_reward_only_once(self):
        game = self.game()
        p = self.recruit(game, "kaia_ren")
        s.assign(game, p.id, 0)
        site = s.site_at(game, 0); site.kind = "sealed_station"
        before = game.credits
        for _ in range(4): s.advance_employed(game)
        self.assertEqual(site.surveyed, s.SURVEY_WORK)
        self.assertEqual(site.progress, 0)
        self.assertEqual(game.credits, before)
        while not site.recovered_by: s.advance_employed(game)
        self.assertEqual(game.credits-before, site.spec.credits)
        self.assertIsNone(p.system_id)
        with self.assertRaises(RuleError): s.assign(game, p.id, 0)
        for _ in range(20): s.advance_employed(game)
        self.assertEqual(game.credits-before, site.spec.credits)

    def test_wrong_skill_blocks_recovery_and_switching_keeps_progress(self):
        game = self.game()
        hacker = self.recruit(game, "kaia_ren")
        archaeologist = self.recruit(game, "saeli_orr")
        s.assign(game, hacker.id, 0)
        site = s.site_at(game, 0); site.kind = "ancient_observatory"
        site.surveyed = s.SURVEY_WORK
        s.advance_employed(game)
        self.assertEqual(site.progress, 0)
        self.assertIn("Blocked", s.expedition_status(game, hacker))
        with self.assertRaises(RuleError): s.assign(game, archaeologist.id, 0)
        s.unassign(game, hacker.id); s.assign(game, archaeologist.id, 0)
        s.advance_employed(game)
        self.assertEqual(site.progress, archaeologist.skill("archaeology"))
        self.assertEqual(site.surveyed, s.SURVEY_WORK)
        self.assertEqual(len(game.specialists.sites), 1)

    def test_foreign_fleets_pause_expeditions_but_not_xp(self):
        game = self.game(with_ai=True)
        p = self.recruit(game, "kaia_ren")
        s.assign(game, p.id, 0)
        with patch.object(game, "foreign_fleet", return_value=[object()]):
            s.advance_employed(game)
            self.assertIn("Paused", s.expedition_status(game, p))
        self.assertEqual(s.site_at(game, 0).surveyed, 0)
        self.assertEqual(p.xp, 1)

    def test_each_site_credits_its_reward_and_research_is_spent_this_turn(self):
        from orion.research import TECHNOLOGIES
        for kind, identifier, field in (("sealed_station", "kaia_ren", "credits"),
                                         ("rare_asteroid", "torvek", "resources"),
                                         ("ancient_observatory", "saeli_orr", "research")):
            with self.subTest(kind=kind):
                game = self.game()
                p = self.recruit(game, identifier)
                s.assign(game, p.id, 0)
                site = s.site_at(game, 0)
                site.kind, site.surveyed = kind, s.SURVEY_WORK
                site.progress = site.spec.work-1
                if field == "research":
                    game.choose_research("research_instruments")
                    game.technology.progress = TECHNOLOGIES["research_instruments"].cost-site.spec.research
                before = getattr(game, field)
                recurring = game.empire_rates[0] if field == "credits" else game.resource_rate() if field == "resources" else 0
                game.advance_turn()
                self.assertEqual(site.recovered_by, "player")
                if field == "research":
                    self.assertIn("research_instruments", game.technology.completed)
                else:
                    self.assertEqual(getattr(game, field), before+recurring+getattr(site.spec, field))

    def test_ai_builds_hub_only_after_basic_industry_and_food(self):
        game = self.game(with_ai=True)
        game.ships[:] = [ship for ship in game.ships if ship.owner != "rival"]
        home, planet = game.headquarters("rival")
        game.opponent.credits = game.opponent.resources = 500
        game.turn, game.year = 20, 2319
        s.ai_orders(game, "rival")
        self.assertFalse(planet.construction_queue)
        planet.buildings = ["factory", "trade_center"]
        planet.farmers = 3
        s.ai_orders(game, "rival")
        self.assertFalse(planet.construction_queue)  # Reserve the first expansion.
        self.colony(game, sid=home.id, pid=next(w.id for w in home.worlds if not w.colonized), owner="rival")
        s.ai_orders(game, "rival")
        self.assertEqual(planet.construction_queue[0].item_id, "space_hub")

    def test_hiring_is_blocked_in_observer_and_battle_modes(self):
        game = self.game()
        self.hub(game); s.advance_visitors(game)
        candidate = s.visitors(game)[0]
        game.combat = object()
        with self.assertRaises(RuleError): s.hire(game, candidate.id)
        game.combat = None
        observer = self.game(race_id="observer", rival_count=2)
        with self.assertRaises(RuleError): s.hire(observer, "mara_voss")

    def test_progress_and_reward_ownership_survive_save_and_capture(self):
        game = self.game(with_ai=True)
        p = self.recruit(game, "kaia_ren")
        s.assign(game, p.id, 0)
        site = s.site_at(game, 0)
        site.kind, site.surveyed, site.progress = "sealed_station", s.SURVEY_WORK, 6
        store = Storage(self.root)
        restored, payload = store.load(store.save(game))
        self.assertEqual(payload["version"], SAVE_VERSION)
        self.assertEqual(restored, game)
        with patch("orion.ai.run_ai", return_value=[]):
            for _ in range(3):
                game.advance_turn(); restored.advance_turn()
        self.assertEqual(restored, game)
        p = s.person(restored, p.id)
        while not s.site_at(restored, 0).recovered_by: s.advance_employed(restored)
        self.colony(restored, owner="rival", pid=2)
        other = self.recruit(restored, "echo_nine", "rival")
        with self.assertRaises(RuleError): s.assign(restored, other.id, 0, owner="rival")

    def test_construction_forecast_includes_leader_level_gain(self):
        game = self.game()
        p = self.recruit(game, "mara_voss")
        s.assign(game, p.id, 0, 2)
        p.xp = 4
        earth = game.planet_at(0, 2)
        earth.population = 8; earth.farmers = 7; earth.scientists = earth.miners = 0
        earth.construction_queue = [ConstructionProject("research_lab"), ConstructionProject("factory")]
        game.resources = 500
        expected = game.queue_estimates(earth)
        completed = []
        for turn in range(1, 20):
            report = game.advance_turn()
            completed.extend([turn]*len(report.completed))
            if not earth.construction_queue: break
        self.assertEqual(completed, expected)
        s.unassign(game, p.id)
        game.queue_building(0, 2, "mine")
        slow = game.queue_estimates(earth)
        s.assign(game, p.id, 0, 2)
        self.assertLessEqual(game.queue_estimates(earth)[0], slow[0])

    def test_ai_hires_assigns_and_pays_under_player_rules(self):
        game = self.game(with_ai=True)
        home, planet = self.hub(game, "rival")
        planet.buildings.append("trade_center")
        game.opponent.credits = 500
        s.advance_visitors(game)
        offered = s.visitors(game, "rival")
        before = game.opponent.credits
        s.ai_orders(game, "rival")
        staff = s.employed(game, "rival")
        self.assertTrue(staff)
        self.assertTrue(all(p in offered and p.system_id is not None for p in staff))
        self.assertEqual(before-game.opponent.credits, sum(p.spec.hiring_fee for p in staff))

    def test_private_specialist_news_is_not_leaked(self):
        game = self.game(with_ai=True)
        s.record(game, "rival", "Private rival expedition")
        self.assertFalse(any("Private rival" in e.detail for e in news.entries(game)))
        self.assertEqual(news.unread_count(game), 0)
        s.record(game, "player", "Your specialist arrived")
        self.assertEqual(news.unread_count(game), 1)
        news.mark_read(game)
        self.assertEqual(news.unread_count(game), 0)

    def test_lost_sites_do_not_expose_enemy_recovery_progress(self):
        from types import SimpleNamespace
        from orion.specialist_view import rows
        game = self.game(with_ai=True)
        p = self.recruit(game, "kaia_ren")
        s.assign(game, p.id, 0)
        site = s.site_at(game, 0)
        app = SimpleNamespace(game=game, specialist_tab="sites")
        self.assertEqual(rows(app), [site])
        game.planet_at(0, 2).owner = "rival"
        self.assertFalse(rows(app))
        site.surveyed, site.progress, site.recovered_by = s.SURVEY_WORK, site.spec.work, "player"
        self.assertEqual(rows(app), [site])  # Your own awarded discoveries remain history.

    def test_balance_migration_preserves_custom_values_and_research(self):
        old = balance.default_profile()
        old["version"] = 3
        del old["data"]["specialists"], old["data"]["expedition_sites"]
        del old["data"]["rules"]["specialists"], old["data"]["buildings"]["space_hub"]
        old["data"]["buildings"]["factory"]["industry"] = 17
        before = deepcopy(old)
        modern = balance.upgrade_profile(old)
        self.assertEqual(old, before)
        self.assertFalse(balance.validate(modern))
        self.assertEqual(modern["data"]["buildings"]["factory"]["industry"], 17)
        self.assertEqual(modern["data"]["technologies"], old["data"]["technologies"])

    def test_old_campaign_adds_empty_roster_without_changing_economy(self):
        game = self.game()
        payload = game.to_dict(); del payload["specialists"]
        restored = GameState.from_dict(payload, version=38)
        self.assertEqual(restored.empire_rates, game.empire_rates)
        self.assertFalse(s.employed(restored))
        self.assertFalse(s.visitors(restored))
        self.hub(restored)
        restored.advance_turn()
        self.assertEqual(len(s.visitors(restored)), 2)

    def test_editor_rejects_duplicate_names_profiles_and_invalid_rules(self):
        for section, identifier, field, value in (
            ("specialists", "mara_voss", "name", s.SPECIALISTS["ilyra_senn"].name),
            ("specialists", "mara_voss", "role", "admiral"),
            ("specialists", "kaia_ren", "survey", 0),
            ("expedition_sites", "sealed_station", "skill", "none"),
            ("rules", "specialists", "XP_PER_LEVEL", 0),
            ("rules", "specialists", "SOCIAL_VISIT_CHANCE", 101)):
            with self.subTest(field=field):
                profile = balance.default_profile()
                profile["data"][section][identifier][field] = value
                self.assertTrue(balance.validate(profile))

    def test_save_rejects_corrupt_specialists_sites_and_news(self):
        game = self.game()
        p = self.recruit(game, "kaia_ren")
        s.assign(game, p.id, 0)
        source = game.to_dict()
        index = next(i for i, p in enumerate(source["specialists"]["people"]) if p["id"] == "kaia_ren")
        mutations = [
            lambda d: d["people"].append(d["people"][0]),
            lambda d: d["people"][index].update(xp=-1),
            lambda d: d["people"][index].update(xp=True),
            lambda d: d["people"][index].update(owner="unknown"),
            lambda d: d["people"][index].update(system_id=True),
            lambda d: d["people"][index].update(planet_id=2),
            lambda d: d["people"][index].update(visitor="player"),
            lambda d: d["sites"].append(d["sites"][0]),
            lambda d: d["sites"][0].update(progress=1),
            lambda d: d["sites"][0].update(recovered_by="player"),
            lambda d: d["sites"][0].update(known_by=[]),
            lambda d: d.update(news_read=500),
            lambda d: d["events"][0].update(turn=999),
        ]
        for i, mutate in enumerate(mutations):
            with self.subTest(case=i):
                data = deepcopy(source); mutate(data["specialists"])
                with self.assertRaises(SaveError): GameState.from_dict(data)


class SpecialistUITests(SpecialistFixtures, unittest.TestCase):
    def test_hiring_assigning_and_hub_navigation_use_live_buttons(self):
        import pygame as pg
        from orion.app import App
        app = App(self.root, capture=True)
        self.addCleanup(pg.quit); self.addCleanup(app.audio.close)
        app.game = self.game()
        self.hub(app.game); s.advance_visitors(app.game)
        app.game.credits = 500
        app.open_planet(2); app.render()
        def click(key):
            app.render()
            button = next(b for b in app.buttons if b.key == key)
            self.assertTrue(button.enabled)
            button.action(); app.render()
        click("surface_space_hub")
        self.assertEqual(app.screen, "specialists")
        selected = s.person(app.game, app.specialist_selected)
        self.assertEqual(selected.spec.role, "leader")
        click("specialist_hire")
        self.assertEqual(app.specialist_tab, "hired")
        click("specialist_assign_0_2")
        self.assertEqual(selected.planet_id, 2)
        click("specialist_unassign")
        self.assertIsNone(selected.planet_id)
        self.assertTrue(app.storage.list_saves())
        app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE, mod=0))
        self.assertEqual(app.screen, "planet")
        app.open_empire(); click("empire_specialists")
        self.assertEqual(app.screen, "specialists")


if __name__ == "__main__":
    unittest.main()

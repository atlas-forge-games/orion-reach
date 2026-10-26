# v0.83 validation

The unmodified v0.82 source and the v0.83 implementation were both exercised
under Python 3.12.14, pygame-ce 2.5.8 and pytest 9.1.1 with dummy SDL video/audio.

The full regression comparison completed in 335 seconds for v0.83 and reported
exactly the same **31 failing test methods** as the unchanged baseline. No new
failing methods appeared in that full run. This is not an all-green repository:
existing failures include historical save-version assertions, old combat
fixtures and unrelated interface expectations.

Final focused checks additionally cover the facility-based interdiction limits
when loading an in-flight save, shield regeneration using only powered generators,
construction catalogue pagination, inspector details and old-profile validation.
Those were run after the full comparison. See the release results below.

Final release results: **18 new research tests and 137 subtests passed**. Another
**86 targeted regression test methods passed**, covering the research interface,
navigation, siege, megastructures, population display, production breakdowns,
building information and fixed surface construction. A recovery-tick fixture was
corrected to advance the real game turn before its save roundtrip; the complete
18-test research file was rerun successfully afterward.

Visual inspection: six-field overview, Industry's three-choice detail screen and
building unlock inspector rendered with the actual game code. Controls were
also exercised at 980×900, 1280×800 and 1920×1080. The six new artwork files are
unchanged RGBA PNGs with verified dimensions, alpha bounds and SHA-256 checksums.
All Python source compiles. No commit or push was performed.

## Baseline failures retained

- `tests.test_administration.AdministrationTests::test_save_roundtrip_retains_remaining_turns`
- `tests.test_ai.AIRulesTests::test_start_is_distant_deterministic_and_preserves_generated_worlds`
- `tests.test_audio.AudioTests::test_bundled_mp3_streams_and_muting_resumes_without_reloading`
- `tests.test_audio.MusicInterfaceTests::test_screen_changes_keep_playing_and_do_not_change_campaign_state`
- `tests.test_audio.MusicInterfaceTests::test_settings_controls_survive_restart_and_music_is_independent_of_clicks`
- `tests.test_balance_editor.BalanceTests::test_saved_balance_survives_later_edits_and_browsing_other_saves`
- `tests.test_building_economy.BuildingEconomyTests::test_debt_save_roundtrip_and_old_versions_still_reject_negative_banks`
- `tests.test_combat_geometry.SaveAndSimulationTests::test_multicell_campaign_round_trip_and_overlaps_are_validated`
- `tests.test_encounters.EncounterSaveTests::test_real_save_file_roundtrip_keeps_search_and_private_warning`
- `tests.test_encounters.EncounterSaveTests::test_version_48_migration_keeps_new_encounters_disabled`
- `tests.test_fuel_range.TravelSaveTests::test_v14_fast_and_pending_voyages_keep_eta_and_can_be_cancelled_or_resumed`
- `tests.test_galaxy_layout.RectangularGalaxyTests::test_isolated_empires_can_research_tanks_without_moving_the_map`
- `tests.test_hyperlanes.HyperlaneSaveTests::test_version_45_migrates_without_rewriting_source_and_current_round_trips`
- `tests.test_monsters.GuardianSaveTests::test_v15_load_does_not_add_guardians_or_change_worlds_and_orders`
- `tests.test_monsters.GuardianSaveTests::test_v16_guardians_remain_unchanged_when_loaded`
- `tests.test_mothership_boarding.MothershipBoardingTests::test_live_resolved_captured_saves_and_old_unarmed_battle_migrate`
- `tests.test_motherships.HabitatRulesTests::test_legacy_active_battle_is_preserved_until_home_conversion_is_safe`
- `tests.test_observer.ObserverRulesTests::test_v039_saves_remain_normal_player_campaigns`
- `tests.test_planet_overview.WorkforceSaveTests::test_v11_migrates_both_current_worlds_and_stale_surveys_and_preserves_source`
- `tests.test_population.PopulationSaveTests::test_v10_migrates_planets_and_surveys_without_rewriting_or_losing_fields`
- `tests.test_production_queue.TradeGoodsTests::test_save_roundtrip_and_real_v34_schema_migration_include_surveys`
- `tests.test_races.RaceSetupTests::test_all_portraits_and_fallback_seals_render_and_foodless_workers_are_clear`
- `tests.test_research_expansion.AccuracyTests::test_targeting_range_evasion_and_specialized_guidance`
- `tests.test_research_progression.ProgressionTests::test_real_v055_profile_keeps_choices_prices_and_active_research_when_loaded`
- `tests.test_starships.CarrierCombatTests::test_drones_move_and_fire_and_point_defense_reduces_their_damage`
- `tests.test_starting_fleets.PendingDepartureTests::test_v13_saves_keep_existing_fleets_and_committed_journeys_without_gifts`
- `tests.test_statistics.StatisticsRulesTests::test_save_load_and_continuation_preserve_all_samples`
- `tests.test_tactical_combat.TacticalRulesTests::test_v12_battle_migration_preserves_damage_actions_and_source_bytes`
- `tests.test_tomb_worlds.SaveTests::test_v21_load_keeps_existing_campaign_without_reseeding_tombs`
- `tests.test_varkesh.SlaveSaveTests::test_real_storage_roundtrip_includes_slaves_and_news`
- `tests.test_victory.VictorySaveTests::test_v8_upgrade_preserves_in_flight_ships_damaged_combat_and_research`

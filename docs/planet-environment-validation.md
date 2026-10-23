# Planet environments validation — v0.78

## Results

Verified with Python 3.12 and pygame-ce 2.5.8, using SDL dummy video/audio.

| Run | Tests | Passed | Failures | Errors |
| --- | ---: | ---: | ---: | ---: |
| Unchanged v0.77 baseline, complete suite | 1,354 | 1,331 | 19 | 4 |
| Final v0.78, complete suite | 1,368 | 1,345 | 19 | 4 |
| Focused environment, home, AI, exploration, diplomacy, research and persistence suite | 139 | 137 | 2 | 0 |

**All 14 new environment tests pass.** The complete run has exactly the same
23 failing test identities and failure/error categories as the unchanged
baseline. The full suite is not clean; this update does not resolve unrelated
baseline failures. The final complete run took 276.032 seconds.

The two failures in the focused run were also reproduced individually against
the unchanged v0.77 baseline: the synthetic v5 diplomacy-save migration and
v16 guardian-battle migration. Older tests can depend on the active balance
profile established by preceding tests, so their focused and full-suite results
can differ.

## Coverage and corrections

The new tests cover all species/biome entries, food-driven growth, Nexus
assembly, Aetheri passive growth, full-colony limits, player/AI native homes,
Skirr toxic food and its production breakdown, mixed resident species,
mobile-habitat neutrality, unchanged settlement gates, actual Toxic colonization,
AI planet quality, deterministic generation and continuation, v54/profile18
migration, and campaign-specific custom balance settings.

The existing late-rival regression exposed a stale-survey terrain mismatch;
native-home initialization now updates charted terrain without refreshing stale
population or ownership. The corrected test verifies the Ice world and a valid
save round trip.

Older expected values were updated where the feature intentionally changes
behavior: Aelari starting farmer allocation, Gaia and Ice growth, Skirr food,
and AI research/expansion timing. The v1 synthetic fixture excludes Toxic
seeding because that historical save schema did not store individual worlds.
AI long-run checks continue to require real expansion and development while
allowing the enabled civilization victory to finish before science victory.

## Commands

Run from the project root, with the project and tests directories on PYTHONPATH:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1 \
  PYTHONPATH=.:tests python3 -m unittest discover -s tests -v

SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1 \
  PYTHONPATH=.:tests python3 -m unittest \
  test_environments test_home_systems test_diplomacy test_research \
  test_monsters test_exploration test_prototype test_ai -v

python3 tools/preview_environments.py
```

## Visual and package checks

- Rendered and inspected Skirr race selection, new-game setup, its native Toxic
  home, a developed Toxic colony, colony management and a Terran Toxic survey.
- Moved the colony efficiency caption below the navigation underline to avoid
  overlap. Landscape proportions and building click areas remain intact.
- The existing asset tests pass for all eight landscapes, including dimensions,
  aspect-ratio cropping, caching and missing/corrupt-image fallbacks.
- All 30 changed Python modules compile.
- The Toxic PNG matches its manifest: 2171 × 724, RGB, 3,460,079 bytes;
  SHA-256 `fe2c80df7a4801012496e06df8d28aea71efe4ba88af6cd7ba78df95359d81cb`.
- The ZIP contains only changed/new release files relative to v0.77. It excludes
  saves, settings, custom balance profiles, caches, test logs and QA screenshots.
  Archive integrity and every included file's bytes are checked after creation.

The reconstructed checkout lacks some original portraits, building art and
music files; visual inspection used the existing fallbacks where necessary.
The update does not replace those assets in the user's complete installation.

## Unchanged failures in the complete baseline and final suite

- **FAIL**: `test_all_portraits_and_fallback_seals_render_and_foodless_workers_are_clear (test_races.RaceSetupTests.test_all_portraits_and_fallback_seals_render_and_foodless_workers_are_clear)`
- **ERROR**: `test_bundled_mp3_streams_and_muting_resumes_without_reloading (test_audio.AudioTests.test_bundled_mp3_streams_and_muting_resumes_without_reloading)`
- **FAIL**: `test_debt_save_roundtrip_and_old_versions_still_reject_negative_banks (test_building_economy.BuildingEconomyTests.test_debt_save_roundtrip_and_old_versions_still_reject_negative_banks)`
- **ERROR**: `test_drones_move_and_fire_and_point_defense_reduces_their_damage (test_starships.CarrierCombatTests.test_drones_move_and_fire_and_point_defense_reduces_their_damage)`
- **ERROR**: `test_legacy_active_battle_is_preserved_until_home_conversion_is_safe (test_motherships.HabitatRulesTests.test_legacy_active_battle_is_preserved_until_home_conversion_is_safe)`
- **ERROR**: `test_live_resolved_captured_saves_and_old_unarmed_battle_migrate (test_mothership_boarding.MothershipBoardingTests.test_live_resolved_captured_saves_and_old_unarmed_battle_migrate)`
- **FAIL**: `test_multicell_campaign_round_trip_and_overlaps_are_validated (test_combat_geometry.SaveAndSimulationTests.test_multicell_campaign_round_trip_and_overlaps_are_validated)`
- **FAIL**: `test_real_save_file_roundtrip_keeps_search_and_private_warning (test_encounters.EncounterSaveTests.test_real_save_file_roundtrip_keeps_search_and_private_warning)`
- **FAIL**: `test_real_storage_roundtrip_includes_slaves_and_news (test_varkesh.SlaveSaveTests.test_real_storage_roundtrip_includes_slaves_and_news)`
- **FAIL**: `test_real_v055_profile_keeps_choices_prices_and_active_research_when_loaded (test_research_progression.ProgressionTests.test_real_v055_profile_keeps_choices_prices_and_active_research_when_loaded)`
- **FAIL**: `test_save_load_and_continuation_preserve_all_samples (test_statistics.StatisticsRulesTests.test_save_load_and_continuation_preserve_all_samples)`
- **FAIL**: `test_save_roundtrip_and_real_v34_schema_migration_include_surveys (test_production_queue.TradeGoodsTests.test_save_roundtrip_and_real_v34_schema_migration_include_surveys)`
- **FAIL**: `test_save_roundtrip_retains_remaining_turns (test_administration.AdministrationTests.test_save_roundtrip_retains_remaining_turns)`
- **FAIL**: `test_screen_changes_keep_playing_and_do_not_change_campaign_state (test_audio.MusicInterfaceTests.test_screen_changes_keep_playing_and_do_not_change_campaign_state)`
- **FAIL**: `test_settings_controls_survive_restart_and_music_is_independent_of_clicks (test_audio.MusicInterfaceTests.test_settings_controls_survive_restart_and_music_is_independent_of_clicks)`
- **FAIL**: `test_targeting_range_evasion_and_specialized_guidance (test_research_expansion.AccuracyTests.test_targeting_range_evasion_and_specialized_guidance)`
- **FAIL**: `test_v10_migrates_planets_and_surveys_without_rewriting_or_losing_fields (test_population.PopulationSaveTests.test_v10_migrates_planets_and_surveys_without_rewriting_or_losing_fields)`
- **FAIL**: `test_v12_battle_migration_preserves_damage_actions_and_source_bytes (test_tactical_combat.TacticalRulesTests.test_v12_battle_migration_preserves_damage_actions_and_source_bytes)`
- **FAIL**: `test_v13_saves_keep_existing_fleets_and_committed_journeys_without_gifts (test_starting_fleets.PendingDepartureTests.test_v13_saves_keep_existing_fleets_and_committed_journeys_without_gifts)`
- **FAIL**: `test_v16_guardians_remain_unchanged_when_loaded (test_monsters.GuardianSaveTests.test_v16_guardians_remain_unchanged_when_loaded)`
- **FAIL**: `test_v8_upgrade_preserves_in_flight_ships_damaged_combat_and_research (test_victory.VictorySaveTests.test_v8_upgrade_preserves_in_flight_ships_damaged_combat_and_research)`
- **FAIL**: `test_version_45_migrates_without_rewriting_source_and_current_round_trips (test_hyperlanes.HyperlaneSaveTests.test_version_45_migrates_without_rewriting_source_and_current_round_trips)`
- **FAIL**: `test_version_48_migration_keeps_new_encounters_disabled (test_encounters.EncounterSaveTests.test_version_48_migration_keeps_new_encounters_disabled)`

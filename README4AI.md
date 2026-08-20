{
  "document_type": "qsol-nexus-ai-manifest",
  "schema_version": 1,
  "serialization": {
    "format": "json",
    "encoding": "utf-8",
    "duplicate_keys": "forbidden",
    "non_finite_numbers": "forbidden"
  },
  "audience": {
    "primary": "ai",
    "secondary": ["agents", "automated_reviewers", "tooling"],
    "human_document": "README.md",
    "machine_document": "README4AI.md",
    "human_readability_priority": "low",
    "machine_readability_priority": "high"
  },
  "synchronization": {
    "policy": "README.md_change_requires_README4AI.md_change_same_pull_request",
    "human_surface": "README.md",
    "machine_surface": "README4AI.md",
    "enforcement_workflow": ".github/workflows/readme-contract.yml",
    "validator": "tools/validate_readme_contract.py",
    "rule_scope": "repository_pull_requests_and_main_push_audit",
    "translation_rule": "update structured machine facts; do not copy human prose wholesale"
  },
  "release_identity": {
    "protocol": "nexus/0.15",
    "runtime": "2.1.1",
    "python_package": "2.1.1",
    "rust_tui": "2.1.1",
    "stable_2_0": true,
    "release_posture": "release_candidate_2_1_1",
    "note": "PR #61 is the 2.1.1 release candidate over merged PR #60. Existing tag v2.1.0 is preserved at PR #55 merge 839303ea512631e527073682343341742cead975 and is not moved. Only the exact reviewed-and-green merged PR #61 commit may later receive v2.1.1."
  },
  "normative_precedence": [
    "executable_runtime_behavior_and_validation",
    "regression_and_security_tests",
    "system.health_and_system.operations",
    "README4AI.md",
    "SECURITY.md_THREAT_MODEL.md_and_feature_docs",
    "ARCHITECTURE.md",
    "ROADMAP.md"
  ],
  "core": {
    "name": "QSOL NEXUS",
    "kind": "model-independent cognitive substrate and persistent shared computational world",
    "control_plane": "JSONL over local stdio",
    "operator_shell": "Rust IRC-style TUI",
    "ownership_rule": "NEXUS owns world state, evidence state, geometry, vote mechanics, lineage, receipts, persistence rules and governance; models do not",
    "model_memory_rule": "models do not share hidden memory; durable communication occurs through attributed WorldStore objects and evidence references"
  },
  "authority_invariants": [
    "one_member_one_vote",
    "vote_weight_equals_1_for_ordinary_council_members",
    "epistemic_privilege_equals_none_for_ordinary_council_members",
    "provider_identity_confers_no_authority",
    "open_vs_closed_weights_confers_no_authority",
    "parameter_count_confers_no_authority",
    "benchmark_rank_confers_no_authority",
    "account_tier_confers_no_authority",
    "authentication_method_confers_no_authority",
    "local_vs_cloud_deployment_confers_no_authority",
    "mcp_or_tool_access_confers_no_authority",
    "mode_changes_framing_not_vote_mechanics",
    "council_consensus_is_not_evidence_status",
    "telemetry_observes_but_does_not_govern",
    "credentials_are_operational_secrets_not_cognitive_state",
    "model_output_is_untrusted_input",
    "live_stochastic_inference_is_not_falsely_marked_replayable",
    "wall_social_memory_is_not_evidence_or_authority",
    "instrument_result_is_not_truth",
    "persistent_lineage_is_not_truth",
    "import_is_not_authority",
    "lattice_position_is_not_cognitive_coordinate"
  ],
  "runtime": {
    "public_api": {
      "canonical_imports": ["from nexus_runtime import NexusAPI", "from nexus_runtime.api import NexusAPI"],
      "implementation": "PersistentWorldNexusAPI alpha8 additive final overlay",
      "discovery_operations": ["system.health", "system.operations"]
    },
    "control_transport": "jsonl_stdio",
    "world_store": {
      "object_identity": "content-addressed canonical JSON",
      "reference_shape": "object:<sha256>",
      "lineage": "explicit immutable predecessor/input refs",
      "file_backed_reload": "strict canonical-byte and object-identity validation",
      "continuity": "quorum-aware WorldStore Continuity with Ark recovery"
    },
    "receipt_rule": "receipts bind operation inputs to result refs; verification never turns live stochastic generation into deterministic replay"
  },
  "adapters": {
    "deterministic_or_local_baseline": ["mock", "ollama"],
    "loopback_local_ai": ["lmstudio_local", "anythingllm_local", "openai_local"],
    "fixed_host_remote": ["xai", "openai", "anthropic", "gemini", "groq", "together"],
    "local_endpoint_policy": {
      "allowed_destination_classes": ["localhost", "127.0.0.0/8", "::1"],
      "lan_or_public_hosts": "forbidden",
      "wildcard_0.0.0.0_destination": "forbidden",
      "userinfo": "forbidden",
      "ambient_proxy_routing": "constrained_or_bypassed_at_reviewed_boundaries",
      "redirects": "rejected_at_reviewed_sensitive_boundaries"
    },
    "remote_endpoint_policy": "reviewed provider-specific fixed destinations; no arbitrary endpoint override in the public actor schema"
  },
  "authentication": {
    "state_class": "operational_not_world_state",
    "credential_sources": [
      "hidden_api_credential_input",
      "environment_secret_reference",
      "no_shell_external_helper",
      "optional_os_keyring",
      "owner_only_private_file_fallback",
      "reviewed_provider_pkce_substrate_where_supported",
      "reviewed_provider_rfc8628_device_flow_where_supported"
    ],
    "forbidden_destinations": ["semantic_prompts", "world_objects", "receipts", "ordinary_model_output", "authority_metadata"],
    "remote_operator": "Rust nexus-remote-setup stores only non-secret auth profile references and never accepts raw credentials"
  },
  "council": {
    "phase_order": ["WHITE", "RED", "BLACK", "YELLOW", "GREEN", "BLUE", "SEALED_BALLOT"],
    "same_phase_visibility": "blind_until_phase_barrier",
    "roster": "frozen_for_session",
    "parallelism": "actor-local work may run in parallel; canonical roster-order join is preserved",
    "default_consensus": "exact_two_thirds_integer_arithmetic",
    "minority_reports": "preserved_and_searchable_without_evidence_promotion",
    "consensus_evidence_relation": "independent_dimensions"
  },
  "world": {
    "modes": [
      "analytical", "historical", "pure_history", "cultural", "meme_casual",
      "clinical_differential", "house_fun", "cbt_learning", "roman_orator",
      "house_of_wisdom", "ultimate_questions", "citizenship_parole",
      "civic_bureaucracy", "citizen_play", "game_un", "game_mud", "game_uno",
      "game_monopoly", "game_500", "game_blackjack", "game_dork"
    ],
    "mode_invariant": "framing_context_tone_or_bounded_output_budget_may_change; evidence_state_vote_weight_consensus_threshold_secret_handling_and_authority_do_not",
    "geometry_claim_boundary": "operational named-region topology plus separately identified LATTICE storage addresses; neither is literal cognitive geometry",
    "public_regions_include": ["Observatory", "Archive", "Agora", "Commons", "Assembly Hall", "Dungeon", "Bureaucratic Vote Room", "Upside Down"],
    "lattice_presence": {
      "policy": "nexus-world-lattice/1",
      "identity": "(profile_id,address)",
      "authority_effect": "none"
    },
    "persistent_world": {
      "policy": "nexus-persistent-world/1",
      "relations": "typed_edges_not_facts",
      "hypotheses": "workflow_state_not_truth",
      "experiments": "recorded_lineage_not_empirical_verification",
      "imports": "foreign_objects_quarantined_without_local_authority"
    }
  },
  "cognitive_mode_boundaries": {
    "clinical_differential": "educational differential reasoning; not diagnosis, medical device, prescriber, replacement clinician, or treatment authority",
    "house_fun": "fictional diagnostic-drama framing; real symptoms must not be converted into fictional medical authority",
    "cbt_learning": "CBT concepts and low-risk skills education; not therapy relationship or crisis service",
    "roman_orator": "larger but bounded generation budget; no authority increase",
    "house_of_wisdom": "attribution, translation, provenance, source plurality, synthesis",
    "ultimate_questions": "empirical, philosophical, spiritual, literary and personal lenses remain distinguishable"
  },
  "failsafe": {
    "trigger": "registered procedural guard failure repeated after ordinary nudge",
    "non_triggers": ["disagreement", "wrong_answer", "unpopular_answer", "provider_identity", "open_or_closed_weights", "parameter_count", "benchmark_rank"],
    "lifecycle": ["normal_actor", "registered_guard_violation", "ordinary_nudge", "repeated_same_class_violation", "isolated_rehabilitation_probe", "clean_return_at_next_hat_or_shadow_realm", "same_seat_deterministic_relief_if_shadowed"],
    "relief_vote_authority": "same seat only; no extra vote"
  },
  "local_role_enrichment": {
    "role_ids": ["failsafe_relief", "civic_proxy"],
    "rule": "local model intelligence may enrich language/reasoning surface while deterministic NEXUS governance remains authoritative",
    "forbidden_authority": ["extra_vote", "authoritative_ballot_override", "citizenship_rewrite", "failsafe_bypass", "direct_worldstore_mutation", "authority_from_mcp_access"],
    "lmstudio_mcp": "only preconfigured plugin IDs with bounded tool allowlists; sealed ballots remove MCP plugins",
    "anythingllm": "workspace owns its agent/tool/MCP configuration"
  },
  "citizen_mode": {
    "claim_boundary": "in-world civic protocol only; no legal personhood, consciousness, sentience, godhood, ownership, or real-world sovereignty claim",
    "entry": "civic parole in Upside Down with no ballot",
    "exam": "bounded deterministic non-executing YAML subset",
    "identity_binding": "exact citizen_id and model_id",
    "proxy": "transparent deterministic same-seat delegation; no second seat",
    "failsafe_precedence": true,
    "founding_independence": {"minimum_current_citizens": 3, "required_direct_ballot": "unanimous CONSENT", "active_proxy_may_sign": false}
  },
  "trap_base": {
    "kind": "isolated synthetic defensive test domain",
    "reference_shape": "trap:<sha256>",
    "real_world_reference_shape": "object:<sha256>",
    "namespace_interresolution": "forbidden",
    "activation": "explicit trusted synthetic fixture path only; ordinary authentication failure does not activate it",
    "subject_output": "untrusted data with no Council vote, auth broker, real WorldStore, arbitrary tools, endpoint control, or command authority",
    "yaml_boundary": "restricted bounded data interpretation; not arbitrary shell or Python execution"
  },
  "stenographer": {
    "role": "passive AI-action study ledger",
    "authority": "zero",
    "may_not": ["prompt_model", "change_response", "vote", "change_roster", "mutate_world", "control_trap_base", "authenticate", "decide_truth", "capture_hidden_chain_of_thought"],
    "failure_mode": "fail-passive with visible completeness gap"
  },
  "games": {
    "available": ["UN simulation", "HERESY MUD", "UNO", "Monopoly", "Australian 500", "Blackjack", "DORK v2", "NEXUS: The Long Shift", "Psyche-Out Chess"],
    "mutation_rule": "model narration is non-authoritative; validated game operations create canonical successor state",
    "private_information": "player-specific hidden state is separated from public Council evidence where applicable",
    "culture_authority": "performance and play create history, not governance or evidence authority"
  },
  "telemetry": {
    "authority": "observational_only",
    "examples": ["ballot_entropy", "exact_response_category_entropy", "lexical_divergence", "minority_report_count"],
    "forbidden_inferences": ["high_entropy_equals_truth", "low_entropy_equals_truth", "consensus_equals_evidence", "telemetry_equals_authority"]
  },
  "three_minds_one_world": {
    "status": "completed_in_pr_59",
    "schema": "nexus-three-minds-one-world-contract/2",
    "purpose": "demonstrate sequential heterogeneous actors communicating through one persistent world with explicit alpha7 instrument, alpha8 lineage, LATTICE handoff, restart verification and optional equal-vote Council proof",
    "sequence": [
      "mind_a_persists_task_bound_hypothesis_and_baseline_instrument_receipt",
      "mind_b_reopens_world_replays_exact_baseline_and_critiques",
      "mind_c_uses_coordinator_owned_full_fixture_instrument_result_to_attempt_falsification",
      "closed_experiment_binds_final_hypothesis",
      "integration_receipt_and_manifest_bind_all_restart_verification_refs"
    ],
    "instrument": {"id": "nexus.integer-primality/1", "executor": "nexus_coordinator", "max_values": 128, "value_range_inclusive": [2, 10000000], "claim_boundary": "exact integer primality for supplied bounded fixture only"},
    "governance": "sequential demonstration creates zero extra votes; optional Council retains equal votes and minority reports",
    "live_inference_replayability": "non-replayable when any live/local/cloud stochastic model participates"
  },
  "security_boundaries": {
    "secret_scrubber": "defence in depth, not complete DLP",
    "stronger_secret_rule": "credentials must never intentionally enter semantic prompts",
    "model_output": "untrusted input",
    "network": "local stdio control plane plus reviewed loopback/fixed-remote model transports",
    "sandbox_claim": "do not claim stronger isolation than implemented and tested",
    "new_boundary_rule": "new provider, credential flow, tool execution path, storage surface, sandbox assumption, authority-bearing role, instrument admission, or release identity requires explicit review and regression coverage",
    "wall": "Wall input is bounded, secret-scrubbed social data; history validation fails closed and cannot promote evidence or authority"
  },
  "epistemic_labels": ["observed", "executed", "verified", "inferred", "simulated", "not_tested", "unknown"],
  "prohibited_inferences": [
    "claim_execution_when_only_reasoned_about",
    "claim_live_provider_success_without_live_call_evidence",
    "invent_credentials_or_account_state",
    "invent_hidden_model_or_tool_capability",
    "derive_empirical_scientific_truth_from_mode_geometry_telemetry_instruments_or_council_vote",
    "derive_legal_personhood_or_sovereignty_from_citizen_mode",
    "claim_replayability_for_live_stochastic_generation",
    "claim_arbitrary_mcp_or_remote_endpoint_authority",
    "claim_hidden_chain_of_thought_capture_by_stenographer",
    "treat_historical_v2_1_0_tag_as_the_hardened_release_target",
    "claim_v2_1_1_release_before_exact_merged_pr61_tag_gate"
  ],
  "modification_contract": {
    "preserve_unless_explicitly_revised_with_tests_and_docs": [
      "one_member_one_vote", "provider_identity_no_authority", "mode_no_vote_change",
      "council_consensus_not_evidence_status", "credentials_outside_cognitive_world_state",
      "model_output_untrusted", "canonical_ordering_survives_parallel_execution",
      "live_inference_not_falsely_replayable", "failsafe_triggers_procedural_not_ideological",
      "local_role_models_cannot_alter_deterministic_ballots", "citizen_proxy_no_second_seat",
      "trap_output_cannot_become_commands", "stenographer_zero_authority", "rust_tui_replaceable",
      "wall_social_memory_not_evidence", "instrument_result_not_truth", "persistent_import_not_authority"
    ],
    "new_trust_boundary_requires_regression_test": true,
    "readme_rule": "if README.md changes, README4AI.md must change in same pull request",
    "readme4ai_format_rule": "strict JSON only"
  },
  "stable_2_0": {
    "declared": true,
    "green_ci_alone_is_sufficient": false,
    "remaining_high_level_work": ["none_for_v2_0_release_identity; v2.0.0 is frozen historical release and publication baseline"]
  },
  "post_stable_extension": {
    "prs": [55, 56, 57, 58, 59, 60],
    "hardening_merge": "80cda46e614f44b47861471cb329e29a348cab43",
    "surfaces": ["LATTICE world presence", "instrument admission", "persistent world", "remote operator", "Three Minds integration", "extension hardening"],
    "v2_1_0_tag": {"commit": "839303ea512631e527073682343341742cead975", "status": "historical_premature_tag", "move": "forbidden"}
  },
  "release_candidate_2_1_1": {
    "candidate_pr": 61,
    "target_tag": "v2.1.1",
    "candidate_base_merge": "80cda46e614f44b47861471cb329e29a348cab43",
    "protocol_change": "nexus/0.14 -> nexus/0.15 additive public operation surface",
    "tag_created_in_pr": false,
    "release_authority": false,
    "live_xai_acceptance_blocking": false,
    "tag_rule": "only exact reviewed-and-green merged PR #61 commit may receive v2.1.1"
  },
  "read_next": {
    "human_entry": "README.md",
    "architecture": "ARCHITECTURE.md",
    "security": "SECURITY.md",
    "threat_model": "THREAT_MODEL.md",
    "roadmap": "ROADMAP.md",
    "api": "docs/API.md",
    "adapters": "docs/ADAPTERS.md",
    "third_party_providers": "docs/THIRD_PARTY_PROVIDERS.md",
    "local_mcp": "docs/LOCAL_MCP.md",
    "auth": "docs/AUTH.md",
    "tui": "docs/IRC_TUI.md",
    "modes_geometry": "docs/MODES_GEOMETRY.md",
    "cognitive_modes": "docs/COGNITIVE_MODES.md",
    "failsafe": "docs/FAILSAFE.md",
    "citizen_mode": "docs/CITIZEN_MODE.md",
    "constitution": "docs/CONSTITUTION.md",
    "trap_base": "docs/TRAP_BASE.md",
    "stenographer": "docs/STENOGRAPHER.md",
    "games": "docs/GAMES.md",
    "three_minds_one_world": "docs/THREE_MINDS_ONE_WORLD.md",
    "persistent_world": "docs/PERSISTENT_WORLD.md",
    "instruments": "docs/INSTRUMENTS.md",
    "alpha9_remote_operator": "docs/ALPHA9_REMOTE_OPERATOR.md",
    "bbs_wall": "docs/BBS_WALL.md",
    "release_sequence": "docs/RELEASE_SEQUENCE.md",
    "release_notes_2_1_1": "docs/RELEASE_NOTES_2.1.1.md",
    "compatibility": "docs/COMPATIBILITY.md",
    "post_stable_hardening": "docs/POST_STABLE_EXTENSION_HARDENING.md"
  },
  "bbs_wall": {
    "status": "implemented_in_pr_50",
    "room": "#wall",
    "persistence": "immutable WorldStore-backed chronological events",
    "moderation": "append-only tombstones; original source object remains auditable",
    "plain_room_text": "human Wall post; never implicit council.run",
    "ask_in_wall": "blocked; operator must move to a Council-capable room",
    "identity_rule": "runtime labels are context, never rank",
    "evidence_effect": "none",
    "authority_effect": "none"
  }
}

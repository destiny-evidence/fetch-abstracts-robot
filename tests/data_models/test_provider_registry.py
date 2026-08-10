"""Tests for provider configuration assembly."""

from far import provider_data_models
from far.provider_data_models.generic import ExternalAPI, external_api_priority_batch


def test_get_all_provider_api_configs_returns_all_providers(test_settings):
    """Test that provider config assembly returns exactly the defined providers."""
    configs = provider_data_models.get_all_provider_api_configs(test_settings)
    assert {config.name for config in configs} == set(ExternalAPI)


def test_get_all_provider_api_configs_respects_priority_order(
    test_settings, monkeypatch
):
    """Test that output order follows priority regardless of construction order."""
    factories = provider_data_models.BATCH_PROVIDER_CONFIG_FACTORIES
    monkeypatch.setattr(
        provider_data_models,
        "BATCH_PROVIDER_CONFIG_FACTORIES",
        tuple(reversed(factories)),
    )
    configs = provider_data_models.get_all_provider_api_configs(test_settings)

    rank_map = external_api_priority_batch.priorities
    config_ranks = [rank_map[config.name] for config in configs]
    assert config_ranks == sorted(config_ranks)

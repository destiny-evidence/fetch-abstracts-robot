"""Tests for provider configuration assembly."""

from far.provider_data_models import get_all_provider_api_configs
from far.provider_data_models.generic import ExternalAPI


def test_get_all_provider_api_configs_returns_expected_order(test_settings):
    """Test that get_all_provider_api_configs returns the expected API configurations."""
    configs = get_all_provider_api_configs(test_settings)

    assert sorted([config.name for config in configs]) == sorted(ExternalAPI)

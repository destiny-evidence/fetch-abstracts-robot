"""Tests for PubMed API config in far/data_models/pubmed.py."""

from far.data_models.pubmed import get_pubmed_batch_api_config


def test_get_pubmed_batch_api_config_includes_tool_and_email(test_settings):
    config = get_pubmed_batch_api_config(test_settings)

    assert config.query_params["db"] == "pubmed"
    assert config.query_params["retmode"] == "json"
    assert config.query_params["tool"] == "fetch-abstracts-robot"
    assert config.query_params["email"] == str(test_settings.mailto)


def test_get_pubmed_batch_api_config_omits_email_when_missing(test_settings):
    no_email_settings = test_settings.model_copy(update={"mailto": None})

    config = get_pubmed_batch_api_config(no_email_settings)

    assert config.query_params["db"] == "pubmed"
    assert config.query_params["retmode"] == "json"
    assert config.query_params["tool"] == "fetch-abstracts-robot"
    assert "email" not in config.query_params

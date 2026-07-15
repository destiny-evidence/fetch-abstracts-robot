import pytest

from far.data_models.generic import ExternalAPI
from far.enhancement_processor import AbstractEnhancementProcessor
from far.local.config import set_up_processor


def test_set_up_processor_happy_path_success(test_settings):
    processor = set_up_processor(test_settings, excluded_apis=None)
    assert isinstance(processor, AbstractEnhancementProcessor)
    assert len(processor.available_api_configs) > 0


@pytest.mark.parametrize(
    "excluded_api", [[ExternalAPI.CROSSREF_BATCH], [ExternalAPI.SCOPUS_BATCH]]
)
def test_set_up_processor_exclude_single_api(test_settings, excluded_api):
    processor = set_up_processor(test_settings, excluded_apis=excluded_api)
    assert isinstance(processor, AbstractEnhancementProcessor)
    assert all(
        config.name.lower() != excluded_api[0].name.lower()
        for config in processor.available_api_configs
    )


def test_set_up_processor_exclude_all_apis(test_settings):
    all_excluded_apis = [ExternalAPI.CROSSREF_BATCH, ExternalAPI.SCOPUS_BATCH]
    with pytest.raises(SystemExit):
        set_up_processor(test_settings, excluded_apis=all_excluded_apis)

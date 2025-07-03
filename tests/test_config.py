"""tests for app/config.py."""

from app.config import get_settings


def test_get_settings(set_test_environment_variables: None) -> None:
    """
    Test the get_settings function.

    Args:
        set_test_environment_variables (None): Pytest fixture to test environment variables.

    """
    expected_env = "local"
    expected_destiny_repository_url = "http://localhost:8001/enhancement/"
    expected_robot_id = "e0aba318-eee9-4b4c-b503-7f72547063d8"
    expected_robot_secret = "dummy_secret"  # noqa: S105
    expected_elsevier_scopus_key = "dummy_scopus_key"

    settings = get_settings()

    assert settings.env == expected_env
    assert (
        settings.destiny_repository_url.encoded_string()
        == expected_destiny_repository_url
    )
    assert str(settings.robot_id) == expected_robot_id
    assert settings.robot_secret == expected_robot_secret
    assert (
        settings.elsevier_scopus_key.get_secret_value() == expected_elsevier_scopus_key
    )

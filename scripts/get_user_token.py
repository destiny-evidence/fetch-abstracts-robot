import time
from enum import StrEnum
from uuid import UUID

import msal
from loguru import logger
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Deployment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    destiny_robot_dev_auth_secret: SecretStr
    destiny_robot_dev_auth_app_id: UUID
    jt_ad_tenant_id: UUID
    destiny_repository_development_app_id: UUID
    destiny_repository_staging_app_id: UUID

    model_config = SettingsConfigDict(env_file="user_token.secrets", extra="ignore")


def get_settings() -> Settings:
    return Settings()


def get_device_flow(settings: Settings, deployment: Deployment) -> str:
    """
    Initiates the device flow for user authentication.
    Will open a browser and prompt the user for auth.

    Args:
            settings (Settings): The application settings.
            deployment (Deployment): The deployment environment.

    Returns:
            str: The access token.

    """
    if deployment == Deployment.DEVELOPMENT:
        repo_app_id = settings.destiny_repository_development_app_id
    elif deployment == Deployment.STAGING:
        repo_app_id = settings.destiny_repository_staging_app_id
    elif deployment == Deployment.PRODUCTION:
        error_message = "Production deployment not yet supported."
        raise NotImplementedError(error_message)

    authority = f"https://login.microsoftonline.com/{settings.jt_ad_tenant_id}"
    app = msal.PublicClientApplication(
        client_id=str(settings.destiny_robot_dev_auth_app_id), authority=authority
    )

    flow = app.initiate_device_flow(scopes=[f"api://{repo_app_id!s}/.default"])
    logger.info(flow["message"])
    time.sleep(30)
    token = app.acquire_token_by_device_flow(flow)
    logger.info(token.get("access_token"))

    return token.get("access_token")


def get_app_flow(settings: Settings) -> dict:
    """
    Initialise the app flow for a Client application.

    Args:
            settings (Settings): The application settings.

    Returns:
            str: The access token.

    """
    authority = f"https://login.microsoftonline.com/{settings.jt_ad_tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id=str(settings.destiny_robot_dev_auth_app_id),
        client_credential=settings.destiny_robot_dev_auth_secret.get_secret_value(),
        authority=authority,
    )

    token = app.acquire_token_for_client(
        scopes=[f"api://{settings.destiny_repository_staging_app_id!s}/.default"]
    )
    return token.get("access_token")


def main() -> None:
    settings = get_settings()
    # device flow now recommended for user-based token generation
    access_token = get_device_flow(settings, Deployment.STAGING)
    # access_token = get_app_flow(settings)
    logger.info(access_token)


if __name__ == "__main__":
    main()

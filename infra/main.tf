data "azurerm_container_registry" "destiny_shared_infra" {
  name                = var.container_registry_name
  resource_group_name = var.container_registry_resource_group_name
}

# This might exist for you if your robot has already been deployed.
# In this case, you can use a data resource instead https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/resource_group
resource "azurerm_resource_group" "robot_resource_group" {
  name     = "rg-${var.robot_name}-${var.environment}"
  location = "swedencentral"
  tags = {
    "Budget Code" = "destiny-evidence"
    "Created by" = "Harry Moss"
    "Owner" = "cceaoss@ucl.ac.uk"
    "Environment" = "warm"
    "Region" = "Sweden Central"
  }
}

# Create a user assigned identity for our robot. This is the identity used when authenticating.
resource "azurerm_user_assigned_identity" "fetch_abstracts_robot" {
  location            = azurerm_resource_group.robot_resource_group.location
  name                = var.robot_name
  resource_group_name = azurerm_resource_group.robot_resource_group.name
}

# This creates a container app to run the fetch abstracts robot in
module "container_app_fetch_abstracts_robot" {
  source                          = "app.terraform.io/destiny-evidence/container-app/azure"
  version                         = "1.6.2"
  app_name                        = var.robot_name
  environment                     = var.environment
  container_registry_id           = data.azurerm_container_registry.destiny_shared_infra.id
  container_registry_login_server = data.azurerm_container_registry.destiny_shared_infra.login_server
  resource_group_name             = azurerm_resource_group.robot_resource_group.name
  region                          = azurerm_resource_group.robot_resource_group.location

  # We're the api url for the destiny repository here, which the fetch abstracts robot will use to authenticate against.
  # The necessaary `AZURE_CLIENT_ID` environment variable is set by the container app module.
  env_vars = [
    {
      name  = "DESTINY_REPOSITORY_URL"
      value = var.destiny_repository_url
    },
    {
      name  = "ROBOT_ID"
      value = var.robot_id
    },
    {
      name        = "ROBOT_SECRET"
      secret_name = "robot-secret"
    }
  ]

  secrets = [
    {
      name  = "robot-secret",
      value = var.robot_secret
    }
  ]

  # Ingress changes will be ignored to avoid messing up manual custom domain config.
  # See https://github.com/hashicorp/terraform-provider-azurerm/issues/21866#issuecomment-1755381572.
  ingress = {
    external_enabled           = true
    allow_insecure_connections = false
    target_port                = 8001
    transport                  = "auto"
    traffic_weight = {
      latest_revision = true
      percentage      = 100
    }
  }

  # You can see here that we're passing the user assigned identity that we created above to the client application.
  # This identity has the robot role assignment and will allow the robot to authenticate with destiny repository.
  identity = {
    id           = azurerm_user_assigned_identity.fetch_abstracts_robot.id
    principal_id = azurerm_user_assigned_identity.fetch_abstracts_robot.principal_id
    client_id    = azurerm_user_assigned_identity.fetch_abstracts_robot.client_id
  }
}

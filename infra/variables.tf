variable "robot_name" {
  description = "Name of the robot."
}

variable "robot_id" {
  description = "The id the robot will send to destiny repository to identify itself."
}

variable "robot_secret" {
  description = "The secret the robot will use in HMAC auth with destiny repository."
  sensitive   = true
}

variable "elsevier_scopus_key" {
  description = "The Elsevier Scopus API key the robot will use to authenticate with the Scopus API."
  sensitive   = true
}

variable "elsevier_scopus_inst_token" {
  description = "The Elsevier Scopus institutional token the robot will use to authenticate with the Scopus API."
  sensitive   = true
}

variable "destiny_repository_url" {
  description = "Url to configure the robot to post callbacks to."
}

# Variables below this line are for deploying the fetch abstracts robot.
# These may not be necessary for your use case
variable "container_registry_name" {
  description = "Name of the container registry where fetch abstract robot images are pushed."

}

variable "container_registry_resource_group_name" {
  description = "Name of the container registry resource group."
}

variable "key_vault_name" {
  description = "Name of the Key Vault where fetch abstracts robot images are pushed."

}

variable "key_vault_resource_group_name" {
  description = "Name of the Key Vault resource group."
}

variable "github_actions_service_principal_object_id" {
  description = "The Object ID of the Azure Service Principal used by GitHub Actions to deploy the Incremental Updater App and App Job."
  type = string
}

variable "deployment_environment" {
  description = "Environment for the Fetch Abstracts Robot, should be either development, staging or production."
  default     = "development"
  type = string
  validation {
    condition     = contains(["development", "staging", "production"], var.deployment_environment)
    error_message = "Environment must be one of 'development', 'staging' or 'production'."
  }
}


variable "owner_name" {
  description = "Name of the owner of the robot."
}

variable "owner_email" {
  description = "Email of the owner of the robot."
}

variable "budget_code" {
  description = "Budget code for the robot."
}

variable "environment_description" {
  description = "Description of the environment the robot is deployed to."
  default     = "warm"
}

variable "region_friendly_name" {
  description = "Friendly name of the region the robot is deployed to."
  default     = "Sweden Central"
}

variable "poll_interval_seconds" {
  description = "Interval in seconds between polling the Scopus API for new abstracts."
  default     = "3600"
}

variable "batch_size" {
  description = "Number of abstracts to fetch in each batch."
  default     = "10"
}

locals {
  app_name = "incremental-updater"
  app_job_name = "job-openalex-refresh"
  minimum_resource_tags = {
    "Created by"  = var.owner_name
    "Environment" = var.deployment_environment
    "Owner"       = var.owner_email
    "Region" = var.region_friendly_name
  }
  extended_resource_tags = merge(local.minimum_resource_tags, {
    "Budget code" = var.budget_code
  })
}

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

variable "environment" {
  description = "Environment for the Fetch Abstracts Robot, should be either development, staging or production."
  default     = "development"
}

variable "subscription_id" {
  description = "The Azure subscription ID to use for the deployment."
  type        = string
}

variable "owner_name" {
  description = "Name of the owner of the robot."
}

variable "owner_email" {
  description = "Email of the owner of the robot."
}

variable "environment_description" {
  description = "Description of the environment the robot is deployed to."
  default     = "warm"
}

variable "region_friendly_name" {
  description = "Friendly name of the region the robot is deployed to."
  default     = "Sweden Central"
}

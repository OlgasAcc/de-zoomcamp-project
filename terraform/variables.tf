variable "credentials" {
  description = "My Credentials"
  default     = "gcp-creds.json"
  # Use commands defined in the README.md for gcp-creds.json file generation
}

variable "project" {
  description = "Project"
  default     = "terraform-demo-452019"
}

variable "region" {
  description = "Region"
  default = "us-central1"
}

variable "location" {
  description = "Project Location"
  default = "US"
}

variable "bq_dataset_name" {
  description = "Airplane delay BigQuery Dataset Name"
  default     = "airline_data"
}

variable "gcs_bucket_name" {
  description = "Airplane delay Storage Bucket Name"
  default     = "terraform-demo-452019-airline-delay-bucket"
}

variable "gcs_storage_class" {
  description = "Bucket Storage Class"
  default     = "STANDARD"
}
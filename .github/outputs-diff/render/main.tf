# Renders a datastream execution template exactly as schedules.tf does. No providers
# or backend, so terraform init/apply here need no credentials or network.

variable "template_path" { type = string }
variable "template_vars" { type = map(string) }

output "rendered" {
  value = templatefile(var.template_path, var.template_vars)
}

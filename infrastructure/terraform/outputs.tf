output "ecs_task_definition_family" {
  description = "Family of the ECS task definition"
  value       = module.ecs.task_definition_family
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.vpc.private_subnet_ids
}
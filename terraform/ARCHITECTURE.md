# AWS Architecture
Terraform is responsible for building the many cloud components that make up an AWS State Machine (seen below). 

![statemachine](docs/images/statemachine.jpg)

Each green box represents a distinct AWS Lambda function that is responsible for a task such as spawning an instance from an Amazon Machine Image or issuing commands to an instance. Together these lambdas coordinate the task of creating a cloud based host to which a user can issue commands. 

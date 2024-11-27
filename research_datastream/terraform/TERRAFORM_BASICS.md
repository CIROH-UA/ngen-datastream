# Terraform Basics

Terraform is an open-source **Infrastructure as Code (IaC)** tool that simplifies and automates the process of provisioning and managing cloud infrastructure. Instead of manually configuring resources through a cloud provider's console, Terraform enables you to define your infrastructure in human-readable code using its declarative language, **HashiCorp Configuration Language (HCL)**.

## Why Terraform?
Terraform provides several key advantages for managing infrastructure:
1. **Portability Across Cloud Providers**  
   Terraform's syntax is cloud-agnostic, which means you can use the same tool to manage resources across different providers like **AWS**, **Azure**, **Google Cloud Platform**, and many more. This makes it an ideal choice for multi-cloud strategies or transitioning between providers.

2. **Version Control**  
   Since infrastructure is defined as code, you can store it in repositories like GitHub, enabling versioning, collaboration, and peer review for changes to your infrastructure.

3. **Reproducibility**  
   With Terraform, you can define consistent and repeatable configurations, ensuring that your environments—whether for development, testing, or production—are identical.

4. **Scalability**  
   From managing a single server to orchestrating complex multi-region architectures, Terraform scales with your needs.

## How Terraform Works
At its core, Terraform operates in three stages:
1. **Write**: Define the infrastructure you need in `.tf` files. For the Research Datastream, this [file](https://github.com/CIROH-UA/ngen-datastream/blob/main/research_datastream/terraform/main.tf) is provided and does not need to be editted. 
2. **Plan**: Preview the changes Terraform will make before applying them.
3. **Apply**: Execute the changes to create, update, or destroy resources. 

Terraform uses **providers** to interact with specific cloud platforms or services. For this project, we’ll focus on AWS, where Terraform will manage resources like **EC2 instances**, **IAM roles**, **S3 buckets**, and more. However, the same Terraform principles can be applied to other cloud providers with only minor adjustments to your code.

## Resources to Learn More
Here are some helpful resources to deepen your understanding of Terraform:
- [Official Terraform Documentation](https://www.terraform.io/docs)
- [Learn Terraform on HashiCorp’s Website](https://learn.hashicorp.com/terraform)
- [AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

## Next Steps
Before getting started, make sure you have:
- [Terraform installed](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli)
- An AWS account with appropriate credentials
- Basic familiarity with cloud computing concepts (or review [this guide](https://aws.amazon.com/what-is-cloud-computing/))

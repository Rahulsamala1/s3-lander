
# Data Pipeline: S3 to BigQuery using Docker, AWS Fargate, Lambda, and GitHub Actions

This repository contains a serverless data pipeline to load data from **Amazon S3** into **Google BigQuery** using **AWS Fargate**, **Lambda**, **Docker**, and **GitHub Actions**. The Python code that performs the data extraction, transformation, and loading (ETL) is packaged inside a Docker container and deployed on Fargate.

## Overview

This project automates the process of:
1. Building and deploying a Docker image containing the Python code to handle data loading.
2. Using **GitHub Actions** for continuous integration and deployment.
3. Running the Dockerized Python application using **AWS Fargate**.
4. Optionally triggering the workflow with **AWS Lambda** when a new file is uploaded to an S3 bucket.
5. Transforming the data (if needed) and uploading it to **Google BigQuery**.

## Components

- **GitHub Actions**: Automates the CI/CD pipeline.
- **Docker**: Packages the Python app along with dependencies.
- **Amazon ECR**: Stores the Docker image.
- **AWS Fargate**: Runs the container in a serverless environment.
- **AWS Lambda**: Triggers the process when a new object is uploaded to an S3 bucket (optional).
- **S3**: Source of the data to be loaded into BigQuery.
- **BigQuery**: Target destination for the data.

## Requirements

- AWS account with permissions to use services like S3, Lambda, Fargate, and ECR.
- Google Cloud account with permissions to access BigQuery.
- GitHub repository with appropriate actions and workflows set up.

## Setup

### 1. Clone this repository
```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

### 2. Build Docker Image
You need to build the Docker image for the Python application.

```bash
docker build -t your-docker-image .
```

### 3. Push Docker Image to Amazon ECR
1. Create an ECR repository if you haven't already:

   ```bash
   aws ecr create-repository --repository-name your-repo-name
   ```

2. Authenticate Docker to your Amazon ECR registry:

   ```bash
   aws ecr get-login-password --region your-region | docker login --username AWS --password-stdin your-account-id.dkr.ecr.your-region.amazonaws.com
   ```

3. Tag your Docker image:

   ```bash
   docker tag your-docker-image:latest your-account-id.dkr.ecr.your-region.amazonaws.com/your-repo-name:latest
   ```

4. Push the image to ECR:

   ```bash
   docker push your-account-id.dkr.ecr.your-region.amazonaws.com/your-repo-name:latest
   ```

### 4. GitHub Actions Workflow
The repository includes a GitHub Actions workflow that will:
- Trigger on code changes (push, pull requests).
- Build and push the Docker image to Amazon ECR.
- Deploy the Docker container to AWS Fargate.

Ensure that your GitHub Actions workflow file (`.github/workflows/deploy.yml`) is correctly configured.

#### Example GitHub Actions Workflow (`deploy.yml`)
```yaml
name: Deploy to AWS Fargate

on:
  push:
    branches:
      - main

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v2

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v1

      - name: Log in to Amazon ECR
        uses: aws-actions/amazon-ecr-login@v1

      - name: Build and push Docker image
        run: |
          docker build -t ${{ secrets.ECR_REPOSITORY }} .
          docker tag ${{ secrets.ECR_REPOSITORY }}:latest ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com/${{ secrets.ECR_REPOSITORY }}:latest
          docker push ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com/${{ secrets.ECR_REPOSITORY }}:latest

      - name: Deploy to Fargate
        run: |
          aws ecs update-service --cluster your-cluster-name --service your-service-name --force-new-deployment
```

Make sure to update the workflow with your specific values and secrets (e.g., ECR repository, AWS account ID, region).

### 5. Deploying to AWS Fargate
To deploy the Docker container to AWS Fargate, follow these steps:
1. **Create ECS Cluster**: In the AWS Management Console, navigate to **ECS** and create a new ECS cluster. Choose the **Fargate** launch type.
2. **Create Task Definition**: In ECS, create a new task definition and specify the Docker image you pushed to ECR. Set the task's CPU and memory configuration according to your application's requirements.
3. **Create or Update ECS Service**: Create a new ECS service or update an existing one to use the new task definition. Ensure that the service is set to use the Fargate launch type.
4. **Deploy the service**: Once the ECS service is configured, AWS Fargate will automatically run your container without you having to manage EC2 instances.

### 6. Lambda Function (Optional)
If you want to trigger the process whenever new data is uploaded to an S3 bucket, you can create a Lambda function to handle the trigger and invoke the Fargate task.

#### Example Lambda Trigger Code (Optional)
```python
import boto3

def lambda_handler(event, context):
    # Assuming the Lambda function is triggered by an S3 event
    s3_event = event['Records'][0]
    s3_bucket = s3_event['s3']['bucket']['name']
    s3_key = s3_event['s3']['object']['key']

    # Logic to trigger Fargate task or interact with the Docker container
    client = boto3.client('ecs')
    
    response = client.run_task(
        cluster='your-cluster-name',
        taskDefinition='your-task-definition',
        launchType='FARGATE',
        overrides={
            'containerOverrides': [
                {
                    'name': 'your-container-name',
                    'environment': [
                        {'name': 'S3_BUCKET', 'value': s3_bucket},
                        {'name': 'S3_KEY', 'value': s3_key}
                    ]
                }
            ]
        },
        networkConfiguration={
            'awsvpcConfiguration': {
                'subnets': ['your-subnet-id'],
                'assignPublicIp': 'ENABLED'
            }
        }
    )
    return response
```



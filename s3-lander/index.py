import json
import urllib.parse
import boto3

s3 = boto3.client('s3')
ecs = boto3.client('ecs')

def handler(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        response = ecs.run_task(
            cluster='fargate',
            launchType = 'FARGATE',
            taskDefinition='s3_lander_test_td',
            count = 1,
            platformVersion='LATEST',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': [
                        'subnet-0bafb82750eb8f0f0',
                        'subnet-06513c5ac7d6db222'
                    ],
                    'assignPublicIp': 'DISABLED'
                }
            },
            overrides={
                'containerOverrides': [
                    {
                        'name': 's3_lander_test',
                        'environment': [
                            {
                                'name': 'S3_BUCKET',
                                'value': bucket
                            },
                            {
                                'name': 'S3_KEY',
                                'value': key
                            },
                        ]
                    }
                ]
            }
        )
    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
        raise e

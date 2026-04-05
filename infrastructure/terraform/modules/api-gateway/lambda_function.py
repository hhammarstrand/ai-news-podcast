import json
import os
import boto3


def handler(event, context):
    ecs_client = boto3.client("ecs")

    cluster = os.environ["ECS_CLUSTER"]
    task_def = os.environ["ECS_TASK_DEF"]
    subnet_ids = os.environ["SUBNET_IDS"].split(",")
    security_group_id = os.environ["SECURITY_GROUP_ID"]

    response = ecs_client.run_task(
        cluster=cluster,
        taskDefinition=task_def,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnet_ids,
                "securityGroups": [security_group_id],
                "assignPublicIp": "DISABLED",
            }
        },
    )

    task_arn = response["tasks"][0]["taskArn"]
    print(f"Started task: {task_arn}")

    return {"statusCode": 200, "body": json.dumps({"taskArn": task_arn})}
import json
import logging
import boto3
import requests
import time
import os

# Configuring Environment variable 
api_endpoint_url = os.environ['api_endpoint_url']
snow_secret_full_arn = os.environ['snow_secret_arn']

# Configure the logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_last_execution_status(pipeline_name):
    # Create a CodePipeline client
    codepipeline_client = boto3.client('codepipeline')

    try:
        # Get the list of executions for the specified pipeline
        response = codepipeline_client.list_pipeline_executions(
            pipelineName=pipeline_name,
            maxResults=1  # Limit to one result to get the most recent execution
        )
        
        # Extract the status of the last execution
        if 'pipelineExecutionSummaries' in response and response['pipelineExecutionSummaries']:
            last_execution_status = response['pipelineExecutionSummaries'][0]['status']
            time.sleep(60)
            time_counter = 0
            while not last_execution_status in ["Failed","Succeeded"]:
                time_counter = time_counter + 1
                if(time_counter == 12):
                    print("The customization pipeline {} is still in {} state and taking longer than expected, please look into it".format(pipeline_name,last_execution_status))
                    break
                else:
                    response = codepipeline_client.list_pipeline_executions(pipelineName=pipeline_name,maxResults=1)  # Limit to one result to get the most recent execution
                    last_execution_status = response['pipelineExecutionSummaries'][0]['status']
                    print("The customization pipeline {} is  in {} state".format(pipeline_name,last_execution_status))
                    time.sleep(60)
                
                
            return last_execution_status
        else:
            print("Issue in finding the customization pipeline {}".format(pipeline_name))
            return None

    except Exception as e:
        print(f"Error: {e}")
        return None

def api_call(build_status_code,snow_taskid,account_details):
    # Replace 'YOUR_API_ENDPOINT' with the actual API endpoint URL
    api_endpoint = api_endpoint_url

    secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
    get_secret = secrets_client.get_secret_value(SecretId=snow_secret_full_arn)
    snow_secret_data = json.loads(get_secret['SecretString'])
    username = snow_secret_data['username']
    password = snow_secret_data['password']
    logger.info(f"the snow username is {username}")
    logger.info(f"the snow password is {password}")
    snow_auth = (username,password)

    # Replace 'YOUR_PAYLOAD' with the JSON data you want to send in the POST request
    payload = {
        "status": "Failed",
        "accountdetails":{},
        "SNOWTicketID":"TASK000000084161",
    }
    
    payload["SNOWTicketID"] = snow_taskid
    payload["status"] = build_status_code

    try:
        if(build_status_code == "910"):
            payload["status"] = "Success"
            payload["accountdetails"] = {
                "account_name" : account_details["name"],
                "account_id" : account_details["id"]
            }
        else:
            logger.info("Closing the snow ticket {} as the account vending failed".format(snow_taskid))
        # Make a POST request to the API with JSON payload
        payload_data = json.dumps(payload)
        logger.info(payload_data)
        response = requests.post(api_endpoint, data=payload_data,headers={"Content-Type":"application/json"}, auth=snow_auth)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            return {
                'statusCode': 200,
                'body': response.json()
            }
        else:
            return {
                'statusCode': response.status_code,
                'body': response.json()
                
            }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': str(e)
        }


def lambda_handler(event, context):
    logger.info(f"The event from SNS topic {event}")
    logger.info(f"The context from SNS topic {context}")
    account_response_output = event["Records"][0]['Sns']['Message']
    account_response_output = account_response_output.replace("'", '"')
    account_response_output_json = json.loads(account_response_output)
    account_vending_status = account_response_output_json['account_info']['account']['status']
    customization_pipeline_status = "FAILED"
    pipeline_name = account_response_output_json["account_info"]["account"]["id"] + "-customizations-pipeline"
    snow_taskid = account_response_output_json["account_request"]["account_tags"]["SNOWTaskID"]
    customization_pipeline_status = get_last_execution_status(pipeline_name)
    account_details = account_response_output_json["account_info"]["account"]
    if(account_vending_status.upper() == "ACTIVE" and customization_pipeline_status.upper() == "SUCCEEDED" ):
        logger.info("Build is successfull")
        api_call_status = api_call(build_status_code="910",snow_taskid=snow_taskid,account_details=account_details)
    else:
        logger.error("Build failed")
        api_call_status = api_call(build_status_code="930",snow_taskid=snow_taskid,account_details=account_details) 
       
    logger.info(f"After the API call the output is {api_call_status}")

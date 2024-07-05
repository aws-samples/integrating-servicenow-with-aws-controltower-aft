"""
###  ###
"""

import json

def generate_account_tag(snow_payload_data):
    account_tags = {
        "Environment" : snow_payload_data["environment"],
        "SNOWTaskID" : snow_payload_data["SNOWTicketID"]
    }
    return account_tags

def generate_tfvars_payload(snow_payload_data,config_map_data,tfvars_payload_data):
    print("generate tfvars payload in progress")
    accountname = snow_payload_data["accountName"]
    account_tags = generate_account_tag(snow_payload_data)
    accountemail = snow_payload_data["accountEmail"]
    if not snow_payload_data["SSOUserFirstName"]:
        SSOUserFirstName = snow_payload_data["change_requested_by"]
    else:
        SSOUserFirstName =  snow_payload_data["SSOUserFirstName"]
    if not snow_payload_data["SSOUserLastName"]:
        SSOUserLastName = snow_payload_data["change_requested_by"]
    else:
        SSOUserLastName =  snow_payload_data["SSOUserLastName"]
    SSOUserEmail = snow_payload_data["accountEmail"]
    account_customizations_name = config_map_data["businessunit_to_requestype"][snow_payload_data["businessUnit"]]["account_customizations_name"]
    workload_type = config_map_data["businessunit_to_requestype"][snow_payload_data["businessUnit"]]["request_type"] + "-" + snow_payload_data["cloudAccountType"]
    ManagedOrganizationalUnit = config_map_data["businessunit_to_requestype"][snow_payload_data["businessUnit"]]["managed_org_unit"][snow_payload_data["cloudAccountType"]]
    snow_taskid = snow_payload_data["SNOWTicketID"]
    change_management_parameters = {
        "change_requested_by" : snow_payload_data["change_requested_by"],
        "change_reason" : snow_payload_data["change_reason"]
        }
    refined_tfvars_payload_data = tfvars_payload_data
    refined_tfvars_payload_data["AccountName"] = accountname
    refined_tfvars_payload_data["AccountEmail"] = accountemail
    refined_tfvars_payload_data["snow_taskid"] = snow_taskid
    refined_tfvars_payload_data["account_tags"] = account_tags
    refined_tfvars_payload_data["SSOUserEmail"] = SSOUserEmail
    refined_tfvars_payload_data["SSOUserFirstName"] = SSOUserFirstName
    refined_tfvars_payload_data["SSOUserLastName"] = SSOUserLastName
    refined_tfvars_payload_data["account_customizations_name"] = account_customizations_name
    refined_tfvars_payload_data["SSOUserLastName"] = SSOUserLastName
    refined_tfvars_payload_data["workload_type"] = workload_type
    refined_tfvars_payload_data["ManagedOrganizationalUnit"] = ManagedOrganizationalUnit
    refined_tfvars_payload_data["change_management_parameters"] = change_management_parameters
    print(refined_tfvars_payload_data)
    finalized_tfvars_payload_data = json.dumps(refined_tfvars_payload_data, indent=4)
    with open('terraform_payload.json', 'w') as tfvars_json_file: 
        tfvars_json_file.write(finalized_tfvars_payload_data)

# Open and read the JSON file
config_map_file_path = "config_map.json"
snow_payload_file_path = "snow_input.json"
tfvars_payload_template_path = "tfvars_payload_template.json"

with open(snow_payload_file_path, "r") as snow_payload_file:
    snow_payload_data = json.load(snow_payload_file)
with open(config_map_file_path , "r") as config_map_file:
    config_map_data = json.load(config_map_file)
with open(tfvars_payload_template_path , "r") as tfvars_payload_template_file:
    tfvars_payload_data = json.load(tfvars_payload_template_file)

generate_tfvars_payload(snow_payload_data,config_map_data,tfvars_payload_data)

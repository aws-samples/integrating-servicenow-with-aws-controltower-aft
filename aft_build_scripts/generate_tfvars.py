"""
###  ###
"""

import json
from jinja2 import Template 
import re
from pathlib import Path
import time

def generate_tfvars(existing_tfvars,new_tfvars,workload_type):
    print("###New tfvars generation is in progress...###")
    for key in new_tfvars[workload_type]:
        if(key in existing_tfvars[workload_type]):
            print("###The requested account already exists and it is updated with payload data###")
            existing_tfvars[workload_type][key] = new_tfvars[workload_type][key]
        else:
            print("###The requested account is a new account, generating the new updated tfvars###")
            existing_tfvars[workload_type][key] = new_tfvars[workload_type][key]
    print(existing_tfvars)
    return(existing_tfvars)


def generate_tfvars_json_file(new_generated_tfvars_dict):
    print("### Updating the json tfvars file with the new changes for terraform apply ###")
    new_generated_tfvars_json = json.dumps(new_generated_tfvars_dict, indent=4)
    print(new_generated_tfvars_json)
    with open(workload_type+'.auto.tfvars.json', 'w') as tfvars_json_file: 
        tfvars_json_file.write(new_generated_tfvars_json)


# Open and read the JSON file
file_path = "terraform_payload.json"

with open(file_path, "r") as json_file:
    data = json.load(json_file)
    workload_type = data["workload_type"]

path = Path(workload_type+'-requests.tf')
if not path.exists():
    with open('terraform_template.jinja2') as tf_template_file:
        tf_template = Template(tf_template_file.read())
        terraform_file_rendered = tf_template.render(workload_type=workload_type)
        with open(workload_type+'-requests.tf', "w") as tf_file:
            tf_file.write(terraform_file_rendered)

path = Path(workload_type+'.auto.tfvars.json')
if not path.exists(): 
    with open('tfvars_template.json.jinja2') as tfvars_template_file:
        tfvars_template = Template(tfvars_template_file.read())
        tfvars_file_rendered = tfvars_template.render(workload_type=workload_type)
    with open(workload_type+'.auto.tfvars.json', "w") as tfvars_file:
        tfvars_file.write(tfvars_file_rendered)
    time.sleep(5)

with open(workload_type+'.auto.tfvars.json', "r") as json_tfvars_file:
    existing_tfvars_map = json.load(json_tfvars_file)  
with open('workload.auto.tfvars.json.jinja2') as file_:
    template = Template(file_.read())
    print(template.render(account=data, workload_type=workload_type))
    find_errors = re.findall("ERROR:.*",template.render(account=data,workload_type=workload_type))
    if find_errors:
        print("###Below errors found in the generated tfvars###")
        for value in find_errors:
            print(value)
        exit()
    else:
        print("###Successfully generated the tfvar entry for the payload###")
        new_tfvars_map = json.loads(template.render(account=data,workload_type=workload_type))
    new_generated_tfvars = generate_tfvars(existing_tfvars_map,new_tfvars_map,workload_type)


generate_tfvars_json_file(new_generated_tfvars)


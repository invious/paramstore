#!/usr/bin/env python3
import json
import boto3
import argparse
import re
import stringcase
import os
import stat

parser = argparse.ArgumentParser()

parser.add_argument("--app", "-a", type=str, required=True)
parser.add_argument("--profiles", "-p", type=str, required=True)
args = parser.parse_args()

app_name = args.app
profiles = args.profiles.split(',')

with open('template.yaml') as f:
    text = f.read()

regex = re.compile(r"([A-Z_]+): ['\"]*([^!].+?)['\"]*$", re.MULTILINE)
pairs = regex.findall(text)

pairs_json = list(map(lambda x: {"name": x[0].lower(), "value": x[1]}, pairs ))

new_params = ''.join(list(map(lambda x:f"""
  {stringcase.pascalcase(x[0].lower())}:
    Type : 'AWS::SSM::Parameter::Value<String>'
    NoEcho: true""", pairs)))

for name, value in pairs:
  name = stringcase.pascalcase(name.lower())
  text = re.sub(r"([A-Z_]+): (['\"]*[^!].+?['\"]*$)", f"\g<1>: !Ref {name}", text, 1, re.MULTILINE)

old_params = re.findall(r"Parameters:\n(.+?.+?\n\n)", text, re.DOTALL)[0]
text = re.sub(r"Parameters:\n(.+?.+?\n\n)", f"Parameters:\n{''.join([old_params[:-2], new_params])}\n\n", text, 1, re.DOTALL)

with open('template.yaml', 'w') as f:
    f.write(text)

print('template.yaml updated.')

regex = r"--parameter-overrides (.+?\\.+?)--"

with open('deploy.sh') as f:
    deploy_text = f.read()

matches = re.finditer(regex, deploy_text, re.DOTALL)

for matchNum, match in enumerate(matches):
    old_d_params = match.group(1).strip()

newParams = []
for obj in pairs_json:
    pcase_name = stringcase.pascalcase(obj['name'])
    name = obj['name']
    new = f"{pcase_name}=/$aws_profile/{app_name}/{name} \\\n                          "
    newParams.append(new)

newParams[-1] = newParams[-1].rstrip() + '\n    '

out = ''.join(newParams)
combined_params = old_d_params + '\n                          ' + out

result = re.sub(regex, f"--parameter-overrides {combined_params}--", deploy_text, 1, re.DOTALL)

with open('deploy.sh', 'w') as f:
    f.write(result)

st = os.stat('deploy.sh')
os.chmod('deploy.sh', st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


print('deploy.sh updated.')


for obj in pairs_json:
    name = obj['name']
    value = obj['value']
    for env in profiles:
        client = boto3.Session(profile_name=env).client('ssm')
        path = f"/{env}/{app_name}/{name}"
        client.put_parameter(
            Name=path,
            Value=value,
            Type='String',
            Overwrite=True
        )
        print(f"{path}:{value}")

print('parameters added to parameter store.')

print("Please take a look over your template.yaml and deploy.sh to delete duplicates")

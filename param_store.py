#!/usr/bin/env python3
import argparse
import os
import re
import stat
from typing import List, Tuple

import boto3
import math
import stringcase

INCLUDED = "(" + ")|(".join([
    "settings.py",
    "template.yaml"
]) + ")"
BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
HEX_CHARS = "1234567890abcdefABCDEF"


def shannon_entropy(data, iterator):
    """
    Borrowed from http://blog.dkbza.org/2007/05/scanning-data-for-entropy-anomalies.html
    """
    if not data:
        return 0
    entropy = 0
    for x in iterator:
        p_x = float(data.count(x))/len(data)
        if p_x > 0:
            entropy += - p_x*math.log(p_x, 2)
    return entropy


def get_strings_of_set(word, char_set, threshold=20):
    count = 0
    letters = ""
    strings = []
    for char in word:
        if char in char_set:
            letters += char
            count += 1
        else:
            if count > threshold:
                strings.append(letters)
            letters = ""
            count = 0
    if count > threshold:
        strings.append(letters)
    return strings


def find_aws_key_pairs(pairs: List[Tuple[str,str]]) -> List[Tuple[str,str]]:
    keys_found = []
    for key, value in pairs:
        base64_strings = get_strings_of_set(value, BASE64_CHARS)
        hex_strings = get_strings_of_set(value, HEX_CHARS)
        for string in base64_strings:
            b64_entropy = shannon_entropy(string, BASE64_CHARS)
            if b64_entropy > 4.5:
                keys_found.append( (key, value) )
        for string in hex_strings:
            hex_entropy = shannon_entropy(string, HEX_CHARS)
            if hex_entropy > 3:
                keys_found.append((key, value))
    keys_found = list(set(keys_found))
    if len(set([x[0] for x in keys_found])) != len(keys_found):
        raise EnvironmentError("multiple AWS keys with the same name found. Please make sure each keyname is unique.")
    return keys_found


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

pairs = find_aws_key_pairs(pairs)

pairs_json = list(map(lambda x: {"name": x[0].lower(), "value": x[1]}, pairs ))

new_params = ''.join(list(map(lambda x:f"""
  {stringcase.pascalcase(x[0].lower())}:
    Type : 'AWS::SSM::Parameter::Value<String>'
    NoEcho: true""", pairs)))

for name, value in pairs:
  pascal_name = stringcase.pascalcase(name.lower())
  text = re.sub(f"{name}: (['\"]*[^!].+?['\"]*$)", f"{name}: !Ref {pascal_name}", text, 0, re.MULTILINE)

old_params = re.findall(r"Parameters:\n(.+?.+?\n\n)", text, re.DOTALL)[0]
text = re.sub(r"Parameters:\n(.+?.+?\n\n)", f"Parameters:\n{''.join([old_params[:-2], new_params])}\n\n", text, 1, re.DOTALL)

# with open('template.yaml', 'w') as f:
#     f.write(text)

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

# with open('deploy.sh', 'w') as f:
#     f.write(result)

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

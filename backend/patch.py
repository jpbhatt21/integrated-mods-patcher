from ini_parser import parse_ini_by_hash, print_parsed_ini
import json
import db
data=""
path=""
file="temp_A.ini"
with open(file, 'r', encoding='utf-8') as f:
    data = f.read()
ini_data = parse_ini_by_hash(data)
print_parsed_ini(ini_data)
bearer ="9YD7jd8LjCg-CdDPwKu3gCogalyI1tV5vdTkkFH1"

updated_data={}

def patch_hash(hash,prev=[]):
    if hash in prev:
        return hash
    res = db.get('RECORDS', bearer=bearer, table="WWH", record=hash)
    if res.status_code == 200:
        hash_record = res.json()
        fields = hash_record.get('fields', {})
        next=json.loads(fields.get('Next', '{}'))
        if len(next)==0:
            return hash
        del next['ver']
        next = [k for k in list({k: v for k, v in sorted(next.items(), key=lambda item: item[1]['count'], reverse=True)}.keys())]
        hash = patch_hash(next[0],prev+[hash])


        pass
    return hash


for key,value in ini_data.items():
    updated_data[value]=patch_hash(value)
    data=data.replace(value, updated_data[value])

print_parsed_ini(updated_data)

with open('imm_updated_mod.ini', 'w', encoding='utf-8') as f:
    f.write(data)






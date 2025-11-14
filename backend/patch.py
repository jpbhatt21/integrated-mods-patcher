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
bearer = "" #Your bearer token here

updated_data={}

def patch_hash(hash,prev=[]):
    if hash in prev:
        return hash
    res = db.get('RECORDS', bearer=bearer, table="WWH", record=hash)
    if res.status_code == 200:
        hash_record = res.json()
        fields = hash_record.get('fields', {})
        next=json.loads(fields.get('Data', '{}'))
        next_keys = list(next.keys())
        next_keys.sort(key=lambda x: float(x))    
        max_ver = next_keys[-1]
        next_keys.pop()
        del next[ str(max_ver)]["mod"]
        while (len(next[max_ver])==0):
            if(len(next_keys)==0):
                return hash
            max_ver = next_keys[-1]
            next_keys.pop()
            del next[ str(max_ver)]["mod"]

        max_max_ver = str(max([ float(k) for k in next[max_ver].keys()]))
        max_hash = hash
        max_count=0
        for hash,val in next[max_ver][max_max_ver].items():
            if(val>max_count):
                max_count=val
                max_hash=hash
        hash = patch_hash(max_hash,prev+[hash])
        pass
    return hash


for key,value in ini_data.items():
    updated_data[value]=patch_hash(value)
    data=data.replace(value, updated_data[value])

print_parsed_ini(updated_data)

with open('imm_updated_mod.ini', 'w', encoding='utf-8') as f:
    f.write(data)






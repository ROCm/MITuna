import json

def load(path):
  f = open(path)
  return json.load(f)

def save(json_data, path):
  with open(path, 'w') as f:
    json.dump(json_data, f, indent=4, ensure_ascii=False)

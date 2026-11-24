import json
import os
import sys
from jsonschema import Draft7Validator, validators, ValidationError

SCHEMA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "schema.json")
)

def extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(property, subschema["default"])
        for error in validate_properties(validator, properties, instance, schema):
            yield error

    return validators.extend(validator_class, {"properties": set_defaults})

DefaultValidatingDraft7Validator = extend_with_default(Draft7Validator)

def load_schema(schema_filepath=SCHEMA_PATH):
    with open(schema_filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def validate_sign_entry(sign_data, schema=None):
    if schema is None:
        schema = load_schema()
    
    data_to_validate = sign_data.copy()
    
    data_to_validate.pop("_source_file", None)
    
    try:
        validator = DefaultValidatingDraft7Validator(schema)
        validator.validate(data_to_validate)
        return True, None
    except ValidationError as e:
        path = " -> ".join([str(x) for x in e.absolute_path])
        err_msg = f"Validation Error at `{path}`: {e.message}"
        return False, err_msg

def validate_json_file(json_filepath, schema_filepath=SCHEMA_PATH):
    try:
        schema = load_schema(schema_filepath)
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        all_valid = True
        
        if isinstance(data, list):
            print(f"🔍 Auditing {len(data)} signs in {os.path.basename(json_filepath)}...")
            for idx, sign in enumerate(data):
                
                is_valid, err = validate_sign_entry(sign, schema)
                if not is_valid:
                    sign_id = sign.get('sign_id', f'Index {idx}')
                    print(f"❌ Error in [{sign_id}]: {err}")
                    all_valid = False
        else:
            is_valid, err = validate_sign_entry(data, schema)
            if not is_valid:
                print(f"❌ Error in {json_filepath}: {err}")
                all_valid = False
                
        if all_valid:
            print(f"✅ Success: {json_filepath} is perfectly valid and complies with the strict architecture.")
        else:
            print("⚠️ Errors found. Check the log above.")
            
        return all_valid
    
    except Exception as e:
        print(f"❌ Exception validating file: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_dataset.py <path_to_output.json>")
    else:
        target_file = sys.argv[1]
        validate_json_file(target_file)

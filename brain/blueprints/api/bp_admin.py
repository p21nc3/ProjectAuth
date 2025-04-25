import csv
import os
import json
import time
from uuid import uuid4
from apiflask import APIBlueprint
from apiflask.fields import Integer, String, File
from apiflask.validators import OneOf
from flask import current_app, request
from modules.auth import admin_auth
from modules.validate import JsonString
from jsonschema import validate, ValidationError


bp_admin = APIBlueprint("admin", __name__, url_prefix="/admin")


@bp_admin.get("/top_sites_lists")
def get_top_sites_lists():
    db = current_app.config["db"]
    result = db["top_sites_lists"].distinct("id")
    return {"success": True, "error": None, "data": result}


@bp_admin.put("/top_sites_lists")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({
    "list_id": String(required=True),
    "list_rank_index": Integer(required=True),
    "list_domain_index": Integer(required=True)
}, location="query")
@bp_admin.input({
    "list_file": File(required=True)
}, location="files", schema_name="TopSitesListFile")
def add_top_sites_list(query_data, files_data):
    db = current_app.config["db"]
    list_id = query_data["list_id"]
    list_rank_index = query_data["list_rank_index"]
    list_domain_index = query_data["list_domain_index"]
    list_file = files_data["list_file"]

    tmp_filepath = f"/tmp/{uuid4()}.csv"
    list_file.save(tmp_filepath)

    list_entries = []
    with open(tmp_filepath, "r") as f:
        reader = csv.reader(f)
        for line in reader:
            try:
                list_entries.append({
                    "id": list_id,
                    "rank": int(line[list_rank_index]),
                    "domain": line[list_domain_index]
                })
            except IndexError as e:
                return {"success": False, "error": f"Invalid top sites list file: {e}", "data": None}

    db["top_sites_lists"].delete_many({"id": list_id})
    db["top_sites_lists"].insert_many(list_entries)

    os.remove(tmp_filepath)

    return {"success": True, "error": None, "data": None}


@bp_admin.delete("/top_sites_lists")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({"list_id": String(required=True)}, location="query")
def delete_top_sites_list(query_data):
    db = current_app.config["db"]
    list_id = query_data["list_id"]
    db["top_sites_lists"].delete_many({"id": list_id})
    return {"success": True, "error": None, "data": None}


@bp_admin.post("/db_index")
@bp_admin.auth_required(admin_auth)
def create_database_index():
    db = current_app.config["db"]

    db["top_sites_lists"].create_index([("id", 1)])
    db["top_sites_lists"].create_index([("id", 1), ("domain", 1)])

    db["ground_truth"].create_index([("gt_id", 1)])

    db["landscape_analysis_tres"].create_index([("domain", 1)])
    db["landscape_analysis_tres"].create_index([("domain", 1), ("task_config.task_timestamp_response_received", 1)])
    db["landscape_analysis_tres"].create_index([("task_config.task_id", 1)])
    db["landscape_analysis_tres"].create_index([("task_config.task_state", 1)])
    db["landscape_analysis_tres"].create_index([("task_config.task_timestamp_response_received", -1)])
    db["landscape_analysis_tres"].create_index([("landscape_analysis_result.resolved.reachable", 1)])
    db["landscape_analysis_tres"].create_index([("landscape_analysis_result.recognized_idps", 1)])

    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("domain", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("task_config.task_state", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("landscape_analysis_result.resolved.reachable", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("landscape_analysis_result.resolved.error", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("landscape_analysis_result.recognized_idps.idp_name", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("landscape_analysis_result.error", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("landscape_analysis_result.recognized_navcreds", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("domain", 1), ("task_config.task_timestamp_response_received", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("landscape_analysis_result.resolved.reachable", 1), ("landscape_analysis_result.recognized_idps.idp_name", 1)])

    db["landscape_analysis_tres"].create_index([("landscape_analysis_result.recognized_idps.idp_name", 1)])
    db["landscape_analysis_tres"].create_index([
        ("domain", 1),
        ("landscape_analysis_result.recognized_idps.idp_name", 1),
        ("landscape_analysis_result.recognized_idps.idp_integration", 1),
        ("landscape_analysis_result.recognized_idps.login_page_url", 1)
    ])

    return {"success": True, "error": None, "data": None}


@bp_admin.post("/db_query")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({
    "method": String(required=True, validate=OneOf(["find_all", "find_one", "count", "update_many"])),
    "collection": String(required=True),
    "query": String(required=True, validate=JsonString),
    "projection": String(required=True, validate=JsonString)
}, location="json", schema_name="DatabaseQuery")
def issue_database_query(json_data):
    db = current_app.config["db"]
    method = json_data["method"]
    collection = json_data["collection"]
    query = json.loads(json_data["query"])
    projection = json.loads(json_data["projection"])

    result = None
    if method == "find_all":
        result = list(db[collection].find(query, {"_id": False, **projection}))
    elif method == "find_one":
        result = db[collection].find_one(query, {"_id": False, **projection})
    elif method == "count":
        result = db[collection].count_documents(query)
    elif method == "update_many":
        result = db[collection].update_many(query, projection).modified_count

    return {"success": True, "error": None, "data": result}


@bp_admin.get("/query")
def get_stored_database_queries():
    db = current_app.config["db"]
    result = list(db["queries"].find({}, {"_id": False}))
    return {"success": True, "error": None, "data": result}


@bp_admin.put("/query")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({
    "description": String(required=True),
    "query": String(required=True, validate=JsonString)
}, location="query")
def add_stored_database_query(query_data):
    db = current_app.config["db"]
    description = query_data["description"]
    query = json.loads(query_data["query"])
    db["queries"].insert_one({"description": description, "query": json.dumps(query)})
    return {"success": True, "error": None, "data": None}


@bp_admin.delete("/query")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({
    "query": String(required=True)
}, location="query")
def delete_stored_database_query(query_data):
    db = current_app.config["db"]
    query = query_data["query"]
    db["queries"].delete_many({"query": query})
    return {"success": True, "error": None, "data": None}


@bp_admin.post("/ground_truth/duplicate")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({
    "source_gt_id": String(required=True),
    "target_gt_id": String(required=True)
}, location="query")
def duplicate_ground_truth(query_data):
    db = current_app.config["db"]
    source_gt_id = query_data["source_gt_id"]
    target_gt_id = query_data["target_gt_id"]

    for c in db["ground_truth"].find({"gt_id": source_gt_id}, {"_id": False}):
        c["gt_id"] = target_gt_id
        c["timestamp"] = int(time.time())
        db["ground_truth"].insert_one(c)

    return {"success": True, "error": None, "data": None}


@bp_admin.delete("/ground_truth")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({
    "gt_id": String(required=True)
}, location="query")
def delete_ground_truth(query_data):
    db = current_app.config["db"]
    gt_id = query_data["gt_id"]
    db["ground_truth"].delete_many({"gt_id": gt_id})
    return {"success": True, "error": None, "data": None}


@bp_admin.get("/auth_stats")
def get_auth_stats():
    """Get authentication statistics for the admin dashboard"""
    db = current_app.config["db"]
    
    try:
        # Get counts for each authentication type
        passkey_count = db["landscape_analysis_tres"].count_documents({
            "landscape_analysis_result.recognized_idps.idp_name": "PASSKEY BUTTON"
        })
        
        mfa_count = db["landscape_analysis_tres"].count_documents({
            "landscape_analysis_result.recognized_idps.idp_name": "MFA_GENERIC"
        })
        
        password_count = db["landscape_analysis_tres"].count_documents({
            "landscape_analysis_result.recognized_idps.idp_name": "PASSWORD_BASED"
        })
        
        webauthn_api_count = db["landscape_analysis_tres"].count_documents({
            "landscape_analysis_result.recognized_navcreds": {"$exists": True, "$ne": []}
        })
        
        lastpass_count = db["landscape_analysis_tres"].count_documents({
            "landscape_analysis_result.recognized_lastpass_icon": {"$exists": True, "$ne": []}
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching authentication stats: {e}")
        return {
            "success": False,
            "error": f"Error fetching stats: {str(e)}",
            "data": None
        }
    
    return {
        "success": True, 
        "error": None, 
        "data": {
            "passkey_count": passkey_count,
            "mfa_count": mfa_count,
            "password_count": password_count,
            "webauthn_api_count": webauthn_api_count,
            "lastpass_count": lastpass_count
        }
    }


@bp_admin.route('/api/idp_rules', methods=['GET','PUT'])
@bp_admin.auth_required(admin_auth)
def manage_idp_rules():
    """
    GET: Return idp_rules.json from worker/config
    PUT: Validate against JSON schema and update idp_rules.json
    """
    try:
        worker_config_path = os.path.join(current_app.config.get("WORKER_PATH", ""), "config")
        if not os.path.exists(worker_config_path):
            return {"success": False, "error": f"Worker config path not found: {worker_config_path}", "data": None}
            
        idp_rules_path = os.path.join(worker_config_path, "idp_rules.py")
        if not os.path.exists(idp_rules_path):
            return {"success": False, "error": f"IDP rules file not found: {idp_rules_path}", "data": None}
        
        if request.method == 'GET':
            try:
                # Read the content of idp_rules.py
                with open(idp_rules_path, 'r') as f:
                    content = f.read()
                    
                # Extract the IdpRules dictionary from the Python file
                # This is a simple parser and might need to be improved
                rules_dict_str = content.split('IdpRules = ')[1].strip()
                
                # Convert Python dictionary syntax to valid JSON
                rules_json = json.dumps(eval(rules_dict_str))
                
                return {"success": True, "error": None, "data": json.loads(rules_json)}
                
            except Exception as e:
                current_app.logger.error(f"Error reading IDP rules: {e}")
                return {"success": False, "error": f"Error reading IDP rules: {str(e)}", "data": None}
        
        elif request.method == 'PUT':
            try:
                # Read and validate the JSON against a schema
                rules_data = request.json
                
                # Here you'd validate against a schema
                # validate(instance=rules_data, schema=idp_rules_schema)
                
                # Convert JSON to Python dictionary string
                rules_dict_str = json.dumps(rules_data, indent=4)
                
                # Write back to idp_rules.py
                with open(idp_rules_path, 'w') as f:
                    f.write(f"IdpRules = {rules_dict_str}")
                
                return {"success": True, "error": None, "data": None}
                
            except ValidationError as e:
                current_app.logger.error(f"Schema validation error: {e}")
                return {"success": False, "error": f"Schema validation error: {str(e)}", "data": None}
            except Exception as e:
                current_app.logger.error(f"Error updating IDP rules: {e}")
                return {"success": False, "error": f"Error updating IDP rules: {str(e)}", "data": None}
    except Exception as e:
        current_app.logger.error(f"Error in manage_idp_rules: {e}")
        return {"success": False, "error": f"General error: {str(e)}", "data": None}

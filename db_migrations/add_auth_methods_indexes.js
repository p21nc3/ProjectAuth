// MongoDB migration script to add indexes for new authentication methods
// Run with: docker exec -it sso-monitor-db-1 mongosh -u root -p example /scripts/add_auth_methods_indexes.js

// Connect to the database
db = db.getSiblingDB("sso-monitor");

print("Adding indexes for new authentication methods...");

// Add indexes for auth_methods
db.landscape_analysis_tres.createIndex({ "landscape_analysis_result.auth_methods.password.detected": 1 }, { background: true });
db.landscape_analysis_tres.createIndex({ "landscape_analysis_result.auth_methods.passkey.detected": 1 }, { background: true });
db.landscape_analysis_tres.createIndex({ "landscape_analysis_result.auth_methods.totp.detected": 1 }, { background: true });
db.landscape_analysis_tres.createIndex({ "landscape_analysis_result.auth_methods.sms.detected": 1 }, { background: true });
db.landscape_analysis_tres.createIndex({ "landscape_analysis_result.auth_methods.email.detected": 1 }, { background: true });
db.landscape_analysis_tres.createIndex({ "landscape_analysis_result.auth_methods.app.detected": 1 }, { background: true });

// Add indexes for metadata_available
db.landscape_analysis_tres.createIndex({ "landscape_analysis_result.metadata_available.webauthn_api": 1 }, { background: true });
db.landscape_analysis_tres.createIndex({ "landscape_analysis_result.metadata_available.lastpass": 1 }, { background: true });
db.landscape_analysis_tres.createIndex({ "landscape_analysis_result.metadata_available.idps": 1 }, { background: true });

// Add indexes for recognized_navcreds
db.landscape_analysis_tres.createIndex({ "landscape_analysis_result.recognized_navcreds": 1 }, { background: true });

// Add indexes for new IDPs - use a simple field filter
db.landscape_analysis_tres.createIndex({ "landscape_analysis_result.recognized_idps.idp_name": 1 }, { background: true });

print("Done adding indexes for new authentication methods");

// Print stats
print("Added indexes for new authentication methods");
print("Indexes in landscape_analysis_tres:");
db.landscape_analysis_tres.getIndexes().forEach(function(index) { printjson(index); });
print("Indexes in login_trace_analysis_tres:");
db.login_trace_analysis_tres.getIndexes().forEach(function(index) { printjson(index); }); 
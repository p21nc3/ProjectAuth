// MongoDB migration script to add indexes for new authentication methods
// Run with: docker exec -it sso-monitor-db-1 mongosh -u root -p example /scripts/add_auth_methods_indexes.js

// Connect to the database
db = db.getSiblingDB("sso-monitor");

// Add indexes for recognized_idps
db.landscape_analysis_tres.createIndex({ "recognized_idps.idp_name": 1 }, { background: true });
db.login_trace_analysis_tres.createIndex({ "recognized_idps.idp_name": 1 }, { background: true });

// Add indexes for auth_methods
db.landscape_analysis_tres.createIndex({ "auth_methods.password.detected": 1 }, { background: true });
db.landscape_analysis_tres.createIndex({ "auth_methods.passkey.detected": 1 }, { background: true });
db.landscape_analysis_tres.createIndex({ "auth_methods.totp.detected": 1 }, { background: true });
db.landscape_analysis_tres.createIndex({ "auth_methods.sms.detected": 1 }, { background: true });
db.landscape_analysis_tres.createIndex({ "auth_methods.email.detected": 1 }, { background: true });
db.landscape_analysis_tres.createIndex({ "auth_methods.app.detected": 1 }, { background: true });

db.login_trace_analysis_tres.createIndex({ "auth_methods.password.detected": 1 }, { background: true });
db.login_trace_analysis_tres.createIndex({ "auth_methods.passkey.detected": 1 }, { background: true });
db.login_trace_analysis_tres.createIndex({ "auth_methods.totp.detected": 1 }, { background: true });
db.login_trace_analysis_tres.createIndex({ "auth_methods.sms.detected": 1 }, { background: true });
db.login_trace_analysis_tres.createIndex({ "auth_methods.email.detected": 1 }, { background: true });
db.login_trace_analysis_tres.createIndex({ "auth_methods.app.detected": 1 }, { background: true });

// Print completion message
print("Added indexes for new authentication methods");
print("Indexes in landscape_analysis_tres:");
db.landscape_analysis_tres.getIndexes().forEach(printjson);
print("Indexes in login_trace_analysis_tres:");
db.login_trace_analysis_tres.getIndexes().forEach(printjson); 
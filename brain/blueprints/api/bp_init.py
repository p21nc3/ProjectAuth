# Database initialization script to create necessary indexes
import logging

logger = logging.getLogger(__name__)

def initialize_database(db):
    """
    Initialize the database with required indexes.
    This is called when the application starts.
    """
    try:
        # Create indexes for landscape analysis
        logger.info("Creating indexes for landscape analysis...")
        db.landscape_analysis.create_index("scan_id")
        db.landscape_analysis.create_index("timestamp")
        db.landscape_analysis.create_index("domain")
        db.landscape_analysis.create_index("landscape_analysis_result.recognized_idps.idp_name")
        
        # Create indexes for the new authentication fields
        logger.info("Creating indexes for authentication detection...")
        db.landscape_analysis.create_index("landscape_analysis_result.metadata_available.passkey")
        db.landscape_analysis.create_index("landscape_analysis_result.metadata_available.mfa_generic")
        db.landscape_analysis.create_index("landscape_analysis_result.metadata_available.password_based")
        db.landscape_analysis.create_index("landscape_analysis_result.metadata_available.webauthn_api")
        db.landscape_analysis.create_index("landscape_analysis_result.metadata_available.lastpass")
        
        logger.info("Database initialization completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False 
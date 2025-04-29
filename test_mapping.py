"""
Script de test pour vérifier le mapping des colonnes Airtable et leur statut de synchronisation
Exécutez ce script avant la synchronisation pour s'assurer que le mapping est correct
"""
import logging
import sys
from pyairtable import Table
from config import (
    AIRTABLE_API_KEY,
    AIRTABLE_BASE_ID,
    AIRTABLE_TABLE_NAME,
    AIRTABLE_INVOICE_FILE_COLUMNS,
    AIRTABLE_SYNC_STATUS_COLUMNS
)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("test_mapping")

def test_column_mapping():
    """Vérifie que les colonnes définies dans le mapping existent dans Airtable"""
    logger.info("====================================================")
    logger.info("Test du mapping des colonnes Airtable")
    logger.info("====================================================")
    
    # Vérifier la configuration
    logger.info(f"API Key définie: {'Oui' if AIRTABLE_API_KEY else 'Non'}")
    logger.info(f"Base ID défini: {'Oui' if AIRTABLE_BASE_ID else 'Non'}")
    logger.info(f"Table Name défini: {'Oui' if AIRTABLE_TABLE_NAME else 'Non'}")
    
    if not (AIRTABLE_API_KEY and AIRTABLE_BASE_ID and AIRTABLE_TABLE_NAME):
        logger.error("Configuration incomplète. Vérifiez vos variables d'environnement.")
        return False
    
    try:
        # Connexion à Airtable
        table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
        
        # Récupérer un enregistrement pour vérifier la structure
        record = table.first()
        if not record:
            logger.warning("Table vide ou inaccessible. Impossible de vérifier les colonnes.")
            return False
        
        # Récupérer les noms de colonnes réels
        fields = record.get('fields', {})
        column_names = set(fields.keys())
        
        logger.info(f"Colonnes trouvées dans Airtable: {', '.join(sorted(column_names)[:10])}...")
        
        # Vérifier les colonnes de factures
        invoice_columns_ok = True
        for column in AIRTABLE_INVOICE_FILE_COLUMNS:
            exists = column in column_names
            logger.info(f"Colonne facture '{column}': {'Existe' if exists else 'N\'existe PAS'}")
            if not exists:
                invoice_columns_ok = False
        
        # Vérifier les colonnes de statut
        status_columns_ok = True
        for file_col, status_col in AIRTABLE_SYNC_STATUS_COLUMNS.items():
            file_exists = file_col in column_names
            status_exists = status_col in column_names
            
            if file_exists and status_exists:
                logger.info(f"Mapping OK: '{file_col}' -> '{status_col}'")
            elif file_exists and not status_exists:
                logger.warning(f"Colonne facture '{file_col}' existe mais pas sa colonne de statut '{status_col}'")
                status_columns_ok = False
            elif not file_exists and status_exists:
                logger.warning(f"Colonne statut '{status_col}' existe mais pas sa colonne de facture '{file_col}'")
                status_columns_ok = False
            else:
                logger.error(f"Ni la colonne '{file_col}' ni sa colonne de statut '{status_col}' n'existent")
                status_columns_ok = False
        
        # Vérification complète
        if invoice_columns_ok and status_columns_ok:
            logger.info("✅ Toutes les colonnes du mapping existent dans Airtable")
            return True
        else:
            logger.error("❌ Certaines colonnes du mapping n'existent pas dans Airtable")
            return False
            
    except Exception as e:
        logger.error(f"Erreur lors du test du mapping: {e}")
        return False

def suggest_mapping_fixes():
    """Suggère des corrections au mapping en fonction des colonnes réellement disponibles"""
    logger.info("====================================================")
    logger.info("Recherche de corrections possibles pour le mapping")
    logger.info("====================================================")
    
    try:
        # Connexion à Airtable
        table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
        
        # Récupérer un enregistrement pour vérifier la structure
        record = table.first()
        if not record:
            logger.warning("Table vide ou inaccessible. Impossible de suggérer des corrections.")
            return
        
        # Récupérer les noms de colonnes réels
        fields = record.get('fields', {})
        column_names = list(fields.keys())
        
        # Rechercher des colonnes contenant "facture" ou "document"
        invoice_cols = [col for col in column_names if "facture" in col.lower() or "document" in col.lower()]
        logger.info(f"Colonnes potentielles de factures trouvées: {invoice_cols}")
        
        # Rechercher des colonnes contenant "sync", "status" ou "état"
        status_cols = [col for col in column_names if "sync" in col.lower() or "status" in col.lower() or "état" in col.lower()]
        logger.info(f"Colonnes potentielles de statut trouvées: {status_cols}")
        
        # Suggérer un mapping si des colonnes candidates sont trouvées
        if invoice_cols and status_cols:
            logger.info("Suggestion de mapping possible:")
            logger.info("```python")
            logger.info("AIRTABLE_INVOICE_FILE_COLUMNS = [")
            for col in invoice_cols[:3]:
                logger.info(f'    "{col}",')
            logger.info("]")
            
            logger.info("\nAIRTABLE_SYNC_STATUS_COLUMNS = {")
            for i, col in enumerate(invoice_cols[:3]):
                if i < len(status_cols):
                    logger.info(f'    "{col}": "{status_cols[i]}",')
                else:
                    logger.info(f'    "{col}": "",  # Colonne de statut manquante')
            logger.info("}")
            logger.info("```")
            
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de corrections: {e}")

if __name__ == "__main__":
    # Exécuter le test et suggérer des corrections si nécessaire
    if not test_column_mapping():
        suggest_mapping_fixes()
    else:
        logger.info("Le mapping est correct. La synchronisation peut être lancée.")

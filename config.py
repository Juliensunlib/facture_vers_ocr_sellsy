"""
Configuration pour l'intégration Airtable-Sellsy
"""
import os

# Configuration Airtable
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME")

# Noms des colonnes Airtable pour les factures fournisseurs
AIRTABLE_INVOICE_FILE_COLUMN = "Facture_PDF"  # Colonne contenant les fichiers PDF
AIRTABLE_INVOICE_DATE_COLUMN = "Date_Facture"  # Colonne contenant la date de facture
AIRTABLE_INVOICE_REF_COLUMN = "Reference_Facture"  # Colonne contenant la référence de facture
AIRTABLE_SUPPLIER_COLUMN = "Fournisseur"  # Colonne contenant le nom du fournisseur
AIRTABLE_SYNCED_COLUMN = "Synchronisé_Sellsy"  # Colonne pour marquer comme synchronisé
AIRTABLE_SELLSY_ID_COLUMN = "ID_Sellsy"  # Colonne pour stocker l'ID Sellsy

# Configuration Sellsy API V2
SELLSY_CLIENT_ID = os.environ.get("SELLSY_CLIENT_ID")
SELLSY_CLIENT_SECRET = os.environ.get("SELLSY_CLIENT_SECRET")
SELLSY_WEBHOOK_TOKEN = os.environ.get("SELLSY_WEBHOOK_TOKEN", "")

# Paramètres de synchronisation
SYNC_INTERVAL_MINUTES = 60  # Intervalle de synchronisation pour GitHub Actions
BATCH_SIZE = 10  # Nombre de factures à traiter par lot

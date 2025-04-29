"""
Configuration pour l'intégration Airtable-Sellsy
"""
import os

# Configuration Airtable
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME")

# Noms des colonnes Airtable pour les factures fournisseurs
AIRTABLE_INVOICE_FILE_COLUMNS = [
    "Facture 1 (from Documents Abonnés 3)",
    "Facture 2 (from Documents Abonnés 3)",
    "Facture 3 (from Documents Abonnés 3)"
]

# Colonnes de statut de synchronisation pour chaque facture
AIRTABLE_SYNC_STATUS_COLUMNS = {
    "Facture 1 (from Documents Abonnés 3)": "Sync_Status_Facture_1",
    "Facture 2 (from Documents Abonnés 3)": "Sync_Status_Facture_2",
    "Facture 3 (from Documents Abonnés 3)": "Sync_Status_Facture_3"
}

# Colonnes pour stocker les IDs Sellsy pour chaque facture
AIRTABLE_SELLSY_ID_COLUMNS = {
    "Facture 1 (from Documents Abonnés 3)": "ID_Sellsy_Facture_1",
    "Facture 2 (from Documents Abonnés 3)": "ID_Sellsy_Facture_2",
    "Facture 3 (from Documents Abonnés 3)": "ID_Sellsy_Facture_3"
}

# Colonne existante pour l'ID de l'abonné
AIRTABLE_SUBSCRIBER_ID_COLUMN = "ID_Sellsy"  # Contient le numéro d'abonné

# Colonnes pour les informations de l'abonné
AIRTABLE_SUBSCRIBER_FIRSTNAME_COLUMN = "Prenom"  # Prénom de l'abonné
AIRTABLE_SUBSCRIBER_LASTNAME_COLUMN = "Nom"  # Nom de l'abonné

# Ajout de la variable manquante pour la compatibilité avec l'ancien code
AIRTABLE_SELLSY_ID_COLUMN = "ID_Sellsy"  # Même que AIRTABLE_SUBSCRIBER_ID_COLUMN

AIRTABLE_CREATED_DATE_COLUMN = "Created_Time"  # Colonne contenant la date de création de l'enregistrement
AIRTABLE_SYNCED_COLUMN = "Synchronisé_Sellsy"  # Colonne principale pour marquer comme synchronisé (ancienne, gardée pour compatibilité)

# Configuration email pour l'OCR Sellsy
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")  # SMTP par défaut Gmail
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))        # Port TLS par défaut
EMAIL_USER = os.environ.get("EMAIL_USER", "marie@sunlib.fr")   # Votre adresse email
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")        # Mot de passe ou token d'app
EMAIL_FROM = os.environ.get("EMAIL_FROM", "marie@sunlib.fr")   # Adresse expéditeur
EMAIL_OCR_TO = os.environ.get("EMAIL_OCR_TO", "ocr.200978@sellsy.net")  # Adresse OCR Sellsy

# Conservation des anciens paramètres Sellsy pour compatibilité
SELLSY_CLIENT_ID = os.environ.get("SELLSY_CLIENT_ID", "")
SELLSY_CLIENT_SECRET = os.environ.get("SELLSY_CLIENT_SECRET", "")
SELLSY_WEBHOOK_TOKEN = os.environ.get("SELLSY_WEBHOOK_TOKEN", "")

# Paramètres de synchronisation
SYNC_INTERVAL_MINUTES = 60  # Intervalle de synchronisation pour GitHub Actions
BATCH_SIZE = 100  # Nombre de factures à traiter par lot - AUGMENTÉ pour traiter plus de factures

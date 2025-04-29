"""
Client pour l'API Airtable - Récupération des factures fournisseurs
"""
from pyairtable import Table
import requests
import os
import tempfile
from datetime import datetime
import logging
from config import (
    AIRTABLE_API_KEY, 
    AIRTABLE_BASE_ID, 
    AIRTABLE_TABLE_NAME,
    AIRTABLE_INVOICE_FILE_COLUMNS,
    AIRTABLE_CREATED_DATE_COLUMN,
    AIRTABLE_SYNCED_COLUMN,
    AIRTABLE_SELLSY_ID_COLUMN
)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("airtable_api")

class AirtableAPI:
    def __init__(self):
        """Initialise la connexion à l'API Airtable"""
        self.table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
        logger.info(f"Connexion à Airtable établie pour la table {AIRTABLE_TABLE_NAME}")

    def get_unsynchronized_invoices(self, limit=None):
        """
        Récupère les factures fournisseurs non encore synchronisées avec Sellsy,
        créées à partir d'aujourd'hui
        
        Args:
            limit (int, optional): Nombre maximum de factures à récupérer
            
        Returns:
            list: Liste des enregistrements Airtable
        """
        # Obtenir la date du jour au format YYYY-MM-DD
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Construire la formule pour filtrer:
        # 1. Les factures non synchronisées
        # 2. Qui ont au moins un fichier PDF dans l'une des trois colonnes
        # 3. Qui ont été créées aujourd'hui ou après
        has_files = []
        for column in AIRTABLE_INVOICE_FILE_COLUMNS:
            has_files.append(f"IS_ATTACHMENT({column})")
        
        files_formula = f"OR({','.join(has_files)})"
        sync_formula = f"OR({AIRTABLE_SYNCED_COLUMN}=BLANK(), {AIRTABLE_SYNCED_COLUMN}=FALSE())"
        date_formula = f"IS_AFTER({AIRTABLE_CREATED_DATE_COLUMN}, '{today}')"
        
        formula = f"AND({files_formula}, {sync_formula}, {date_formula})"
        
        try:
            # Récupération des enregistrements
            if limit:
                records = self.table.all(formula=formula, max_records=limit)
            else:
                records = self.table.all(formula=formula)
                
            logger.info(f"Récupération de {len(records)} factures non synchronisées créées depuis le {today}")
            return records
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des factures: {e}")
            return []

    def download_invoice_file(self, record):
        """
        Télécharge le premier fichier de facture attaché dans l'une des colonnes définies
        
        Args:
            record (dict): Enregistrement Airtable
            
        Returns:
            tuple: (Chemin vers le fichier téléchargé, Nom de la colonne source) ou (None, None) en cas d'échec
        """
        try:
            fields = record.get('fields', {})
            
            # Parcourir les colonnes de factures dans l'ordre
            for column in AIRTABLE_INVOICE_FILE_COLUMNS:
                attachments = fields.get(column, [])
                
                if attachments:
                    # Récupérer la première pièce jointe
                    attachment = attachments[0]
                    file_url = attachment.get('url')
                    file_name = attachment.get('filename')
                    
                    if not file_url:
                        continue
                        
                    # Créer un fichier temporaire avec l'extension du fichier original
                    _, file_extension = os.path.splitext(file_name)
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
                    temp_file_path = temp_file.name
                    temp_file.close()
                    
                    # Télécharger le fichier
                    response = requests.get(file_url, stream=True)
                    response.raise_for_status()
                    
                    with open(temp_file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                            
                    logger.info(f"Fichier téléchargé avec succès depuis {column}: {file_name} -> {temp_file_path}")
                    return temp_file_path, column
            
            logger.warning(f"Aucune pièce jointe trouvée pour l'enregistrement {record.get('id')}")
            return None, None
            
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement du fichier: {e}")
            return None, None

    def mark_as_synchronized(self, record_id, sellsy_id=None, file_column=None):
        """
        Marque un enregistrement comme synchronisé avec Sellsy
        
        Args:
            record_id (str): ID de l'enregistrement Airtable
            sellsy_id (str, optional): ID Sellsy de la facture créée
            file_column (str, optional): Nom de la colonne contenant le fichier synchronisé
            
        Returns:
            bool: True si la mise à jour a réussi, False sinon
        """
        try:
            update_data = {
                AIRTABLE_SYNCED_COLUMN: True,
                "Dernière_Synchronisation": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Ajouter l'ID Sellsy si fourni
            if sellsy_id:
                update_data[AIRTABLE_SELLSY_ID_COLUMN] = str(sellsy_id)
                
            # Ajouter quelle colonne a été synchronisée si fournie
            if file_column:
                update_data["Colonne_Synchronisée"] = file_column
                
            self.table.update(record_id, update_data)
            logger.info(f"Enregistrement {record_id} marqué comme synchronisé (Sellsy ID: {sellsy_id}, Colonne: {file_column})")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut de synchronisation: {e}")
            return False

    def get_invoice_data(self, record):
        """
        Extrait les données minimales de facture d'un enregistrement Airtable
        
        Args:
            record (dict): Enregistrement Airtable
            
        Returns:
            dict: Données de la facture pour Sellsy
        """
        # Structure minimale pour l'envoi à l'OCR
        invoice_data = {
            "record_id": record.get('id'),
            "reference": "",  # Laissé vide pour que l'OCR le détecte automatiquement
            "date": "",       # Laissé vide pour que l'OCR le détecte automatiquement
            "supplier_name": "", # Laissé vide pour que l'OCR le détecte automatiquement
            "file_path": None  # Sera mis à jour après le téléchargement
        }
        
        return invoice_data

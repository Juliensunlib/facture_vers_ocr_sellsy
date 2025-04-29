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
    AIRTABLE_INVOICE_FILE_COLUMN,
    AIRTABLE_INVOICE_DATE_COLUMN, 
    AIRTABLE_INVOICE_REF_COLUMN,
    AIRTABLE_SUPPLIER_COLUMN,
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
        Récupère les factures fournisseurs non encore synchronisées avec Sellsy
        
        Args:
            limit (int, optional): Nombre maximum de factures à récupérer
            
        Returns:
            list: Liste des enregistrements Airtable
        """
        # Formule pour filtrer les factures non synchronisées avec Sellsy et qui ont un fichier PDF
        formula = f"AND(IS_ATTACHMENT({AIRTABLE_INVOICE_FILE_COLUMN}), OR({AIRTABLE_SYNCED_COLUMN}=BLANK(), {AIRTABLE_SYNCED_COLUMN}=FALSE()))"
        
        try:
            # Récupération des enregistrements
            if limit:
                records = self.table.all(formula=formula, max_records=limit)
            else:
                records = self.table.all(formula=formula)
                
            logger.info(f"Récupération de {len(records)} factures non synchronisées")
            return records
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des factures: {e}")
            return []

    def download_invoice_file(self, record):
        """
        Télécharge le fichier de facture attaché à un enregistrement Airtable
        
        Args:
            record (dict): Enregistrement Airtable
            
        Returns:
            str: Chemin vers le fichier téléchargé, ou None en cas d'échec
        """
        try:
            fields = record.get('fields', {})
            attachments = fields.get(AIRTABLE_INVOICE_FILE_COLUMN, [])
            
            if not attachments:
                logger.warning(f"Pas de pièce jointe trouvée pour l'enregistrement {record.get('id')}")
                return None
                
            # Récupérer la première pièce jointe
            attachment = attachments[0]
            file_url = attachment.get('url')
            file_name = attachment.get('filename')
            
            if not file_url:
                logger.warning(f"URL de téléchargement manquante pour l'enregistrement {record.get('id')}")
                return None
                
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
                    
            logger.info(f"Fichier téléchargé avec succès: {file_name} -> {temp_file_path}")
            return temp_file_path
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement du fichier: {e}")
            return None

    def mark_as_synchronized(self, record_id, sellsy_id=None):
        """
        Marque un enregistrement comme synchronisé avec Sellsy
        
        Args:
            record_id (str): ID de l'enregistrement Airtable
            sellsy_id (str, optional): ID Sellsy de la facture créée
            
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
                
            self.table.update(record_id, update_data)
            logger.info(f"Enregistrement {record_id} marqué comme synchronisé (Sellsy ID: {sellsy_id})")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut de synchronisation: {e}")
            return False

    def get_invoice_data(self, record):
        """
        Extrait les données de facture d'un enregistrement Airtable
        
        Args:
            record (dict): Enregistrement Airtable
            
        Returns:
            dict: Données de la facture pour Sellsy
        """
        fields = record.get('fields', {})
        
        # Extraction des données de base
        invoice_data = {
            "record_id": record.get('id'),
            "reference": fields.get(AIRTABLE_INVOICE_REF_COLUMN, ""),
            "date": fields.get(AIRTABLE_INVOICE_DATE_COLUMN, ""),
            "supplier_name": fields.get(AIRTABLE_SUPPLIER_COLUMN, ""),
            "file_path": None  # Sera mis à jour après le téléchargement
        }
        
        # Convertir la date au format ISO si nécessaire
        if invoice_data["date"] and not isinstance(invoice_data["date"], str):
            try:
                # Si c'est un objet datetime ou similaire
                invoice_data["date"] = invoice_data["date"].strftime("%Y-%m-%d")
            except (AttributeError, TypeError):
                # Garder la valeur telle quelle
                pass
        
        return invoice_data

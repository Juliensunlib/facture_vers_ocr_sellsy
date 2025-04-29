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
    AIRTABLE_SELLSY_ID_COLUMN,  # Maintenant défini dans config.py
    AIRTABLE_SYNC_STATUS_COLUMNS,
    AIRTABLE_SELLSY_ID_COLUMNS,
    AIRTABLE_SUBSCRIBER_ID_COLUMN
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
        
        # Approche simplifiée pour la formule
        # Au lieu d'utiliser IS_ATTACHMENT qui peut causer des problèmes
        # Nous allons filtrer en fonction des statuts de synchronisation 
        # et vérifier la présence de pièces jointes après le filtrage
        formula_conditions = []
        
        for column, sync_column in AIRTABLE_SYNC_STATUS_COLUMNS.items():
            # Vérifier seulement si le statut est BLANK() ou FALSE()
            formula_conditions.append(f"OR({sync_column}=BLANK(), {sync_column}=FALSE())")
        
        # Combine all conditions with OR
        if formula_conditions:
            formula = f"OR({','.join(formula_conditions)})"
        else:
            formula = ""
            
        try:
            # Récupération des enregistrements
            if formula:
                if limit:
                    records = self.table.all(formula=formula, max_records=limit)
                else:
                    records = self.table.all(formula=formula)
            else:
                if limit:
                    records = self.table.all(max_records=limit)
                else:
                    records = self.table.all()
                
            # Filtrer manuellement les enregistrements qui ont réellement des pièces jointes
            filtered_records = []
            for record in records:
                fields = record.get('fields', {})
                for column in AIRTABLE_INVOICE_FILE_COLUMNS:
                    # Vérifier si la colonne a un fichier attaché
                    attachments = fields.get(column, [])
                    if attachments:
                        # Vérifier le statut de synchronisation
                        sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
                        is_synced = fields.get(sync_column, False) if sync_column else True
                        
                        # Si au moins une colonne a un fichier et n'est pas synchronisée, ajouter l'enregistrement
                        if not is_synced:
                            filtered_records.append(record)
                            break
            
            logger.info(f"Récupération de {len(filtered_records)} enregistrements avec factures non synchronisées")
            return filtered_records
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des factures: {e}")
            return []

    def get_next_unsynchronized_file(self, record):
        """
        Trouve la prochaine colonne de facture non synchronisée dans un enregistrement
        
        Args:
            record (dict): Enregistrement Airtable
            
        Returns:
            str: Nom de la colonne contenant une facture non synchronisée, ou None si tout est synchronisé
        """
        fields = record.get('fields', {})
        
        for column in AIRTABLE_INVOICE_FILE_COLUMNS:
            attachments = fields.get(column, [])
            sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
            
            # Vérifier si la colonne a un fichier
            if attachments:
                # Vérifier si la colonne n'est pas marquée comme synchronisée
                if sync_column and not fields.get(sync_column, False):
                    return column
        
        return None

    def download_invoice_file(self, record, file_column):
        """
        Télécharge le premier fichier de facture attaché dans une colonne spécifique
        
        Args:
            record (dict): Enregistrement Airtable
            file_column (str): Nom de la colonne contenant le fichier à télécharger
            
        Returns:
            str: Chemin vers le fichier téléchargé, ou None en cas d'échec
        """
        try:
            fields = record.get('fields', {})
            attachments = fields.get(file_column, [])
            
            if not attachments:
                logger.warning(f"Aucune pièce jointe trouvée dans la colonne {file_column} pour l'enregistrement {record.get('id')}")
                return None
                
            # Récupérer la première pièce jointe
            attachment = attachments[0]
            file_url = attachment.get('url')
            file_name = attachment.get('filename')
            
            if not file_url:
                logger.warning(f"URL de pièce jointe manquante dans {file_column}")
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
                    
            logger.info(f"Fichier téléchargé avec succès depuis {file_column}: {file_name} -> {temp_file_path}")
            return temp_file_path
            
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement du fichier depuis {file_column}: {e}")
            return None

    def mark_file_as_synchronized(self, record_id, file_column, sellsy_id=None):
        """
        Marque une colonne de facture spécifique comme synchronisée avec Sellsy
        
        Args:
            record_id (str): ID de l'enregistrement Airtable
            file_column (str): Nom de la colonne contenant le fichier synchronisé
            sellsy_id (str, optional): ID Sellsy de la facture créée
            
        Returns:
            bool: True si la mise à jour a réussi, False sinon
        """
        try:
            # Identifier les colonnes de statut et d'ID correspondantes
            sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(file_column)
            id_column = AIRTABLE_SELLSY_ID_COLUMNS.get(file_column)
            
            if not sync_column:
                logger.error(f"Colonne de statut de synchronisation non trouvée pour {file_column}")
                return False
                
            update_data = {
                sync_column: True,
                "Colonne_Synchronisée": file_column,
                "Dernière_Synchronisation": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Ajouter l'ID Sellsy si fourni et si la colonne ID existe
            if sellsy_id and id_column:
                update_data[id_column] = str(sellsy_id)
                
            self.table.update(record_id, update_data)
            logger.info(f"Facture dans {file_column} marquée comme synchronisée pour l'enregistrement {record_id} (Sellsy ID: {sellsy_id})")
            
            # Vérifier si toutes les factures sont synchronisées pour mettre à jour la colonne globale
            self._update_global_sync_status(record_id)
            
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut de synchronisation pour {file_column}: {e}")
            return False

    def _update_global_sync_status(self, record_id):
        """
        Met à jour le statut global de synchronisation si toutes les factures sont synchronisées
        
        Args:
            record_id (str): ID de l'enregistrement Airtable
        """
        try:
            # Récupérer l'enregistrement complet
            record = self.table.get(record_id)
            if not record:
                return
                
            fields = record.get('fields', {})
            
            # Vérifier si toutes les factures avec pièces jointes sont synchronisées
            all_synced = True
            
            for column in AIRTABLE_INVOICE_FILE_COLUMNS:
                attachments = fields.get(column, [])
                sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
                
                # Si la colonne a un fichier mais n'est pas synchronisée
                if attachments and sync_column and not fields.get(sync_column, False):
                    all_synced = False
                    break
            
            # Mettre à jour le statut global uniquement si tout est synchronisé
            if all_synced:
                self.table.update(record_id, {
                    AIRTABLE_SYNCED_COLUMN: True,
                    "Dernière_Synchronisation_Complete": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                logger.info(f"Toutes les factures sont synchronisées pour l'enregistrement {record_id}")
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut global: {e}")

    def get_invoice_data(self, record, file_column):
        """
        Extrait les données minimales de facture d'un enregistrement Airtable
        
        Args:
            record (dict): Enregistrement Airtable
            file_column (str): Nom de la colonne contenant le fichier
            
        Returns:
            dict: Données de la facture pour Sellsy
        """
        fields = record.get('fields', {})
        
        # Récupérer le numéro d'abonné si disponible
        subscriber_id = fields.get(AIRTABLE_SUBSCRIBER_ID_COLUMN, "")
        
        # Structure minimale pour l'envoi à l'OCR
        invoice_data = {
            "record_id": record.get('id'),
            "subscriber_id": subscriber_id,
            "file_column": file_column,
            "reference": "",  # Laissé vide pour que l'OCR le détecte automatiquement
            "date": "",       # Laissé vide pour que l'OCR le détecte automatiquement
            "supplier_name": "", # Laissé vide pour que l'OCR le détecte automatiquement
        }
        
        return invoice_data

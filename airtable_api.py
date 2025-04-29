"""
Client pour l'API Airtable - Récupération des factures fournisseurs
Version mise à jour avec la nouvelle logique de synchronisation
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
    AIRTABLE_SELLSY_ID_COLUMN,
    AIRTABLE_SYNC_STATUS_COLUMNS,
    AIRTABLE_SELLSY_ID_COLUMNS,
    AIRTABLE_SUBSCRIBER_ID_COLUMN,
    AIRTABLE_SUBSCRIBER_FIRSTNAME_COLUMN,
    AIRTABLE_SUBSCRIBER_LASTNAME_COLUMN
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
        try:
            logger.info("Récupération des enregistrements Airtable...")
            
            # Récupérer tous les enregistrements sans filtrage initial
            # Nous filtrerons en mémoire pour plus de fiabilité
            if limit:
                records = self.table.all(max_records=limit)
            else:
                records = self.table.all()
            
            logger.info(f"Récupération de {len(records)} enregistrements au total")
            
            # Filtrer en mémoire pour trouver les enregistrements avec des factures non synchronisées
            validated_records = []
            for record in records:
                fields = record.get('fields', {})
                has_unsync_file = False
                
                for column in AIRTABLE_INVOICE_FILE_COLUMNS:
                    attachments = fields.get(column, [])
                    if attachments:
                        sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
                        is_synced = fields.get(sync_column, False) if sync_column else False
                        
                        if not is_synced:
                            has_unsync_file = True
                            break
                
                if has_unsync_file:
                    validated_records.append(record)
            
            logger.info(f"Après validation: {len(validated_records)} enregistrements avec factures non synchronisées")
            return validated_records
            
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
                # Vérifier si la colonne n'est pas marquée comme synchronisée (FALSE ou BLANK)
                is_synced = fields.get(sync_column, False) if sync_column else False
                if not is_synced:
                    return column
        
        return None

    def download_invoice_file(self, record, file_column):
        """
        Télécharge le premier fichier de facture attaché dans une colonne spécifique
        
        Args:
            record (dict): Enregistrement Airtable
            file_column (str): Nom de la colonne contenant le fichier à télécharger
            
        Returns:
            tuple: (Chemin vers le fichier téléchargé, nom original du fichier) ou (None, None) en cas d'échec
        """
        try:
            fields = record.get('fields', {})
            attachments = fields.get(file_column, [])
            
            if not attachments:
                logger.warning(f"Aucune pièce jointe trouvée dans la colonne {file_column} pour l'enregistrement {record.get('id')}")
                return None, None
                
            # Récupérer la première pièce jointe
            attachment = attachments[0]
            file_url = attachment.get('url')
            file_name = attachment.get('filename')
            
            if not file_url:
                logger.warning(f"URL de pièce jointe manquante dans {file_column}")
                return None, None
                
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
            return temp_file_path, file_name
            
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement du fichier depuis {file_column}: {e}")
            return None, None

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
            # Identifier la colonne de statut correspondante
            sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(file_column)
            
            if not sync_column:
                logger.error(f"Colonne de statut de synchronisation non trouvée pour {file_column}")
                return False
            
            # Identifier la colonne pour stocker l'ID Sellsy si applicable
            sellsy_id_column = AIRTABLE_SELLSY_ID_COLUMNS.get(file_column)
            
            # Logging des valeurs avant mise à jour
            logger.info(f"Mise à jour pour le record {record_id}, colonne de statut {sync_column}")
                
            # Préparer les données à mettre à jour
            update_data = {
                sync_column: True  # Utiliser True pour les cases à cocher Airtable
            }
            
            # Si un ID Sellsy est fourni et qu'une colonne dédiée existe, l'ajouter
            if sellsy_id and sellsy_id_column:
                update_data[sellsy_id_column] = sellsy_id
                logger.info(f"Stockage de l'ID Sellsy {sellsy_id} dans la colonne {sellsy_id_column}")
            
            # Log de débogage
            logger.info(f"Données de mise à jour: {update_data}")
                
            # Effectuer la mise à jour
            result = self.table.update(record_id, update_data)
            
            # Log de débogage - Afficher le résultat de la mise à jour
            logger.info(f"Résultat de la mise à jour: {result}")
            
            logger.info(f"Facture dans {file_column} marquée comme synchronisée pour l'enregistrement {record_id} (Sellsy ID: {sellsy_id})")
            
            # Mettre à jour le statut global
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
            # Récupérer l'enregistrement complet pour obtenir les statuts à jour
            record = self.table.get(record_id)
            if not record:
                logger.warning(f"Enregistrement {record_id} non trouvé lors de la mise à jour du statut global")
                return
                
            fields = record.get('fields', {})
            
            # Variables pour le suivi
            all_synced = True
            has_attachments = False
            
            # Pour chaque colonne de facture
            for column in AIRTABLE_INVOICE_FILE_COLUMNS:
                attachments = fields.get(column, [])
                
                # Si cette colonne a un fichier attaché
                if attachments:
                    has_attachments = True
                    sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
                    
                    # Vérifier si le statut est explicitement True
                    # Si le champ n'existe pas (None) ou est False, considérer comme non synchronisé
                    sync_status = fields.get(sync_column, False)
                    if not sync_status:
                        all_synced = False
                        logger.info(f"La colonne {column} n'est pas synchronisée, statut global reste à False")
                        break
            
            logger.info(f"État de synchronisation pour record {record_id}: has_attachments={has_attachments}, all_synced={all_synced}")
            
            # Mettre à jour le statut global uniquement si tout est synchronisé ET il y a au moins une pièce jointe
            current_global_status = fields.get(AIRTABLE_SYNCED_COLUMN, False)
            
            if has_attachments:
                if all_synced and not current_global_status:
                    # Si tout est synchronisé mais le statut global est False ou absent
                    update_result = self.table.update(record_id, {
                        AIRTABLE_SYNCED_COLUMN: True
                    })
                    logger.info(f"Toutes les factures sont synchronisées - Champ global mis à jour à TRUE pour {record_id}")
                    logger.debug(f"Résultat mise à jour globale: {update_result}")
                elif not all_synced and current_global_status:
                    # Si au moins une facture n'est pas synchronisée et le statut global est True
                    update_result = self.table.update(record_id, {
                        AIRTABLE_SYNCED_COLUMN: False
                    })
                    logger.info(f"Certaines factures ne sont pas synchronisées - Champ global mis à jour à FALSE pour {record_id}")
                    logger.debug(f"Résultat mise à jour globale: {update_result}")
            else:
                logger.info(f"Aucune pièce jointe trouvée pour l'enregistrement {record_id} - Aucune mise à jour du statut global")
        
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
        
        # Récupérer le nom et prénom si disponibles
        first_name = fields.get(AIRTABLE_SUBSCRIBER_FIRSTNAME_COLUMN, "")
        last_name = fields.get(AIRTABLE_SUBSCRIBER_LASTNAME_COLUMN, "")
        
        # Structure minimale pour l'envoi à l'OCR
        invoice_data = {
            "record_id": record.get('id'),
            "subscriber_id": subscriber_id,
            "file_column": file_column,
            "first_name": first_name,
            "last_name": last_name,
            "reference": "",  # Laissé vide pour que l'OCR le détecte automatiquement
            "date": "",       # Laissé vide pour que l'OCR le détecte automatiquement
            "supplier_name": "", # Laissé vide pour que l'OCR le détecte automatiquement
        }
        
        return invoice_data

    def check_global_sync_status(self, record_id):
        """
        Vérifie si toutes les factures d'un enregistrement sont synchronisées
        
        Args:
            record_id (str): ID de l'enregistrement Airtable
        
        Returns:
            tuple: (bool: présence d'attachements, bool: tous synchronisés)
        """
        try:
            # Récupérer l'enregistrement
            record = self.table.get(record_id)
            if not record:
                logger.warning(f"Enregistrement {record_id} non trouvé lors de la vérification du statut")
                return False, False
                
            fields = record.get('fields', {})
            
            has_attachments = False
            all_synced = True
            
            # Vérifier chaque colonne de facture
            for column in AIRTABLE_INVOICE_FILE_COLUMNS:
                attachments = fields.get(column, [])
                
                if attachments:
                    has_attachments = True
                    sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
                    is_synced = fields.get(sync_column, False) if sync_column else False
                    
                    if not is_synced:
                        all_synced = False
                        break
            
            return has_attachments, all_synced
        
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du statut global: {e}")
            return False, False

    def set_global_sync_status(self, record_id, status):
        """
        Définit explicitement le statut global de synchronisation
        
        Args:
            record_id (str): ID de l'enregistrement Airtable
            status (bool): Nouveau statut (True/False)
            
        Returns:
            bool: True si la mise à jour a réussi, False sinon
        """
        try:
            update_data = {
                AIRTABLE_SYNCED_COLUMN: status
            }
            
            result = self.table.update(record_id, update_data)
            
            if result:
                status_text = "TRUE" if status else "FALSE"
                logger.info(f"Statut global de synchronisation mis à jour à {status_text} pour l'enregistrement {record_id}")
                return True
            else:
                logger.warning(f"Échec de la mise à jour du statut global pour l'enregistrement {record_id}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de la définition du statut global: {e}")
            return False

    def get_unprocessed_files_count(self, record_id):
        """
        Compte le nombre de fichiers non synchronisés dans un enregistrement
        
        Args:
            record_id (str): ID de l'enregistrement Airtable
            
        Returns:
            int: Nombre de fichiers non synchronisés (0 si aucun trouvé ou erreur)
        """
        try:
            record = self.table.get(record_id)
            if not record:
                return 0
                
            fields = record.get('fields', {})
            unprocessed_count = 0
            
            for column in AIRTABLE_INVOICE_FILE_COLUMNS:
                attachments = fields.get(column, [])
                if attachments:
                    sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
                    is_synced = fields.get(sync_column, False) if sync_column else False
                    
                    if not is_synced:
                        unprocessed_count += 1
            
            return unprocessed_count
            
        except Exception as e:
            logger.error(f"Erreur lors du comptage des fichiers non traités: {e}")
            return 0

    def get_all_file_statuses(self, record_id):
        """
        Récupère les statuts de synchronisation pour tous les fichiers d'un enregistrement
        
        Args:
            record_id (str): ID de l'enregistrement Airtable
            
        Returns:
            dict: {column_name: {'has_file': bool, 'is_synced': bool}}
        """
        try:
            record = self.table.get(record_id)
            if not record:
                return {}
                
            fields = record.get('fields', {})
            statuses = {}
            
            for column in AIRTABLE_INVOICE_FILE_COLUMNS:
                attachments = fields.get(column, [])
                has_file = bool(attachments)
                
                sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
                is_synced = fields.get(sync_column, False) if sync_column and has_file else False
                
                statuses[column] = {
                    'has_file': has_file,
                    'is_synced': is_synced,
                    'file_name': attachments[0].get('filename') if has_file else None
                }
            
            return statuses
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statuts de fichiers: {e}")
            return {}

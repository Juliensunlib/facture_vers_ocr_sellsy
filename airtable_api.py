"""
Client corrigé pour l'API Airtable - Récupération des factures fournisseurs
Adaptation pour tenir compte des champs manquants ou différents
Version améliorée pour gérer l'absence des colonnes ID_Sellsy_Facture_
"""
from pyairtable import Table
import requests
import os
import tempfile
import logging
from config import (  # Changé config_fixed en config
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
    AIRTABLE_SUBSCRIBER_LASTNAME_COLUMN,
    TRUST_COLUMN_MAPPING  # Nouvelle option ajoutée dans config.py
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
        
        # CORRECTION: Vérifier quels champs existent réellement dans la table
        self._check_table_structure()
    
    def _check_table_structure(self):
        """
        Vérifie la structure de la table Airtable pour déterminer quels champs existent réellement
        Version corrigée qui fait confiance au mapping si l'option est activée
        """
        # CORRECTION: Faire confiance au mapping défini si l'option est activée
        if TRUST_COLUMN_MAPPING:
            logger.info("Utilisation du mapping de colonnes défini dans config.py sans vérification")
            self.has_subscriber_id = AIRTABLE_SUBSCRIBER_ID_COLUMN != ""
            self.has_firstname = AIRTABLE_SUBSCRIBER_FIRSTNAME_COLUMN != ""
            self.has_lastname = AIRTABLE_SUBSCRIBER_LASTNAME_COLUMN != ""
            self.has_global_sync = AIRTABLE_SYNCED_COLUMN != ""
            self.sync_status_columns = AIRTABLE_SYNC_STATUS_COLUMNS.copy()
            self.sellsy_id_columns = AIRTABLE_SELLSY_ID_COLUMNS.copy()
            return
        
        try:
            # Récupérer plusieurs enregistrements pour une meilleure détection
            records = self.table.all(max_records=10)  # Examiner jusqu'à 10 enregistrements
            if not records:
                logger.warning("Table vide ou inaccessible, impossible de vérifier sa structure")
                # Initialiser avec des valeurs par défaut en cas d'échec
                self.has_subscriber_id = False
                self.has_firstname = False
                self.has_lastname = False
                self.has_global_sync = False
                self.sync_status_columns = {}
                self.sellsy_id_columns = {}
                return
            
            # Combiner tous les champs trouvés dans tous les enregistrements
            all_fields = set()
            for record in records:
                fields = record.get('fields', {})
                all_fields.update(fields.keys())
                
            logger.info(f"Champs détectés dans Airtable: {', '.join(all_fields)}")
            
            # Vérifier les champs globaux
            self.has_subscriber_id = AIRTABLE_SUBSCRIBER_ID_COLUMN in all_fields
            self.has_firstname = AIRTABLE_SUBSCRIBER_FIRSTNAME_COLUMN in all_fields
            self.has_lastname = AIRTABLE_SUBSCRIBER_LASTNAME_COLUMN in all_fields
            self.has_global_sync = AIRTABLE_SYNCED_COLUMN in all_fields
            
            # Vérifier les champs de status de synchronisation
            self.sync_status_columns = {}
            for file_col, status_col in AIRTABLE_SYNC_STATUS_COLUMNS.items():
                if file_col in all_fields and status_col in all_fields:
                    self.sync_status_columns[file_col] = status_col
                elif file_col in all_fields:
                    logger.warning(f"Colonne de fichier {file_col} existe mais pas sa colonne de statut {status_col}")
                    # Continuer sans le statut, on considérera toujours non synchronisé
                    
            # Vérifier les champs d'ID Sellsy
            self.sellsy_id_columns = {}
            for file_col, id_col in AIRTABLE_SELLSY_ID_COLUMNS.items():
                if id_col and file_col in all_fields and id_col in all_fields:
                    self.sellsy_id_columns[file_col] = id_col
                    
            # Journaliser les résultats
            logger.info(f"Structure de table détectée:")
            logger.info(f"  - Champ ID Abonné: {self.has_subscriber_id}")
            logger.info(f"  - Champ Prénom: {self.has_firstname}")
            logger.info(f"  - Champ Nom: {self.has_lastname}")
            logger.info(f"  - Statut global de synchronisation: {self.has_global_sync}")
            logger.info(f"  - Colonnes de statut de synchronisation: {len(self.sync_status_columns)}")
            logger.info(f"  - Colonnes d'ID Sellsy: {len(self.sellsy_id_columns)}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de la structure de la table: {e}")
            # Initialiser avec des valeurs par défaut en cas d'échec
            self.has_subscriber_id = False
            self.has_firstname = False
            self.has_lastname = False
            self.has_global_sync = False
            self.sync_status_columns = {}
            self.sellsy_id_columns = {}

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
                    # Vérifier si la colonne de fichier existe dans l'enregistrement
                    attachments = fields.get(column, [])
                    if attachments:
                        # Utiliser la colonne de statut correspondante si elle existe
                        sync_column = self.sync_status_columns.get(column)
                        if sync_column:
                            # CORRECTION: Considérer explicitement que False ou champ manquant = non synchronisé
                            is_synced = fields.get(sync_column, False)
                            if not is_synced:
                                has_unsync_file = True
                                break
                        else:
                            # CORRECTION: Avec TRUST_COLUMN_MAPPING, on considère que la colonne existe
                            if TRUST_COLUMN_MAPPING and column in AIRTABLE_SYNC_STATUS_COLUMNS:
                                logger.info(f"Colonne {column} considérée comme non synchronisée (confiance au mapping)")
                                has_unsync_file = True
                                break
                            else:
                                logger.warning(f"Colonne de statut manquante pour {column} dans l'enregistrement {record.get('id', 'inconnu')}, ignorée")
                                continue
                
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
        Version améliorée avec vérification stricte des colonnes
        
        Args:
            record (dict): Enregistrement Airtable
            
        Returns:
            str: Nom de la colonne contenant une facture non synchronisée, ou None si tout est synchronisé
        """
        fields = record.get('fields', {})
        record_id = record.get('id', 'inconnu')
        
        logger.info(f"Recherche de factures non synchronisées pour l'enregistrement {record_id}")
        
        # Vérifier chaque colonne de facture dans l'ordre défini
        for column in AIRTABLE_INVOICE_FILE_COLUMNS:
            # Vérifier si la colonne existe et contient un fichier
            attachments = fields.get(column, [])
            if not attachments:
                logger.debug(f"Colonne {column} : pas de fichier attaché")
                continue
            
            # Récupérer le nom exact de la colonne de statut correspondante
            sync_column = self.sync_status_columns.get(column)
            
            # CORRECTION: Avec TRUST_COLUMN_MAPPING activé, on fait confiance au mapping défini
            if not sync_column and TRUST_COLUMN_MAPPING:
                sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
                if sync_column:
                    logger.debug(f"Utilisation du mapping défini pour la colonne de statut: {sync_column}")
            
            if not sync_column:
                # CORRECTION: Ne pas retourner les colonnes sans colonne de statut correspondante
                # car mark_file_as_synchronized ne pourra pas les traiter
                logger.warning(f"Colonne de statut manquante pour {column}, ignorée car non modifiable")
                continue
            
            # Vérifier explicitement si le statut est False ou manquant/vide
            is_synced = fields.get(sync_column, False)
            
            # Logging détaillé pour le débogage
            logger.debug(f"Colonne {column}, statut {sync_column} = {is_synced}")
            
            if not is_synced:
                logger.info(f"Fichier non synchronisé trouvé dans {column} (statut: {is_synced})")
                return column
            else:
                logger.debug(f"Colonne {column} : déjà synchronisée")
        
        logger.info(f"Aucune facture non synchronisée trouvée pour l'enregistrement {record_id}")
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
        Version améliorée avec vérifications supplémentaires
        
        Args:
            record_id (str): ID de l'enregistrement Airtable
            file_column (str): Nom exact de la colonne contenant le fichier synchronisé
            sellsy_id (str, optional): ID Sellsy de la facture créée
            
        Returns:
            bool: True si la mise à jour a réussi, False sinon
        """
        try:
            # Vérifier que le fichier_column est bien dans notre mapping
            if file_column not in AIRTABLE_INVOICE_FILE_COLUMNS:
                logger.error(f"Colonne {file_column} non reconnue dans le mapping des colonnes de factures")
                return False
            
            # Identifier la colonne de statut correspondante
            sync_column = self.sync_status_columns.get(file_column)
            
            # CORRECTION: Avec TRUST_COLUMN_MAPPING activé, on fait confiance au mapping défini
            if not sync_column and TRUST_COLUMN_MAPPING:
                sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(file_column)
                if sync_column:
                    logger.debug(f"Utilisation du mapping défini pour la colonne de statut: {sync_column}")
            
            if not sync_column:
                logger.error(f"Colonne de statut de synchronisation non trouvée pour {file_column}. Impossible de marquer comme synchronisé.")
                return False
            
            # Vérifier que l'enregistrement existe toujours
            record = self.table.get(record_id)
            if not record:
                logger.error(f"L'enregistrement {record_id} n'existe pas ou n'est plus accessible")
                return False
                
            # Logging des valeurs avant mise à jour
            logger.info(f"Mise à jour pour le record {record_id}, colonne de statut {sync_column}")
            
            # Préparer les données à mettre à jour en utilisant une valeur booléenne explicite
            update_data = {
                sync_column: True  # Valeur booléenne explicite pour Airtable
            }
            
            # Si un ID Sellsy est fourni et qu'une colonne dédiée existe, l'ajouter
            sellsy_id_column = self.sellsy_id_columns.get(file_column)
            
            # CORRECTION: Avec TRUST_COLUMN_MAPPING activé, on fait confiance au mapping défini
            if not sellsy_id_column and TRUST_COLUMN_MAPPING:
                sellsy_id_column = AIRTABLE_SELLSY_ID_COLUMNS.get(file_column)
                
            if sellsy_id and sellsy_id_column:
                update_data[sellsy_id_column] = sellsy_id
                logger.info(f"Stockage de l'ID Sellsy {sellsy_id} dans la colonne {sellsy_id_column}")
            elif sellsy_id:
                logger.info(f"ID Sellsy {sellsy_id} généré mais pas de colonne pour le stocker")
            
            # Log de débogage
            logger.info(f"Données de mise à jour: {update_data}")
                
            # Effectuer la mise à jour en utilisant la méthode correcte de l'API Airtable
            result = self.table.update(record_id, update_data)
            
            # Vérifier que la mise à jour a bien été effectuée
            if not result or not isinstance(result, dict):
                logger.error(f"La mise à jour de l'enregistrement {record_id} a échoué ou n'a pas renvoyé de résultat valide")
                return False
                
            # Log du résultat de la mise à jour
            logger.info(f"Mise à jour réussie: {result.get('id') == record_id}")
            
            # Mettre à jour le statut global si nécessaire
            if self.has_global_sync:
                self._update_global_sync_status(record_id)
            
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut de synchronisation pour {file_column}: {e}")
            return False

    def _update_global_sync_status(self, record_id):
        """
        Met à jour le statut global de synchronisation si toutes les factures sont synchronisées
        (Uniquement utilisé si le champ global existe)
        
        Args:
            record_id (str): ID de l'enregistrement Airtable
        """
        # Ne rien faire si le champ global n'existe pas
        if not self.has_global_sync:
            return
            
        try:
            # Récupérer l'enregistrement complet pour obtenir les statuts à jour
            record = self.table.get(record_id)
            if not record:
                logger.warning(f"Enregistrement {record_id} non trouvé lors de la mise à jour du statut global")
                return
                
            fields = record.get('fields', {})
            
            all_synced = True
            has_attachments = False
            
            # Pour chaque colonne de facture
            for column in AIRTABLE_INVOICE_FILE_COLUMNS:
                attachments = fields.get(column, [])
                
                # Si cette colonne a un fichier attaché
                if attachments:
                    has_attachments = True
                    sync_column = self.sync_status_columns.get(column)
                    
                    # CORRECTION: Avec TRUST_COLUMN_MAPPING activé, on fait confiance au mapping défini
                    if not sync_column and TRUST_COLUMN_MAPPING:
                        sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
                    
                    if sync_column:
                        # Vérifier si le statut est explicitement True
                        sync_status = fields.get(sync_column, False)
                        if not sync_status:
                            all_synced = False
                            break
                    else:
                        # Si pas de colonne de statut, considérer comme non synchronisé
                        all_synced = False
                        break
            
            # Mettre à jour le statut global uniquement si tout est synchronisé ET il y a des pièces jointes
            if has_attachments:
                current_global_status = fields.get(AIRTABLE_SYNCED_COLUMN, False)
                
                if all_synced != current_global_status:
                    self.table.update(record_id, {
                        AIRTABLE_SYNCED_COLUMN: all_synced
                    })
                    logger.info(f"Statut global mis à jour à {all_synced} pour l'enregistrement {record_id}")
        
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
        
        # Structure minimale pour l'OCR
        invoice_data = {
            "record_id": record.get('id'),
            "file_column": file_column,
            "reference": "",  # Laissé vide pour l'OCR
            "date": "",       # Laissé vide pour l'OCR
            "supplier_name": "", # Laissé vide pour l'OCR
        }
        
        # Ajouter l'ID d'abonné si disponible
        if self.has_subscriber_id:
            invoice_data["subscriber_id"] = fields.get(AIRTABLE_SUBSCRIBER_ID_COLUMN, "")
        else:
            invoice_data["subscriber_id"] = ""
            
        # Ajouter prénom et nom si disponibles
        if self.has_firstname:
            invoice_data["first_name"] = fields.get(AIRTABLE_SUBSCRIBER_FIRSTNAME_COLUMN, "")
        else:
            invoice_data["first_name"] = ""
            
        if self.has_lastname:
            invoice_data["last_name"] = fields.get(AIRTABLE_SUBSCRIBER_LASTNAME_COLUMN, "")
        else:
            invoice_data["last_name"] = ""
        
        return invoice_data

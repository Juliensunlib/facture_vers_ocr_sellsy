"""
Script principal pour synchroniser les factures fournisseurs d'Airtable vers Sellsy par email
"""
import os
import logging
import time
from airtable_api import AirtableAPI
from email_sender import EmailSender
from config import BATCH_SIZE, AIRTABLE_INVOICE_FILE_COLUMNS, AIRTABLE_SYNC_STATUS_COLUMNS, AIRTABLE_SYNCED_COLUMN

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sync_process")

def sync_invoices_to_sellsy():
    """
    Synchronise les factures fournisseurs d'Airtable vers Sellsy via email OCR
    Logique améliorée :
    1. Vérification du statut global de synchronisation
    2. Traitement des factures non synchronisées uniquement
    3. Mise à jour du statut global lorsque toutes les factures sont synchronisées
    """
    logger.info("Démarrage de la synchronisation Airtable -> Sellsy (via email OCR)")
    
    # Initialiser les clients API
    airtable = AirtableAPI()
    email_client = EmailSender()
    
    # Récupérer les enregistrements avec des factures non synchronisées
    unsync_records = airtable.get_unsynchronized_invoices(limit=BATCH_SIZE)
    
    if not unsync_records:
        logger.info("Aucune facture à synchroniser")
        return
        
    logger.info(f"Traitement de {len(unsync_records)} enregistrements")
    
    # Compteurs pour le suivi
    success_count = 0
    error_count = 0
    
    # Traiter chaque enregistrement
    for record in unsync_records:
        record_id = record.get('id')
        fields = record.get('fields', {})
        
        logger.info(f"Traitement de l'enregistrement {record_id}")
        
        # Vérifier d'abord si l'enregistrement est déjà complètement synchronisé
        is_fully_synced = fields.get(AIRTABLE_SYNCED_COLUMN, False)
        if is_fully_synced:
            logger.info(f"L'enregistrement {record_id} est déjà entièrement synchronisé, passage au suivant")
            continue
        
        # Variables pour suivre l'état de synchronisation
        all_files_synced = True
        has_attachments = False
        processed_this_run = False
        
        # Traiter toutes les colonnes de facture pour cet enregistrement
        for file_column in AIRTABLE_INVOICE_FILE_COLUMNS:
            # Vérifier si cette colonne contient un fichier
            attachments = fields.get(file_column, [])
            
            if not attachments:
                logger.debug(f"Pas de pièce jointe dans la colonne {file_column}")
                continue
                
            has_attachments = True
            
            # Vérifier si la facture est déjà synchronisée
            sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(file_column)
            is_synced = fields.get(sync_column, False) if sync_column else False
            
            if is_synced:
                logger.debug(f"Facture dans {file_column} déjà synchronisée")
                continue
                
            # Si on arrive ici, c'est qu'on a une facture non synchronisée
            all_files_synced = False
            
            logger.info(f"Traitement de la facture non synchronisée dans la colonne {file_column}")
                
            try:
                # Extraire les données minimales de la facture
                invoice_data = airtable.get_invoice_data(record, file_column)
                
                if not invoice_data:
                    logger.warning(f"Données de facture invalides pour l'enregistrement {record_id}, colonne {file_column}")
                    error_count += 1
                    continue
                    
                # Télécharger le fichier PDF
                pdf_path, original_filename = airtable.download_invoice_file(record, file_column)
                
                if not pdf_path:
                    logger.warning(f"Impossible de télécharger le fichier PDF depuis {file_column} pour l'enregistrement {record_id}")
                    error_count += 1
                    continue
                    
                # Envoyer par email à l'OCR Sellsy
                logger.info(f"Envoi du PDF {pdf_path} par email vers l'OCR Sellsy")
                email_result = email_client.send_invoice_to_ocr(invoice_data, pdf_path, original_filename)
                
                if not email_result:
                    logger.error(f"Échec de l'envoi par email à l'OCR pour la facture dans {file_column}, enregistrement {record_id}")
                    error_count += 1
                    continue
                    
                # Extraire l'ID de suivi du résultat
                sellsy_id = None
                if isinstance(email_result, dict):
                    # Essayer de récupérer l'ID selon la structure définie
                    if "data" in email_result and "id" in email_result["data"]:
                        sellsy_id = email_result["data"]["id"]
                    elif "id" in email_result:
                        sellsy_id = email_result["id"]
                
                # Marquer cette facture spécifique comme synchronisée dans Airtable
                if airtable.mark_file_as_synchronized(record_id, file_column, sellsy_id):
                    logger.info(f"Statut de synchronisation mis à jour avec succès pour {file_column}")
                    processed_this_run = True
                    success_count += 1
                else:
                    logger.warning(f"Échec de la mise à jour du statut de synchronisation pour {file_column}")
                    error_count += 1
                
                # Pause courte pour éviter de saturer les APIs/serveurs email
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Erreur lors du traitement de la facture dans {file_column}, enregistrement {record_id}: {e}")
                error_count += 1
                all_files_synced = False
        
        # Si on a traité au moins une facture dans cette exécution, 
        # vérifier si toutes les factures sont maintenant synchronisées
        if processed_this_run and has_attachments:
            # Récupérer l'enregistrement à jour pour vérifier le statut actuel
            updated_record = airtable.table.get(record_id)
            if updated_record:
                updated_fields = updated_record.get('fields', {})
                
                # Revérifier toutes les colonnes
                all_synced_now = True
                for column in AIRTABLE_INVOICE_FILE_COLUMNS:
                    attachments = updated_fields.get(column, [])
                    if attachments:
                        sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
                        is_synced = updated_fields.get(sync_column, False) if sync_column else False
                        if not is_synced:
                            all_synced_now = False
                            break
                
                # Si toutes les factures sont synchronisées, mettre à jour le statut global
                if all_synced_now:
                    logger.info(f"Toutes les factures sont maintenant synchronisées pour l'enregistrement {record_id}")
                    current_global_status = updated_fields.get(AIRTABLE_SYNCED_COLUMN, False)
                    
                    if not current_global_status:
                        if airtable.table.update(record_id, {AIRTABLE_SYNCED_COLUMN: True}):
                            logger.info(f"Statut global de synchronisation mis à jour à TRUE pour {record_id}")
                        else:
                            logger.warning(f"Échec de la mise à jour du statut global pour {record_id}")
    
    # Résumé de la synchronisation
    logger.info(f"Synchronisation terminée: {success_count} factures envoyées par email, {error_count} erreurs")

if __name__ == "__main__":
    try:
        sync_invoices_to_sellsy()
    except Exception as e:
        logger.critical(f"Erreur critique lors de la synchronisation: {e}")
        exit(1)

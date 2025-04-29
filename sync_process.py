"""
Script principal simplifié pour synchroniser les factures fournisseurs d'Airtable vers Sellsy par email
Version optimisée qui se concentre uniquement sur les factures individuelles
"""
import os
import logging
import time
from airtable_api import AirtableAPI
from email_sender import EmailSender
from config import BATCH_SIZE, AIRTABLE_INVOICE_FILE_COLUMNS, AIRTABLE_SYNC_STATUS_COLUMNS

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sync_process")

def sync_invoices_to_sellsy():
    """
    Version simplifiée qui ignore le statut global et se concentre uniquement sur les factures individuelles
    Traite toutes les factures non synchronisées indépendamment
    """
    logger.info("Démarrage de la synchronisation Airtable -> Sellsy (via email OCR) - Version simplifiée")
    
    # Initialiser les clients API
    airtable = AirtableAPI()
    email_client = EmailSender()
    
    # Récupérer tous les enregistrements qui ont au moins une facture
    # La méthode existante get_unsynchronized_invoices() reste compatible
    all_records = airtable.get_unsynchronized_invoices(limit=BATCH_SIZE)
    
    if not all_records:
        logger.info("Aucune facture à synchroniser")
        return
        
    logger.info(f"Traitement de {len(all_records)} enregistrements potentiels")
    
    # Compteurs pour le suivi
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    # Traiter chaque enregistrement
    for record in all_records:
        record_id = record.get('id')
        fields = record.get('fields', {})
        
        logger.info(f"Traitement de l'enregistrement {record_id}")
        
        # Traiter toutes les colonnes de facture pour cet enregistrement
        for file_column in AIRTABLE_INVOICE_FILE_COLUMNS:
            # Vérifier si cette colonne contient un fichier
            attachments = fields.get(file_column, [])
            
            if not attachments:
                logger.debug(f"Pas de pièce jointe dans la colonne {file_column}")
                continue
                
            # Vérifier si la facture est déjà synchronisée
            sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(file_column)
            is_synced = fields.get(sync_column, False) if sync_column else False
            
            if is_synced:
                logger.debug(f"Facture dans {file_column} déjà synchronisée, ignorée")
                skipped_count += 1
                continue
                
            # Si on arrive ici, c'est qu'on a une facture à traiter
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
                # Utiliser la méthode simplifiée qui met à jour uniquement le statut de la facture
                if airtable.mark_file_as_synchronized(record_id, file_column, sellsy_id):
                    logger.info(f"Facture dans {file_column} marquée comme synchronisée avec succès")
                    success_count += 1
                else:
                    logger.warning(f"Échec de la mise à jour du statut de synchronisation pour {file_column}")
                    error_count += 1
                
                # Pause courte pour éviter de saturer les APIs/serveurs email
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Erreur lors du traitement de la facture dans {file_column}, enregistrement {record_id}: {e}")
                error_count += 1
    
    # Résumé de la synchronisation
    logger.info(f"Synchronisation terminée: {success_count} factures envoyées, {skipped_count} factures déjà synchronisées, {error_count} erreurs")

if __name__ == "__main__":
    try:
        sync_invoices_to_sellsy()
    except Exception as e:
        logger.critical(f"Erreur critique lors de la synchronisation: {e}")
        exit(1)

"""
Script principal pour synchroniser les factures fournisseurs d'Airtable vers Sellsy par email
"""
import os
import logging
import time
from airtable_api import AirtableAPI
from email_sender import EmailSender
from config import BATCH_SIZE

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sync_process")

def sync_invoices_to_sellsy():
    """
    Synchronise les factures fournisseurs d'Airtable vers Sellsy via email OCR
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
        
        # Trouver la prochaine colonne de facture non synchronisée
        file_column = airtable.get_next_unsynchronized_file(record)
        
        if not file_column:
            logger.warning(f"Aucune facture non synchronisée trouvée pour l'enregistrement {record_id}")
            continue
            
        try:
            # Extraire les données minimales de la facture
            invoice_data = airtable.get_invoice_data(record, file_column)
            
            if not invoice_data:
                logger.warning(f"Données de facture invalides pour l'enregistrement {record_id}")
                error_count += 1
                continue
                
            # Télécharger le fichier PDF
            pdf_path = airtable.download_invoice_file(record, file_column)
            
            if not pdf_path:
                logger.warning(f"Impossible de télécharger le fichier PDF depuis {file_column} pour l'enregistrement {record_id}")
                error_count += 1
                continue
                
            # Envoyer par email à l'OCR Sellsy
            email_result = email_client.send_invoice_to_ocr(invoice_data, pdf_path)
            
            if not email_result:
                logger.error(f"Échec de l'envoi par email à l'OCR pour la facture dans {file_column}, enregistrement {record_id}")
                error_count += 1
                continue
                
            # Extraire l'ID de suivi du résultat (fictif dans notre cas)
            sellsy_id = None
            if isinstance(email_result, dict):
                # Essayer de récupérer l'ID selon la structure définie dans email_sender.py
                if "data" in email_result and "id" in email_result["data"]:
                    sellsy_id = email_result["data"]["id"]
                elif "id" in email_result:
                    sellsy_id = email_result["id"]
            
            # Marquer cette facture spécifique comme synchronisée dans Airtable
            airtable.mark_file_as_synchronized(record_id, file_column, sellsy_id)
            
            logger.info(f"Facture depuis la colonne {file_column} envoyée par email avec succès (ID de suivi: {sellsy_id})")
            success_count += 1
            
            # Pause courte pour éviter de saturer les APIs/serveurs email
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la facture dans {file_column}, enregistrement {record_id}: {e}")
            error_count += 1
    
    # Résumé de la synchronisation
    logger.info(f"Synchronisation terminée: {success_count} factures envoyées par email, {error_count} erreurs")

if __name__ == "__main__":
    try:
        sync_invoices_to_sellsy()
    except Exception as e:
        logger.critical(f"Erreur critique lors de la synchronisation: {e}")
        exit(1)

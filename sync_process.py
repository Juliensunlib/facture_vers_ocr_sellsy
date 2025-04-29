"""
Script principal corrigé pour synchroniser les factures fournisseurs d'Airtable vers Sellsy par email OCR
Version robuste qui gère les cas où certains champs peuvent être manquants
Optimisé pour traiter un grand nombre de factures (jusqu'à 100)
"""
import os
import logging
import time
import sys
from airtable_api import AirtableAPI  # Corrected import
from email_sender import EmailSender
from config import BATCH_SIZE, AIRTABLE_INVOICE_FILE_COLUMNS  # Corrected import

# Configuration améliorée du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("sync_log.txt")
    ]
)
logger = logging.getLogger("sync_process")

def sync_invoices_to_sellsy():
    """
    Version robuste qui se concentre uniquement sur les factures individuelles
    Gère les cas où certains champs peuvent être manquants
    Optimisée pour traiter un grand volume de factures
    """
    logger.info("====================================================")
    logger.info("Démarrage de la synchronisation Airtable -> Sellsy OCR")
    logger.info("Version corrigée pour gérer les champs manquants")
    logger.info("====================================================")
    
    # Initialiser les clients API
    airtable = AirtableAPI()  # Version corrigée qui détecte la structure de la table
    email_client = EmailSender()
    
    # Récupérer tous les enregistrements qui ont au moins une facture non synchronisée
    # Utiliser une limite plus élevée pour s'assurer de traiter toutes les factures (40+)
    all_records = airtable.get_unsynchronized_invoices(limit=BATCH_SIZE)
    
    if not all_records:
        logger.info("Aucune facture à synchroniser")
        return
        
    logger.info(f"Traitement de {len(all_records)} enregistrements contenant des factures non synchronisées")
    
    # Compteurs pour le suivi
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    # Traiter chaque enregistrement
    for record in all_records:
        record_id = record.get('id')
        
        logger.info(f"Traitement de l'enregistrement {record_id}")
        
        # Traiter toutes les colonnes de facture non synchronisées pour cet enregistrement
        for file_column in AIRTABLE_INVOICE_FILE_COLUMNS:
            try:
                # Vérifier si cette colonne contient un fichier à traiter
                # La méthode corrigée get_next_unsynchronized_file vérifie si le fichier existe et n'est pas synchronisé
                if file_column != airtable.get_next_unsynchronized_file(record):
                    continue
                    
                logger.info(f"Traitement de la facture non synchronisée dans la colonne {file_column}")
                    
                # Extraire les données minimales de la facture
                invoice_data = airtable.get_invoice_data(record, file_column)
                
                # Télécharger le fichier PDF
                pdf_path, original_filename = airtable.download_invoice_file(record, file_column)
                
                if not pdf_path:
                    logger.warning(f"Impossible de télécharger le fichier PDF depuis {file_column}")
                    error_count += 1
                    continue
                    
                # Envoyer par email à l'OCR Sellsy
                logger.info(f"Envoi du PDF {original_filename} par email vers l'OCR Sellsy")
                email_result = email_client.send_invoice_to_ocr(invoice_data, pdf_path, original_filename)
                
                if not email_result:
                    logger.error(f"Échec de l'envoi par email à l'OCR pour la facture dans {file_column}")
                    error_count += 1
                    continue
                    
                # Extraire l'ID de suivi du résultat
                sellsy_id = None
                if isinstance(email_result, dict):
                    if "data" in email_result and "id" in email_result["data"]:
                        sellsy_id = email_result["data"]["id"]
                    elif "id" in email_result:
                        sellsy_id = email_result["id"]
                
                # Marquer cette facture spécifique comme synchronisée dans Airtable
                if airtable.mark_file_as_synchronized(record_id, file_column, sellsy_id):
                    logger.info(f"Facture dans {file_column} marquée comme synchronisée avec succès")
                    success_count += 1
                else:
                    logger.warning(f"Échec de la mise à jour du statut de synchronisation pour {file_column}")
                    error_count += 1
                
                # Pause courte pour éviter de saturer les APIs
                time.sleep(1)
            
            except Exception as e:
                logger.error(f"Erreur lors du traitement de la facture dans {file_column}: {e}")
                error_count += 1
        
        # Ajoutons une pause plus courte entre les enregistrements pour réduire la charge
        time.sleep(0.5)
    
    # Résumé de la synchronisation
    logger.info("====================================================")
    logger.info(f"Synchronisation terminée:")
    logger.info(f"  - {success_count} factures envoyées avec succès")
    logger.info(f"  - {skipped_count} factures déjà synchronisées")
    logger.info(f"  - {error_count} erreurs rencontrées")
    logger.info("====================================================")

if __name__ == "__main__":
    try:
        sync_invoices_to_sellsy()
    except Exception as e:
        logger.critical(f"Erreur critique lors de la synchronisation: {e}")
        exit(1)

"""
Script principal pour synchroniser les factures fournisseurs d'Airtable vers Sellsy
"""
import os
import logging
import time
from airtable_api import AirtableAPI
from sellsy_api import SellsyAPIV2
from config import BATCH_SIZE

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sync_process")

def sync_invoices_to_sellsy():
    """
    Synchronise les factures fournisseurs d'Airtable vers Sellsy
    """
    logger.info("Démarrage de la synchronisation Airtable -> Sellsy")
    
    # Initialiser les clients API
    airtable = AirtableAPI()
    sellsy = SellsyAPIV2()
    
    # Récupérer les factures non synchronisées créées aujourd'hui
    unsync_invoices = airtable.get_unsynchronized_invoices(limit=BATCH_SIZE)
    
    if not unsync_invoices:
        logger.info("Aucune facture à synchroniser")
        return
        
    logger.info(f"Traitement de {len(unsync_invoices)} factures")
    
    # Compteurs pour le suivi
    success_count = 0
    error_count = 0
    
    # Traiter chaque facture
    for record in unsync_invoices:
        record_id = record.get('id')
        try:
            # Extraire les données minimales de la facture
            invoice_data = airtable.get_invoice_data(record)
            
            if not invoice_data:
                logger.warning(f"Données de facture invalides pour l'enregistrement {record_id}")
                error_count += 1
                continue
                
            # Télécharger le fichier PDF et récupérer la colonne source
            pdf_path, file_column = airtable.download_invoice_file(record)
            
            if not pdf_path:
                logger.warning(f"Impossible de télécharger le fichier PDF pour l'enregistrement {record_id}")
                error_count += 1
                continue
                
            # Mettre à jour le chemin du fichier dans les données
            invoice_data["file_path"] = pdf_path
            
            # Envoyer à l'OCR Sellsy - sans métadonnées précises, l'OCR fera le travail d'extraction
            ocr_result = sellsy.send_invoice_to_ocr(invoice_data, pdf_path)
            
            if not ocr_result:
                logger.error(f"Échec de l'envoi à l'OCR pour l'enregistrement {record_id}")
                error_count += 1
                continue
                
            # Extraire l'ID Sellsy du résultat OCR
            sellsy_id = None
            if isinstance(ocr_result, dict):
                # Essayer de récupérer l'ID selon différentes structures possibles
                if "data" in ocr_result and "id" in ocr_result["data"]:
                    sellsy_id = ocr_result["data"]["id"]
                elif "id" in ocr_result:
                    sellsy_id = ocr_result["id"]
                elif "docId" in ocr_result:
                    sellsy_id = ocr_result["docId"]
            
            # Marquer comme synchronisé dans Airtable avec la colonne source
            airtable.mark_as_synchronized(record_id, sellsy_id, file_column)
            
            logger.info(f"Facture depuis la colonne {file_column} synchronisée avec succès (Sellsy ID: {sellsy_id})")
            success_count += 1
            
            # Pause courte pour éviter de saturer les API
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement de l'enregistrement {record_id}: {e}")
            error_count += 1
    
    # Résumé de la synchronisation
    logger.info(f"Synchronisation terminée: {success_count} factures synchronisées, {error_count} erreurs")

if __name__ == "__main__":
    try:
        sync_invoices_to_sellsy()
    except Exception as e:
        logger.critical(f"Erreur critique lors de la synchronisation: {e}")
        exit(1)

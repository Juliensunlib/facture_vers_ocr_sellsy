"""
Script principal pour synchroniser les factures fournisseurs d'Airtable vers Sellsy par email
"""
import os
import logging
import time
import sys
from airtable_api import AirtableAPI
from email_sender import EmailSender
from config import BATCH_SIZE, AIRTABLE_INVOICE_FILE_COLUMNS, AIRTABLE_SYNC_STATUS_COLUMNS, AIRTABLE_SYNCED_COLUMN

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sync_process")

def sync_invoices_to_sellsy(limit=None):
    """
    Synchronise les factures fournisseurs d'Airtable vers Sellsy via email OCR
    Logique améliorée :
    1. Vérification du statut global de synchronisation
    2. Traitement des factures non synchronisées uniquement
    3. Mise à jour du statut global lorsque toutes les factures sont synchronisées
    
    Args:
        limit (int, optional): Nombre maximum d'enregistrements à traiter
    """
    logger.info("Démarrage de la synchronisation Airtable -> Sellsy (via email OCR)")
    
    # Initialiser les clients API
    airtable = AirtableAPI()
    email_client = EmailSender()
    
    # Récupérer les enregistrements avec des factures non synchronisées
    batch_size = limit if limit else BATCH_SIZE
    unsync_records = airtable.get_unsynchronized_invoices(limit=batch_size)
    
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

def reset_sync_status(record_id, file_column=None):
    """
    Réinitialise le statut de synchronisation pour permettre une nouvelle synchronisation
    
    Args:
        record_id (str): ID de l'enregistrement Airtable
        file_column (str, optional): Colonne spécifique à réinitialiser, ou None pour toutes
    
    Returns:
        bool: True si la réinitialisation a réussi
    """
    try:
        airtable = AirtableAPI()
        
        if file_column:
            # Réinitialiser une colonne spécifique
            sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(file_column)
            if not sync_column:
                logger.error(f"Colonne de synchronisation non trouvée pour {file_column}")
                return False
                
            # Mettre à jour uniquement cette colonne
            update_data = {sync_column: False}
            result = airtable.table.update(record_id, update_data)
            
            # Mettre également à jour le statut global si nécessaire
            airtable.set_global_sync_status(record_id, False)
            
            logger.info(f"Statut de synchronisation réinitialisé pour {file_column} dans l'enregistrement {record_id}")
            return True
            
        else:
            # Réinitialiser toutes les colonnes
            update_data = {AIRTABLE_SYNCED_COLUMN: False}
            
            for column in AIRTABLE_INVOICE_FILE_COLUMNS:
                sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
                if sync_column:
                    update_data[sync_column] = False
            
            result = airtable.table.update(record_id, update_data)
            logger.info(f"Tous les statuts de synchronisation réinitialisés pour l'enregistrement {record_id}")
            return True
            
    except Exception as e:
        logger.error(f"Erreur lors de la réinitialisation du statut: {e}")
        return False

def list_sync_status(record_id=None, limit=10):
    """
    Affiche le statut de synchronisation des enregistrements
    
    Args:
        record_id (str, optional): ID d'un enregistrement spécifique
        limit (int, optional): Nombre maximum d'enregistrements à afficher
    """
    try:
        airtable = AirtableAPI()
        
        if record_id:
            # Afficher un enregistrement spécifique
            statuses = airtable.get_all_file_statuses(record_id)
            has_attachments, all_synced = airtable.check_global_sync_status(record_id)
            
            print(f"\nStatut de synchronisation pour l'enregistrement {record_id}:")
            print(f"Statut global: {'Synchronisé' if all_synced else 'Non synchronisé'}")
            
            for column, status in statuses.items():
                if status['has_file']:
                    sync_status = "Synchronisé" if status['is_synced'] else "Non synchronisé"
                    print(f"  {column}: {sync_status} - {status['file_name']}")
                    
        else:
            # Afficher les enregistrements non synchronisés
            records = airtable.get_unsynchronized_invoices(limit=limit)
            
            print(f"\n{len(records)} enregistrements avec des factures non synchronisées:")
            
            for record in records:
                record_id = record.get('id')
                fields = record.get('fields', {})
                
                subscriber_id = fields.get(airtable.AIRTABLE_SUBSCRIBER_ID_COLUMN, "")
                first_name = fields.get(airtable.AIRTABLE_SUBSCRIBER_FIRSTNAME_COLUMN, "")
                last_name = fields.get(airtable.AIRTABLE_SUBSCRIBER_LASTNAME_COLUMN, "")
                
                print(f"\nEnregistrement {record_id} - {first_name} {last_name} ({subscriber_id}):")
                
                for column in AIRTABLE_INVOICE_FILE_COLUMNS:
                    attachments = fields.get(column, [])
                    
                    if attachments:
                        sync_column = AIRTABLE_SYNC_STATUS_COLUMNS.get(column)
                        is_synced = fields.get(sync_column, False) if sync_column else False
                        
                        sync_status = "Synchronisé" if is_synced else "Non synchronisé"
                        print(f"  {column}: {sync_status} - {attachments[0].get('filename')}")
    
    except Exception as e:
        logger.error(f"Erreur lors de l'affichage des statuts: {e}")

if __name__ == "__main__":
    try:
        # Récupérer les arguments de la ligne de commande
        if len(sys.argv) > 1:
            cmd = sys.argv[1]
            
            if cmd == "sync":
                # Synchroniser avec limite optionnelle
                limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
                sync_invoices_to_sellsy(limit)
                
            elif cmd == "reset":
                # Réinitialiser le statut
                if len(sys.argv) > 2:
                    record_id = sys.argv[2]
                    
                    if len(sys.argv) > 3:
                        # Réinitialiser une colonne spécifique
                        file_column = sys.argv[3]
                        reset_sync_status(record_id, file_column)
                    else:
                        # Réinitialiser toutes les colonnes
                        reset_sync_status(record_id)
                else:
                    print("Erreur: ID d'enregistrement requis pour la réinitialisation")
                    
            elif cmd == "status":
                # Afficher le statut
                if len(sys.argv) > 2:
                    record_id = sys.argv[2]
                    list_sync_status(record_id)
                else:
                    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
                    list_sync_status(limit=limit)
                    
            else:
                # Commande inconnue
                print(f"Commande inconnue: {cmd}")
                print("Commandes disponibles: sync, reset, status")
        else:
            # Exécution par défaut
            sync_invoices_to_sellsy()
            
    except Exception as e:
        logger.critical(f"Erreur critique lors de la synchronisation: {e}")
        exit(1)

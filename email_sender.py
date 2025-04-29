"""
Module pour envoyer les factures à l'OCR Sellsy par email
"""
import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formatdate
from email import encoders
from config import (
    EMAIL_HOST,
    EMAIL_PORT,
    EMAIL_USER,
    EMAIL_PASSWORD,
    EMAIL_FROM,
    EMAIL_OCR_TO
)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("email_sender")

class EmailSender:
    def __init__(self):
        """Initialise le client d'envoi d'email"""
        self.host = EMAIL_HOST
        self.port = EMAIL_PORT
        self.user = EMAIL_USER
        self.password = EMAIL_PASSWORD
        self.from_addr = EMAIL_FROM
        self.to_addr = EMAIL_OCR_TO
        
        logger.info("Client d'envoi d'email initialisé")
        
    def send_invoice_to_ocr(self, invoice_data, file_path, original_filename=None):
        """
        Envoie une facture fournisseur à l'OCR de Sellsy par email
        
        Args:
            invoice_data (dict): Données minimales de la facture
            file_path (str): Chemin vers le fichier PDF de la facture
            original_filename (str, optional): Nom original du fichier si disponible
            
        Returns:
            dict: Informations sur la facture envoyée, ou None en cas d'échec
        """
        if not os.path.exists(file_path):
            logger.error(f"Fichier non trouvé: {file_path}")
            return None
            
        try:
            # Créer le message email
            msg = MIMEMultipart()
            msg['From'] = self.from_addr
            msg['To'] = self.to_addr
            msg['Date'] = formatdate(localtime=True)
            
            # Récupérer les informations d'abonné
            subscriber_id = invoice_data.get("subscriber_id", "")
            record_id = invoice_data.get("record_id", "")
            first_name = invoice_data.get("first_name", "")
            last_name = invoice_data.get("last_name", "")
            
            # Créer le sujet avec référence à l'ID Airtable pour le suivi
            subject = f"Facture fournisseur pour traitement OCR - Ref:{record_id}"
            if subscriber_id:
                subject += f" - Abonné:{subscriber_id}"
                
            msg['Subject'] = subject
            
            # Corps du message
            body = "Facture fournisseur à traiter par OCR Sellsy\n"
            body += f"ID Airtable: {record_id}\n"
            if subscriber_id:
                body += f"ID Abonné: {subscriber_id}\n"
            if first_name or last_name:
                body += f"Abonné: {first_name} {last_name}\n"
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Créer un nom de fichier personnalisé incluant nom et prénom si disponibles
            base_filename = os.path.basename(file_path)
            _, ext = os.path.splitext(base_filename)
            
            if original_filename:
                base_filename = original_filename
            
            # Nouveau nom de fichier avec nom et prénom
            if first_name and last_name:
                custom_filename = f"{last_name}_{first_name}_facture{ext}"
            elif last_name:
                custom_filename = f"{last_name}_facture{ext}"
            elif first_name:
                custom_filename = f"{first_name}_facture{ext}"
            else:
                # Si ni nom ni prénom n'est disponible, utiliser l'ID
                custom_filename = f"facture_{subscriber_id or record_id}{ext}"
                
            logger.info(f"Nom de fichier personnalisé: {custom_filename}")
            
            # Joindre le fichier PDF
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'pdf')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 
                               f'attachment; filename="{custom_filename}"')
                msg.attach(part)
                
            # Connexion au serveur SMTP et envoi
            with smtplib.SMTP(self.host, self.port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(self.user, self.password)
                smtp.send_message(msg)
                
            logger.info(f"Facture envoyée avec succès par email à {self.to_addr}")
            
            # Retourner un objet similaire à celui attendu par l'ancien code
            # pour maintenir la compatibilité
            result = {
                "status": "success",
                "data": {
                    "id": f"email-{record_id}",  # ID fictif pour le suivi
                    "method": "email",
                    "recipient": self.to_addr,
                    "filename": custom_filename
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la facture par email: {e}")
            return None
        finally:
            # Nettoyage du fichier temporaire
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                    logger.debug(f"Fichier temporaire supprimé: {file_path}")
                except Exception as e:
                    logger.warning(f"Impossible de supprimer le fichier temporaire {file_path}: {e}")

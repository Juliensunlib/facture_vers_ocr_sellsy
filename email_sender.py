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
        
    def send_invoice_to_ocr(self, invoice_data, file_path):
        """
        Envoie une facture fournisseur à l'OCR de Sellsy par email
        
        Args:
            invoice_data (dict): Données minimales de la facture (peut être vide)
            file_path (str): Chemin vers le fichier PDF de la facture
            
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
            
            # Identifier l'abonné si disponible
            subscriber_id = invoice_data.get("subscriber_id", "")
            record_id = invoice_data.get("record_id", "")
            
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
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Joindre le fichier PDF
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'pdf')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 
                               f'attachment; filename="{os.path.basename(file_path)}"')
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
                    "recipient": self.to_addr
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

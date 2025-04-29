"""
Client pour l'API Sellsy V2 - Envoi des factures fournisseurs vers l'OCR
"""
import requests
import logging
import os
import json
import time
from config import SELLSY_CLIENT_ID, SELLSY_CLIENT_SECRET

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sellsy_api")

class SellsyAPIV2:
    def __init__(self):
        """Initialise la connexion à l'API Sellsy V2"""
        self.client_id = SELLSY_CLIENT_ID
        self.client_secret = SELLSY_CLIENT_SECRET
        self.access_token = None
        self.token_expires_at = 0
        self.base_url = "https://api.sellsy.com/v2"
        
        # Authentification initiale
        self._authenticate()
        
        logger.info("Client API Sellsy V2 initialisé")

    def _authenticate(self):
        """
        Obtient un token d'accès OAuth2 pour l'API Sellsy V2
        """
        # Vérifier si le token est encore valide
        if self.access_token and time.time() < self.token_expires_at - 60:
            return
            
        try:
            auth_url = "https://login.sellsy.com/oauth2/access-tokens"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            
            response = requests.post(auth_url, headers=headers, data=data)
            response.raise_for_status()
            
            auth_data = response.json()
            self.access_token = auth_data.get("access_token")
            # Calculer l'expiration du token (généralement 1 heure)
            expires_in = auth_data.get("expires_in", 3600)
            self.token_expires_at = time.time() + expires_in
            
            logger.info(f"Authentification Sellsy réussie, token valide pour {expires_in} secondes")
        except Exception as e:
            logger.error(f"Erreur d'authentification Sellsy: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Détails: {e.response.text}")
            self.access_token = None

    def _make_request(self, method, endpoint, data=None, files=None):
        """
        Effectue une requête à l'API Sellsy avec authentification
        
        Args:
            method (str): Méthode HTTP (GET, POST, PUT, etc.)
            endpoint (str): Point de terminaison API
            data (dict, optional): Données à envoyer
            files (dict, optional): Fichiers à envoyer
            
        Returns:
            dict: Réponse JSON de l'API
        """
        self._authenticate()  # S'assurer que le token est valide
        
        if not self.access_token:
            logger.error("Impossible de faire une requête : pas de token d'accès")
            return None
            
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        
        # Pour les requêtes avec fichiers, ne pas définir Content-Type
        if not files:
            headers["Content-Type"] = "application/json"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=data)
            elif method.upper() == "POST":
                if files:
                    # Pour les requêtes avec fichiers, envoyer data comme form-data
                    response = requests.post(url, headers=headers, data=data, files=files)
                else:
                    # Pour les requêtes JSON standard
                    response = requests.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                logger.error(f"Méthode HTTP non supportée: {method}")
                return None
                
            response.raise_for_status()
            
            # Certains endpoints retournent un corps vide
            if response.content:
                return response.json()
            return {"status": "success"}
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Erreur HTTP lors de la requête Sellsy {method} {endpoint}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Détails: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la requête Sellsy {method} {endpoint}: {e}")
            return None

    def send_invoice_to_ocr(self, invoice_data, file_path):
        """
        Envoie une facture fournisseur à l'OCR de Sellsy sans métadonnées précises
        
        Args:
            invoice_data (dict): Données minimales de la facture (peut être vide)
            file_path (str): Chemin vers le fichier PDF de la facture
            
        Returns:
            dict: Informations sur la facture créée, ou None en cas d'échec
        """
        if not os.path.exists(file_path):
            logger.error(f"Fichier non trouvé: {file_path}")
            return None
            
        try:
            # Préparer les données minimales pour l'OCR
            # Laisser vide pour que l'OCR détecte automatiquement les informations
            form_data = {}
            
            # Préparer le fichier
            with open(file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(file_path), f, 'application/pdf')
                }
                
                # CORRECTION: Utiliser le bon endpoint pour l'OCR des factures fournisseurs
                # D'après la documentation Sellsy V2, l'endpoint correct est:
                logger.info(f"Envoi de la facture vers l'OCR Sellsy (détection automatique)")
                
                # Essayer d'abord avec l'endpoint pour les factures d'achat
                endpoint = "ocr/pur-invoice"
                result = self._make_request("POST", endpoint, data=form_data, files=files)
                
                if not result:
                    # Si échec, essayer un endpoint alternatif
                    logger.warning(f"Échec avec l'endpoint {endpoint}, tentative avec un endpoint alternatif")
                    
                    # Réouvrir le fichier car il a été consommé
                    f.seek(0)
                    
                    # Tenter avec un autre endpoint possible
                    endpoint = "purchases/bills/parseFile"
                    result = self._make_request("POST", endpoint, data=form_data, files=files)
                
                if result:
                    logger.info(f"Facture envoyée avec succès à l'OCR via {endpoint}: {json.dumps(result)[:200]}...")
                    return result
                else:
                    logger.error("Échec de l'envoi à l'OCR Sellsy avec tous les endpoints tentés")
                    return None
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la facture à l'OCR: {e}")
            return None
        finally:
            # Nettoyage du fichier temporaire
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                    logger.debug(f"Fichier temporaire supprimé: {file_path}")
                except Exception as e:
                    logger.warning(f"Impossible de supprimer le fichier temporaire {file_path}: {e}")

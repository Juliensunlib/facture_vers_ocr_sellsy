# Synchronisation Airtable vers Sellsy OCR par Email

Ce projet permet de synchroniser automatiquement les factures fournisseurs depuis Airtable vers le système OCR de Sellsy via email.

## Fonctionnalités

- Récupération des factures depuis trois colonnes Airtable : 
  - "Facture 1 (from Documents Abonnés 3)"
  - "Facture 2 (from Documents Abonnés 3)"
  - "Facture 3 (from Documents Abonnés 3)"
- Envoi des fichiers PDF par email vers l'OCR de Sellsy pour traitement automatique
- Synchronisation uniquement des nouveaux enregistrements
- Prévention des envois en double grâce au marquage des factures synchronisées
- Exécution automatique toutes les heures via GitHub Actions
- Possibilité de lancement manuel

## Configuration

### Variables d'environnement requises

Configurez ces variables d'environnement dans les secrets GitHub :

- `AIRTABLE_API_KEY` : Clé API Airtable
- `AIRTABLE_BASE_ID` : ID de la base Airtable
- `AIRTABLE_TABLE_NAME` : Nom de la table Airtable contenant les factures
- `EMAIL_HOST` : Serveur SMTP (ex: smtp.gmail.com)
- `EMAIL_PORT` : Port SMTP (ex: 587 pour TLS)
- `EMAIL_USER` : Adresse email d'expédition (dsi@sunlib.fr)
- `EMAIL_PASSWORD` : Mot de passe email ou token d'application
- `EMAIL_FROM` : Adresse email d'expédition (identique à EMAIL_USER)
- `EMAIL_OCR_TO` : Adresse email OCR Sellsy (ocr.200978@sellsy.net)

### Configuration d'Airtable

Assurez-vous que votre table Airtable contient :
- Les trois colonnes de fichiers PDF
- Une colonne "Synchronisé_Sellsy" (booléen)
- Une colonne "ID_Sellsy" (texte) - Contient l'identifiant de l'abonné
- Des colonnes pour les statuts de synchronisation de chaque facture (voir config.py)
- Une colonne "Created_Time" (date de création automatique)

## Utilisation

La synchronisation s'exécute automatiquement toutes les heures via GitHub Actions.

Pour lancer manuellement la synchronisation :
1. Allez dans l'onglet "Actions" du dépôt GitHub
2. Sélectionnez le workflow "Sync Airtable invoices to Sellsy by Email"
3. Cliquez sur "Run workflow"

## Fonctionnement

1. Le script récupère les enregistrements qui n'ont pas encore été synchronisés
2. Pour chaque enregistrement, il télécharge le premier fichier PDF trouvé dans l'une des trois colonnes
3. Le fichier est envoyé par email à l'adresse OCR de Sellsy (ocr.200978@sellsy.net) depuis l'adresse configurée (dsi@sunlib.fr)
4. L'enregistrement est marqué comme synchronisé dans Airtable avec un ID de suivi
5. La facture sera traitée automatiquement par l'OCR de Sellsy

## Développement

1. Clonez ce dépôt
2. Installez les dépendances : `pip install -r requirements.txt`
3. Créez un fichier `.env` avec les variables d'environnement requises
4. Exécutez le script : `python sync_process.py`

## Notes importantes

- L'envoi par email est utilisé au lieu de l'API car l'OCR Sellsy est accessible via cette méthode.
- Assurez-vous que les identifiants email sont correctement configurés et que le compte a les autorisations nécessaires pour envoyer des emails.
- L'adresse email d'expédition (dsi@sunlib.fr) doit être autorisée dans le système OCR de Sellsy.

# Synchronisation Airtable vers Sellsy OCR

Ce projet permet de synchroniser automatiquement les factures fournisseurs depuis Airtable vers le système OCR de Sellsy.

## Fonctionnalités

- Récupération des factures depuis trois colonnes Airtable : 
  - "Facture 1 (from Documents Abonnés 3)"
  - "Facture 2 (from Documents Abonnés 3)"
  - "Facture 3 (from Documents Abonnés 3)"
- Envoi des fichiers PDF vers l'OCR de Sellsy pour traitement automatique
- Synchronisation uniquement des nouveaux enregistrements (créés à partir d'aujourd'hui)
- Prévention des envois en double grâce au marquage des factures synchronisées
- Exécution automatique toutes les heures via GitHub Actions
- Possibilité de lancement manuel

## Configuration

### Variables d'environnement requises

Configurez ces variables d'environnement dans les secrets GitHub :

- `AIRTABLE_API_KEY` : Clé API Airtable
- `AIRTABLE_BASE_ID` : ID de la base Airtable
- `AIRTABLE_TABLE_NAME` : Nom de la table Airtable contenant les factures
- `SELLSY_CLIENT_ID` : ID client Sellsy API V2
- `SELLSY_CLIENT_SECRET` : Secret client Sellsy API V2

### Configuration d'Airtable

Assurez-vous que votre table Airtable contient :
- Les trois colonnes de fichiers PDF
- Une colonne "Synchronisé_Sellsy" (booléen)
- Une colonne "ID_Sellsy" (texte)
- Une colonne "Created_Time" (date de création automatique)

## Utilisation

La synchronisation s'exécute automatiquement toutes les heures via GitHub Actions.

Pour lancer manuellement la synchronisation :
1. Allez dans l'onglet "Actions" du dépôt GitHub
2. Sélectionnez le workflow "Sync Airtable invoices to Sellsy"
3. Cliquez sur "Run workflow"

## Fonctionnement

1. Le script récupère uniquement les enregistrements créés à partir d'aujourd'hui qui n'ont pas encore été synchronisés
2. Pour chaque enregistrement, il télécharge le premier fichier PDF trouvé dans l'une des trois colonnes
3. Le fichier est envoyé vers l'OCR de Sellsy qui détecte automatiquement les informations (date, référence, fournisseur)
4. L'enregistrement est marqué comme synchronisé dans Airtable avec l'ID Sellsy
5. La facture reste en attente de validation dans Sellsy

## Développement

1. Clonez ce dépôt
2. Installez les dépendances : `pip install -r requirements.txt`
3. Créez un fichier `.env` avec les variables d'environnement requises
4. Exécutez le script : `python sync_process.py`

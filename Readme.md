# 🏢 Système de Gestion de Station-Service

Application web Django pour la gestion complète d'une ou plusieurs stations-service : carburant, pompes, stock, finances et rapports.

## 📋 Table des matières

- [Technologies](#-technologies)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Architecture du système](#-architecture-du-système)
- [Gestion des rôles](#-gestion-des-rôles)
- [Fonctionnalités](#-fonctionnalités)
- [Règles système](#-règles-système)

---

## 🛠 Technologies

- **Framework** : Django
- **Base de données** : MySQL
- **Dépendances principales** :
  - `django` - Framework web
  - `mysqlclient` - Connecteur MySQL pour Python
  - `python-decouple` - Gestion des variables d'environnement

---

## 🚀 Installation

### Prérequis

- Python 3.8+
- MySQL 5.7+ ou 8.0+
- pip

### Étapes d'installation

1. **Cloner le projet** (si applicable)
2. **Créer un environnement virtuel** :
   ```bash
   python -m venv venv
   source venv/bin/activate  # Sur Windows: venv\Scripts\activate
   ```

3. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurer la base de données MySQL** (voir section Configuration)

5. **Appliquer les migrations** :
   ```bash
   python manage.py migrate
   ```

6. **Créer un utilisateur applicatif avec le rôle `admin` (propriétaire)** via l'interface de gestion des utilisateurs.

7. **Lancer le serveur de développement** :
   ```bash
   python manage.py runserver
   ```

---

## ⚙️ Configuration

### Base de données MySQL

Configurer les paramètres de connexion MySQL dans `settings.py` ou via les variables d'environnement :

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'nom_de_la_base',
        'USER': 'utilisateur_mysql',
        'PASSWORD': 'mot_de_passe',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

### Variables d'environnement

Utiliser `python-decouple` pour gérer les secrets via un fichier `.env` :

```
DB_NAME=station_db
DB_USER=root
DB_PASSWORD=votre_mot_de_passe
DB_HOST=localhost
DB_PORT=3306
SECRET_KEY=votre_secret_key
DEBUG=True
```

---

## 🧠 Architecture du système

Le système repose sur **4 piliers fondamentaux** :

1. **📊 Index** → Calcul automatique des ventes
2. **🛢 Stock** → Suivi en temps réel du carburant
3. **💰 Finances** → Gestion de la caisse, dépenses et versements
4. **📈 Rapports** → Analyse et prise de décision

### Flux de données

```
Index des pompes → Calcul des ventes → Mise à jour du stock
                                              ↓
                                    Gestion financière
                                              ↓
                                    Génération de rapports
```

---

## 👥 Gestion des rôles

L'application contient uniquement **2 rôles** avec des permissions distinctes :
- `admin` : propriétaire de station-service
- `manager` : gérant de station-service

### 🔐 ADMIN

L'Admin est le superviseur global du système avec accès complet.

#### Responsabilités

- ✅ Créer et gérer les stations
- ✅ Créer et gérer les gérants
- ✅ Assigner un gérant à une ou plusieurs stations
- ✅ Configurer les pompes
- ✅ Paramétrer les index de départ
- ✅ Accéder à tous les rapports globaux
- ✅ Voir toutes les dépenses et versements
- ✅ Modifier ou corriger les données si nécessaire
- ✅ Voir les statistiques globales (toutes stations)

### 👤 GÉRANT

Le Gérant est responsable d'une ou plusieurs stations assignées.

#### Responsabilités

- ✅ Se connecter à l'application
- ✅ Envoyer les index des pompes
- ✅ Envoyer le stock actuel
- ✅ Enregistrer les dépenses
- ✅ Enregistrer les versements
- ✅ Enregistrer les approvisionnements
- ✅ Consulter les rapports de sa station uniquement

---

## ⛽ Fonctionnalités

### 1. Gestion des Stations

Chaque station contient :

- **Pompes** (Essence / Gazoil)
- **Stock de carburant** (suivi automatique)
- **Caisse** (argent issu des ventes)
- **Historique des opérations** (traçabilité complète)
- **Rapports** (journaliers, mensuels, personnalisés)

> **Note** : Un gérant peut gérer plusieurs stations.

---

### 2. 🚰 Gestion des Pompes

#### 2.1 Paramétrage initial (ADMIN)

Avant la première utilisation, l'Admin doit :

- Définir la **date de début du système**
- Définir l'**index initial de chaque pompe**

⚠️ **Règle importante** : Impossible d'enregistrer un index avec une date antérieure à la dernière date enregistrée.

#### 2.2 Enregistrement des index (GÉRANT)

Le gérant doit entrer quotidiennement :

- Index pompe Essence
- Index pompe Gazoil
- Date

#### 2.3 Calcul automatique des ventes

Le système calcule automatiquement :

```
Quantité vendue = Index actuel - Index précédent
```

Cela permet de connaître :

- Vente journalière
- Vente par période
- Vente par pompe
- Vente par type de carburant

#### 2.4 Réinitialisation des pompes

- Possible uniquement par ADMIN
- L'historique est conservé

---

### 3. 🛢 Gestion du Stock

#### 3.1 Stock actuel (GÉRANT)

Le gérant envoie :

- Stock Essence (litres)
- Stock Gazoil (litres)

Le système :

- ✅ Déduit automatiquement les ventes
- ✅ Ajoute automatiquement les approvisionnements

---

### 4. 🚛 Approvisionnement

Correspond à la réception de carburant.

#### Informations à enregistrer

- Date de réception
- Produit (Essence / Gazoil)
- Quantité annoncée
- Quantité reçue
- Manquant (litres)
- Matricule du camion
- Nom du chauffeur

#### Traitement automatique

Le système :

- Met à jour le stock
- Calcule les écarts (quantité annoncée vs quantité reçue)

---

### 5. 💰 Gestion Financière

#### 5.1 Caisse

La caisse représente l'argent issu des ventes. Elle est mise à jour automatiquement.

#### 5.2 Dépenses (GÉRANT)

Informations requises :

- Montant
- Raison
- Date
- Compte de départ
- Bénéficiaire (facultatif)
- Type (classifié)

#### 5.3 Versements (GÉRANT)

Versement = transfert de la caisse vers la banque.

Informations requises :

- Montant
- Date
- Banque
- Référence
- Type (classifié)

#### 5.4 Classification

Les dépenses et versements doivent être classifiés selon les catégories suivantes :

- 💼 Salaire
- 🔧 Maintenance
- 🚚 Transport
- 🏦 Banque
- ⛽ Carburant
- 📦 Autres

---

### 6. 📊 Rapports & Statistiques

#### 🔎 Pour le Gérant

- Rapport journalier
- Rapport mensuel
- Total ventes
- Total dépenses
- Solde caisse

#### 📈 Pour l'Admin

- Rapport global toutes stations
- Comparaison entre stations
- Performance par pompe
- Écarts de stock
- Statistiques détaillées

---

## 🔒 Règles système

1. **Contrôle temporel** : Impossible d'entrer une date inférieure à la dernière date enregistrée
2. **Historisation** : Toutes les opérations sont historisées et traçables
3. **Permissions** : Seul l'Admin peut corriger ou modifier des données validées
4. **Multi-stations** : Gestion simultanée de plusieurs stations
5. **Traçabilité** : Toutes les opérations sont datées et horodatées

---

## 📝 Notes de développement

### Structure Django recommandée

```
station/
├── manage.py
├── requirements.txt
├── .env
├── station/          # Projet principal
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/         # Gestion des utilisateurs et rôles
├── stations/         # Modèle Station
├── pumps/            # Gestion des pompes et index
├── stock/            # Gestion du stock
├── supply/           # Approvisionnements
├── finance/          # Caisse, dépenses, versements
└── reports/          # Rapports et statistiques
```

### Modèles de données principaux

- `Station` - Stations-service
- `Pump` - Pompes (Essence/Gazoil)
- `PumpIndex` - Index des pompes avec dates
- `Stock` - Stock de carburant
- `Supply` - Approvisionnements
- `Expense` - Dépenses
- `Payment` - Versements
- `Sale` - Ventes (calculées automatiquement)

---

## 📞 Support

Pour toute question ou problème, veuillez contacter l'équipe de développement.

---

**Version** : 1.0.0  
**Dernière mise à jour** : 2024

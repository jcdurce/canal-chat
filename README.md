# CANAL — Chat privé éphémère

Chat WebSocket minimal. Aucun message n'est sauvegardé.

## Fichiers

```
main.py           ← serveur backend (FastAPI + WebSockets)
index.html        ← interface web (1 seul fichier, zéro dépendance)
requirements.txt  ← dépendances Python
Procfile          ← pour Railway / Render
```

## Lancer en local

```bash
pip install -r requirements.txt
uvicorn main:app --reload
# → ouvrir http://localhost:8000
```

---

## Déploiement en ligne (option A — Railway, recommandé)

**Coût : ~5 USD/mois.** Très simple, domaine inclus.

1. Créez un compte sur https://railway.app
2. Cliquez « New Project » → « Deploy from GitHub repo »
3. Poussez ces 4 fichiers dans un dépôt GitHub (github.com, compte gratuit)
4. Railway détecte automatiquement Python + Procfile
5. Dans l'onglet « Settings » → « Networking » → « Generate Domain »  
   → vous obtenez une URL du type `canal-xxx.up.railway.app`

**Nom de domaine personnalisé** (optionnel, ~15 CAD/an) :
- Achetez un `.ca` ou `.com` sur Namecheap ou Porkbun
- Dans Railway : Settings → Custom Domain → entrez votre domaine
- Chez votre registrar : ajoutez un enregistrement CNAME pointant vers Railway

---

## Déploiement en ligne (option B — Render, gratuit avec limites)

1. Compte sur https://render.com
2. « New Web Service » → connectez votre dépôt GitHub
3. Build command : `pip install -r requirements.txt`
4. Start command  : `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. URL gratuite fournie : `canal-xxx.onrender.com`

⚠ Le plan gratuit Render « endort » le serveur après 15 min d'inactivité.  
Pour un usage régulier, Railway est préférable.

---

## Utilisation

- Entrez un pseudo (sans mot de passe)
- Les utilisateurs connectés apparaissent à gauche
- Cliquez sur un nom pour ouvrir une conversation privée
- **Ctrl+Entrée** pour envoyer
- Vous pouvez coller des centaines de lignes de texte directement
- Aucun message n'est conservé après déconnexion

---

## Partage de fichiers

Chaque session de chat permet d'envoyer un fichier au destinataire ouvert, en plus du texte.

- **Bouton 📎** à côté d'Envoyer, ou **glisser-déposer** directement dans la fenêtre de conversation
- **Taille maximale : 50 Mo** par fichier
- **Tous les types de fichiers** sont acceptés
- Le fichier est gardé **uniquement en mémoire serveur** — jamais écrit sur disque
- **Téléchargement à usage unique** : dès que le destinataire clique sur « Télécharger », le fichier disparaît de la mémoire du serveur
- **Expiration automatique après 15 minutes** si le destinataire ne télécharge pas
- **Purge immédiate** si l'expéditeur ou le destinataire se déconnecte avant le téléchargement — rien ne reste en mémoire
- L'expéditeur voit une barre de progression pendant l'envoi, puis une confirmation quand le fichier a été téléchargé

Aucune configuration supplémentaire n'est requise sur Render ou Railway — la fonctionnalité fait partie du même serveur `main.py`.

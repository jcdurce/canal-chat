# Automatismes de transfert — addendum CANAL

Ce document décrit la fonctionnalité ajoutée à `index.html` du chat
**canal-chat** : deux automatismes paramétrables pour transférer, via le chat,
des fichiers préparés par **FileEncrypter** + **FileSplitter**.

Aucun changement côté backend (`main.py`) : les automatismes réutilisent les
routes existantes `/upload` et `/download/{id}`. Tout est côté client.

---

## Ce qui a été ajouté

Un bouton **⚙** dans la barre du haut ouvre un modal « Automatismes de
transfert » avec deux sections :

### ↑ Envoi automatique
- **Dossier d'envoi** : dossier local contenant les fichiers chiffrés +
  fractionnés (sortie de FileSplitter : `.partNNNN` + `.manifest`).
- **Destinataire** : un utilisateur actuellement en ligne.
- **Fréquence** : Continu · 1 min · 1 h · 2 h · 6 h · 12 h · 1 fois par jour.
- **Fichiers par cycle** : combien de fichiers (non encore envoyés) sont
  envoyés à chaque cycle (1 à 500).
- **Activer l'envoi** / **Désactiver** ; **Réinitialiser le suivi** pour tout
  renvoyer depuis le début.

À chaque cycle, l'automatisme liste le dossier, envoie les fichiers **non déjà
envoyés** (tri naturel, pour respecter l'ordre `part0000`, `part0001`…), via
`POST /upload`. Le suivi des fichiers envoyés est persisté (`localStorage`),
donc le transfert reprend là où il s'est arrêté après un rechargement.

### ↓ Réception automatique
- **Dossier de réception** : dossier local où sauvegarder les fichiers reçus.
- **Fréquence** : **Immédiat** (recommandé) · 1 min · 5 min · 10 min.
- **Activer la réception** / **Désactiver**.

À la réception d'un fichier (événement WebSocket `file`), l'automatisme
déclenche `GET /download/{id}` et écrit le contenu **directement** dans le
dossier choisi, sous le **nom d'origine** (indispensable pour que FileSplitter
puisse reconstituer ensuite).

Les boutons **📎** (envoi manuel) et **Télécharger** (réception manuelle)
restent entièrement fonctionnels.

---

## Pré-requis navigateur

L'accès à un dossier local depuis une page web nécessite l'API
**File System Access** (`showDirectoryPicker`). Supportée par :

- ✅ **Chrome** et **Edge** bureau (recommandé).
- ❌ Firefox, Safari, et le navigateur JavaFX « Navigator » (WebView).

Si l'API n'est pas disponible, le modal affiche un message clair et les
automatismes restent désactivés ; le reste du chat fonctionne normalement.

### Permission et rechargement

Au premier choix d'un dossier, le navigateur demande l'autorisation (lecture
pour l'envoi, lecture+écriture pour la réception). Les « handles » de dossier
sont persistés (`IndexedDB`), mais après un **rechargement de page**, le
navigateur exige un **clic** pour réaccorder l'accès : il suffit de rouvrir le
modal et de cliquer **« Activer l'envoi »** / **« Activer la réception »**.

---

## Workflow complet (avec FileEncrypter + FileSplitter)

**Côté expéditeur :**
1. `FileEncrypter` → chiffre le fichier texte en `.enc` (mot de passe fort).
2. `FileSplitter` → fractionne le `.enc` en fragments `.partNNNN` + un
   `.manifest`.
3. Placer tous ces fichiers dans le **dossier d'envoi** configuré.
4. Ouvrir le chat (Chrome/Edge), se connecter, cliquer **⚙**, choisir le
   dossier d'envoi, le destinataire, la fréquence, puis **Activer l'envoi**.

**Côté récepteur :**
1. Ouvrir le chat (Chrome/Edge), se connecter, cliquer **⚙**, choisir un
   **dossier de réception**, fréquence **Immédiat**, puis **Activer la
   réception**.
2. Les fragments arrivent et sont sauvegardés automatiquement au fur et à
   mesure, sous leur nom d'origine.
3. Une fois tous les fragments + le `.manifest` reçus :
   - `FileSplitter` → **Reconstituer** à partir du `.manifest` → retrouve le
     `.enc`.
   - `FileEncrypter` → **Déchiffrer** le `.enc` avec le même mot de passe →
     retrouve le texte original.

---

## Limites importantes

- **Les deux interlocuteurs doivent rester connectés** pendant le transfert.
  Le serveur garde les fichiers **en mémoire seulement 15 minutes** ; un
  fragment envoyé alors que le récepteur est hors ligne (ou sans réception
  automatique active) est **perdu**. D'où la fréquence « Immédiat »
  recommandée côté réception.
- Le découpage en lot (4300+ fichiers) est géré sans gelmer le navigateur :
  seules les **500 bulles les plus récentes** sont conservées dans le DOM
  (`MAX_VISIBLE_BUBBLES`), l'historique complet reste en mémoire interne.
- Les fichiers sont transférés **chiffrés** (par FileEncrypter) ; le chat ne
  voit que des fragments binaires indéchiffrables.
- Aucune donnée n'est écrite sur le disque du serveur (comportement d'origine
  préservé).

---

## Réglages typiques

| Objectif | Réglage |
|---|---|
| Transfert rapide (tout maintenant) | Envoi : **Continu**, lot **100**. Réception : **Immédiat**. |
| Transfert discret (goutte-à-goutte) | Envoi : **1 h**, lot **5**. Réception : **Immédiat**. |
| Lot quotidien | Envoi : **1 fois par jour**, lot **50**. Réception : **Immédiat** (le récepteur doit être en ligne à l'heure du cycle). |

> Pour 4300 fragments à 5/heure : ~36 jours. À 50/jour : ~86 jours. À 100 en
> continu : ~2 minutes.

---

## Déploiement

Remplacez le fichier `index.html` de votre dépôt `canal-chat` par la version
fournie ici. Aucune autre modification n'est nécessaire (ni `main.py`, ni
`requirements.txt`, ni le `Procfile`). Redéployez sur Render/Railway comme
d'habitude.

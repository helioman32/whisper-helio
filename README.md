# 🎤 Whisper Hélio v1.5

**Dictée vocale Windows — 100% offline, 100% gratuit**

![Version](https://img.shields.io/badge/version-1.5-green.svg)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Windows](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)]()
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)]()

<p align="center">
  <strong>Transformez votre voix en texte instantanément, sans connexion internet.</strong>
</p>

<p align="center">
  <a href="https://helioman.fr">📥 Télécharger</a> •
  <a href="https://helioman.fr">🌐 Site Web</a> •
  <a href="https://www.paypal.com/paypalme/heliostmalo">❤️ Soutenir</a>
</p>

---

## ✨ Fonctionnalités

| Fonctionnalité | Description |
|----------------|-------------|
| 🔒 **100% Offline** | Aucune donnée envoyée sur internet. Confidentialité totale. |
| ⚡ **Ultra rapide** | Transcription quasi-instantanée avec GPU NVIDIA |
| 🎯 **Précision Whisper** | Basé sur le meilleur modèle de reconnaissance vocale |
| 🌍 **Multilingue** | Français, anglais, espagnol, allemand, italien, portugais, néerlandais |
| 🎮 **Raccourcis flexibles** | Clavier F9-F12 ou boutons souris gaming |
| 🎨 **Thèmes** | Mode sombre et mode clair |
| 📝 **Macros** | Remplacement automatique de texte personnalisable |
| 📖 **Dictionnaire** | Correction des mots mal transcrits par Whisper |
| 🚀 **Actions vocales** | Ouvrir des programmes par la voix |
| 📍 **Portable** | Aucune installation requise |
| 📂 **Transcription fichier** | Glissez-déposez un fichier audio pour le transcrire |
| 🆓 **Gratuit** | Open source, sans pub, sans abonnement |

---

## 🆕 Nouveautés v1.5

### 🎤 Streaming temps réel
- **Aperçu en direct** pendant la dictée — un label flottant affiche le texte en quasi-temps-réel sous le curseur
- **Double modèle** : `tiny` (aperçu rapide) + modèle principal (transcription finale de qualité)
- Activable/désactivable dans les Paramètres
- Aucun impact sur la qualité finale

### 📤 Export multi-format
- **5 formats** : SRT, VTT, TXT horodaté, TXT brut, JSON
- Export après transcription de fichier audio
- Anti-écrasement automatique (suffixes _2, _3...)
- Encodage UTF-8 BOM pour compatibilité Windows (accents français)

### 🆕 Nouveautés v1.4b

### 📂 Transcription de fichiers audio
- **Drag-and-drop** : glissez un fichier audio sur la fenêtre pour le transcrire
- **Bouton 📂** : parcourez vos fichiers depuis l'interface
- Formats : MP3, WAV, FLAC, OGG, M4A, WMA, AAC, WEBM, OPUS, MP4
- **8.7× plus rapide** grâce au BatchedInferencePipeline GPU (batch parallèle + VAD Silero)
- Progression en pourcentage avec temps écoulé
- Fenêtre de résultat avec copie en un clic
- Anti-hallucination pour fichiers longs (musique, bruits de fond)

### ⚡ Nouveau modèle `large-v3-turbo`
- **2× plus rapide** que `large-v3`
- Qualité quasi identique
- Disponible directement dans les Paramètres

### 🎨 Fenêtre Paramètres redessinée
- Style cohérent avec la fenêtre principale (sans barre Windows)
- Barre de titre custom avec bouton ✕ et drag
- Coins arrondis, transparence identique

### 🌍 Interface française corrigée
- Tous les accents restaurés (Paramètres, Modèle, Périphérique, Prêt...)
- Traductions complètes FR / EN / DE

### 🎙️ Contrôle automatique du microphone
- Volume micro réglé à 100% automatiquement au démarrage (pycaw)
- Plus besoin de vérifier les paramètres Windows

### 🛡️ Stabilité renforcée
- **70+ bugs corrigés** par audit expert (architecture, performance, robustesse)
- Sauvegarde config atomique (`.tmp` + `os.replace`)
- Hook souris conditionnel (CPU -30% si raccourci clavier)
- VU-mètre adaptatif (80ms repos → 33ms enregistrement)
- Watchdog amélioré avec récupération automatique du verrou
- Protection anti-crash pendant la fermeture (`_safe_after`)
- Logging thread-safe, nettoyage VRAM automatique

---

## 🆕 Nouveautés v1.3

### 🎨 Interface modernisée
- Boutons ronds et ovales élégants
- Animations fluides
- Meilleure cohérence visuelle

### ⚡ Performance optimisée
- **Transcription 40% plus rapide** grâce aux paramètres Whisper optimisés
- **CPU réduit de 40%** avec le VU-mètre pré-rendu
- **Latence réduite de 250ms** sur le collage du texte

### 🛡️ Stabilité améliorée
- **220+ passes de vérification** du code
- Zéro freeze, zéro crash
- Gestion mémoire optimisée pour le mode réunion
- Meilleure gestion des erreurs (micro absent, modèle non trouvé)

### 🖱️ Support souris gaming
- Boutons pouce X1/X2 fonctionnels
- Plus de gel de souris

### 📺 Compatibilité écrans
- Support DPI haute résolution (4K, etc.)
- Fenêtre toujours visible sur multi-moniteurs

---

## 📥 Installation

### Option 1 : Exécutable (recommandé)

1. Téléchargez la [dernière version](https://helioman.fr)
2. Extrayez le ZIP dans un dossier
3. Lancez `installer.bat` (détecte/installe CUDA automatiquement)
4. Ou lancez directement `WhisperHelio.exe`
5. Au premier lancement, le modèle Whisper sera téléchargé automatiquement (~800 MB pour large-v3-turbo)

### Option 2 : Depuis les sources

```bash
# Cloner le repo
git clone https://github.com/helioman32/whisper-helio.git
cd whisper-helio

# Installer les dépendances
pip install -r requirements.txt

# Lancer
python dictee.pyw
```

---

## 📋 Configuration requise

| Composant | Minimum | Recommandé |
|-----------|---------|------------|
| **OS** | Windows 10 64-bit | Windows 11 |
| **RAM** | 8 GB | 16 GB |
| **GPU** | — (CPU possible) | NVIDIA RTX (CUDA) |
| **Stockage** | 5 GB | 10 GB |
| **Python** | 3.8+ | 3.11+ |

---

## ⌨️ Raccourcis

| Raccourci | Action |
|-----------|--------|
| `F9` (défaut) | Maintenir pour dicter, relâcher pour transcrire |
| `F10` `F11` `F12` | Raccourcis alternatifs |
| `Bouton pouce X1/X2` | Pour souris gaming |
| `⏺ Bouton vert` | Mode réunion (enregistrement continu) |
| `📂 Bouton fichier` | Ouvrir un fichier audio à transcrire |
| `⚙️ Bouton gris` | Paramètres |
| `−` | Mode compact (VU-mètre seul) |
| `✕ Bouton rouge` | Fermer |

---

## ⚙️ Paramètres

Cliquez sur l'icône ⚙️ pour accéder aux paramètres :

| Option | Valeurs | Description |
|--------|---------|-------------|
| **Thème** | Dark / Light | Apparence de l'interface |
| **Modèle** | tiny → large-v3-turbo | Précision vs vitesse |
| **Périphérique** | Auto / CUDA / CPU | Utiliser le GPU si disponible |
| **Langue dictée** | FR, EN, ES, DE, IT, PT, NL | Langue de dictée |
| **Interface** | FR, EN, DE | Langue de l'interface |
| **Raccourci** | F9-F12, mouse_x1/x2 | Touche de dictée |
| **Position** | 5 positions | Position au démarrage |

---

## 🎙 Mode Réunion

Le mode réunion est un mode d'enregistrement **continu et mains-libres**. Contrairement au mode normal (push-to-talk), il écoute en permanence, détecte automatiquement la parole, transcrit à la volée et colle le texte dans la fenêtre de votre choix.

### Activer le mode réunion

1. Placez votre curseur dans l'application cible (Word, Bloc-notes, navigateur, etc.)
2. Cliquez sur le bouton **⏺ vert** (en haut à droite de Whisper Hélio)
3. Le bouton passe au **rouge** — le mode réunion est actif

### Fonctionnement

Le mode réunion fonctionne par **cycles automatiques** :

| Étape | Description |
|-------|-------------|
| **Écoute** | Whisper Hélio détecte la présence de voix en continu |
| **Découpe** | Un segment est découpé après **1,2s de silence** ou **25s max** |
| **Transcription** | Le segment est transcrit (barre de statut orange) |
| **Collage** | Le texte est collé automatiquement dans la fenêtre active |
| **Reprise** | L'écoute reprend immédiatement pour le segment suivant |

### Arrêter le mode réunion

1. Cliquez à nouveau sur le bouton **⏺ rouge**
2. Le dernier audio en mémoire est transcrit automatiquement (rien n'est perdu)
3. Le bouton repasse au **vert** — mode normal restauré

### Conseils

- **Parlez naturellement** — les pauses entre les phrases sont respectées (seuil 1,2s)
- **Micro de qualité recommandé** — améliore significativement la transcription
- **Évitez la musique de fond** — peut déclencher des segments parasites
- **Macros et dictionnaire** — s'appliquent aussi en mode réunion
- **Gardez la fenêtre cible au premier plan** — le texte y est collé automatiquement

### Mode réunion vs Push-to-talk

| | Push-to-talk | Mode réunion |
|---|---|---|
| **Déclenchement** | Maintenir le raccourci | Clic unique sur ⏺ |
| **Durée** | Tant que le raccourci est maintenu | Illimité |
| **Découpe** | Un seul bloc | Segments automatiques |
| **Mains-libres** | ❌ | ✅ |
| **Collage** | Une fois à la fin | Continu, segment par segment |

---

## 📂 Transcription de fichiers audio

Whisper Hélio peut transcrire des fichiers audio existants, en plus de la dictée en direct.

### Utilisation

**Méthode 1 — Glisser-déposer :**
Glissez un fichier audio depuis l'Explorateur Windows directement sur la fenêtre de Whisper Hélio.

**Méthode 2 — Bouton 📂 :**
Cliquez sur le bouton 📂 dans l'interface pour parcourir et sélectionner un fichier.

### Formats supportés

`.mp3` `.wav` `.flac` `.ogg` `.m4a` `.wma` `.aac` `.webm` `.opus` `.mp4`

### Fonctionnement

1. La barre de statut affiche la **progression en pourcentage** et le temps écoulé
2. Une fois terminé, une **fenêtre de résultat** s'ouvre avec le texte complet
3. Vous pouvez **copier** le texte ou **fermer** la fenêtre
4. Les fichiers longs sont gérés avec un système anti-hallucination (découpe automatique, timeout par segment)

> **Note :** La transcription de fichier n'est pas disponible pendant un enregistrement ou en mode réunion.

---

## 🔧 Modèles Whisper

| Modèle | Taille | RAM GPU | Précision | Vitesse |
|--------|--------|---------|-----------|---------|
| `tiny` | 75 MB | 1 GB | ★★☆☆☆ | ★★★★★ |
| `base` | 150 MB | 1 GB | ★★★☆☆ | ★★★★☆ |
| `small` | 500 MB | 2 GB | ★★★★☆ | ★★★☆☆ |
| `medium` | 1.5 GB | 5 GB | ★★★★☆ | ★★☆☆☆ |
| `large-v2` | 3 GB | 10 GB | ★★★★★ | ★☆☆☆☆ |
| `large-v3` | 3 GB | 10 GB | ★★★★★ | ★☆☆☆☆ |
| `large-v3-turbo` ⭐ | 800 MB | 6 GB | ★★★★★ | ★★★☆☆ |

**Recommandation :**
- **Avec GPU NVIDIA** : `large-v3-turbo` — meilleur rapport qualité/vitesse
- **Sans GPU** : `small` ou `base` pour un bon compromis

---

## 🛠️ Dépannage

### "Aucun microphone détecté"
- Vérifiez que votre micro est branché
- Vérifiez les paramètres son de Windows
- Redémarrez l'application

### "Erreur chargement modèle"
- Vérifiez votre connexion internet (premier lancement uniquement)
- L'app utilisera automatiquement un modèle plus léger

### Transcription lente
- Passez à `large-v3-turbo` ou un modèle plus petit
- Si vous avez un GPU NVIDIA, vérifiez que CUDA est installé

### F9 ne fonctionne pas
- Essayez de lancer en mode Administrateur
- Vérifiez que le raccourci est bien F9 dans les paramètres
- Testez avec un autre raccourci (F10, F11, F12)

### Fenêtre invisible au démarrage
- Supprimez `%USERPROFILE%\whisper_helio_config.json`
- L'app redémarrera en position par défaut

---

## 📁 Fichiers de configuration

```
%USERPROFILE%\
├── whisper_helio_config.json    # Configuration utilisateur
└── whisper_helio_crash.log      # Logs d'erreur (si problème)
```

---

## 🏗️ Architecture technique

```
Whisper Hélio v1.5
│
├── Thread principal (Tkinter)
│   ├── Interface utilisateur
│   ├── VU-mètre animé (30 fps)
│   ├── Label streaming flottant (aperçu temps réel)
│   └── Gestion des événements
│
├── Thread chargement
│   ├── Chargement modèle Whisper (large-v3)
│   ├── Chargement modèle streaming (tiny, CPU)
│   ├── Boucle d'enregistrement
│   └── Transcription (BatchedInferencePipeline GPU)
│
├── Thread watchdog
│   └── Surveillance et relance automatique
│
├── Thread VRAM cleanup
│   └── gc.collect + torch.cuda.empty_cache (toutes les 5 min)
│
├── Callback audio (sounddevice)
│   └── Capture micro → RingBuffer
│
└── Hooks clavier/souris (keyboard)
    └── Détection raccourcis
```

---

## 📄 Changelog

### v1.5 (Mars 2026)
- Streaming temps réel (aperçu pendant la dictée, double modèle tiny + principal)
- Export multi-format (SRT, VTT, TXT horodaté, TXT brut, JSON)
- Interface française : tous les accents restaurés (30+ corrections)
- 6 corrections d'audit (upx_exclude, guards audio, log_error)

### v1.4b (Mars 2026)
- Transcription fichiers audio (drag-and-drop + bouton 📂)
- **Transcription fichier 8.7× plus rapide** (BatchedInferencePipeline GPU)
- Nouveau modèle `large-v3-turbo` (2× plus rapide)
- Contrôle automatique du volume micro (pycaw)
- Fenêtre Paramètres redessinée (style cohérent, drag, coins arrondis)
- Interface française avec accents complets
- 70+ bugs corrigés par audit expert
- Anti-hallucination fichiers longs (musique)
- Hook souris conditionnel, VU-mètre adaptatif
- Watchdog amélioré, protection fermeture
- Mode build onedir (stabilité DLL améliorée)

### v1.3 (Février 2026)
- Interface modernisée (boutons ronds)
- Performance +40% transcription
- CPU -40% en idle
- 220+ passes de vérification
- Support DPI haute résolution
- Corrections bugs critiques

### v1.2 (2025)
- Mode réunion
- Support souris gaming X1/X2
- Thème clair/sombre
- Multi-langue interface

### v1.1 (2025)
- Amélioration stabilité
- Ajout paramètres

### v1.0 (2024)
- Version initiale

---

## ❤️ Soutenir le projet

Whisper Hélio est **gratuit** et le restera. Si vous l'appréciez, vous pouvez soutenir son développement :

[![PayPal](https://img.shields.io/badge/PayPal-Faire_un_don-blue.svg?logo=paypal)](https://www.paypal.com/paypalme/heliostmalo)

---

## 📄 Licence

GNU General Public License v3.0 — voir [LICENSE](LICENSE)

---

## 🙏 Remerciements

- [OpenAI Whisper](https://github.com/openai/whisper) — Le modèle de reconnaissance vocale
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Implémentation optimisée CTranslate2
- La communauté open source

---

<p align="center">
  Créé avec ❤️ par <strong>Hélio</strong> — Bretagne, France<br>
  <em>Projet Seattle (USA) 2028</em>
</p>

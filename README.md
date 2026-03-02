# 🎤 Whisper Hélio v1.4b

**Dictée vocale Windows — 100% offline, 100% gratuit**

[![Version](https://img.shields.io/badge/version-1.4b-green.svg)](https://github.com/helioman32/whisper-helio/releases)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Windows](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)]()
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)]()

<p align="center">
  <img src="whisper_helio_icon.png" alt="Whisper Helio" width="128">
</p>

<p align="center">
  <strong>Transformez votre voix en texte instantanément, sans connexion internet.</strong>
</p>

<p align="center">
  <a href="https://github.com/helioman32/whisper-helio/releases/latest">📥 Télécharger</a> •
  <a href="https://helioman32.github.io/whisper-helio/">🌐 Site Web</a> •
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
| 🆓 **Gratuit** | Open source, sans pub, sans abonnement |

---

## 🆕 Nouveautés v1.4b

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

### 🛡️ Stabilité améliorée
- **800+ passes de vérification** du code
- Sauvegarde config atomique (`.tmp` + `os.replace`)
- Fix `ensure_ascii=False` — accents bien sauvegardés dans la config
- Fix `ButtonRelease-1` — curseur de resize correctement réinitialisé

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

1. Téléchargez la [dernière release](https://github.com/helioman32/whisper-helio/releases/latest)
2. Extrayez le ZIP
3. Lancez `WhisperHelio.exe`
4. Au premier lancement, le modèle Whisper sera téléchargé automatiquement (~800 MB pour large-v3-turbo)

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
Whisper Hélio v1.4b
│
├── Thread principal (Tkinter)
│   ├── Interface utilisateur
│   ├── VU-mètre animé (30 fps)
│   └── Gestion des événements
│
├── Thread chargement
│   ├── Chargement modèle Whisper
│   ├── Boucle d'enregistrement
│   └── Transcription
│
├── Thread watchdog
│   └── Surveillance et relance automatique
│
├── Callback audio (sounddevice)
│   └── Capture micro → RingBuffer
│
└── Hooks clavier/souris (keyboard)
    └── Détection raccourcis
```

---

## 🤝 Contribution

Les contributions sont les bienvenues !

1. Fork le projet
2. Créez une branche (`git checkout -b feature/amelioration`)
3. Committez (`git commit -m 'Ajout fonctionnalité'`)
4. Push (`git push origin feature/amelioration`)
5. Ouvrez une Pull Request

---

## 📄 Changelog

### v1.4b (Février 2026)
- Nouveau modèle `large-v3-turbo` (2× plus rapide)
- Fenêtre Paramètres redessinée (style cohérent, drag, coins arrondis)
- Interface française avec accents complets
- Sauvegarde config atomique
- 800+ passes de vérification
- Fix ensure_ascii, ButtonRelease-1

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

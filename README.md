# 🎙 Whisper Hélio v1.2

**Logiciel de dictée vocale gratuit et autonome propulsé par OpenAI Whisper**

> Dictez du texte dans n'importe quelle application Windows en appuyant sur une touche — rapide, précis, et 100% confidentiel (fonctionne totalement hors ligne).

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE.txt)
[![Donate PayPal](https://img.shields.io/badge/Soutenir%20le%20projet-PayPal-blue.svg)](https://paypal.me/heliostmalo)

---

## ✨ Points forts

- 🔒 **Confidentialité totale** — Aucun son envoyé sur internet, tout est traité localement
- 📦 **Aucune installation requise** — Version .exe autonome, pas besoin de Python
- 🎤 **Dictée Push-to-Talk** — Maintenez F9 (ou un bouton souris), parlez, relâchez
- 🔴 **Mode Réunion** — Enregistrement continu avec transcription automatique toutes les 5 secondes
- ⚡ **Optimisation GPU** — Utilise votre carte NVIDIA (CUDA) pour une transcription ultra-rapide
- 🌍 **Multi-langues** — Français, anglais, allemand, espagnol, italien et plus
- 🖥️ **Interface trilingue** — Interface disponible en français, anglais et allemand
- 🖱️ **Boutons souris** — Compatible avec les boutons pouce de votre souris
- 💾 **100% hors ligne** — Aucune connexion internet requise
- 🪟 **Windows 10/11** uniquement

---

## 🚀 Installation rapide

1. **Téléchargez** l'archive `Whisper_Helio_v1.2.zip`
2. **Extrayez** tout le contenu dans un dossier (ex: `C:\Whisper Helio\`)
3. Lancez **`installer.bat`** — crée les raccourcis et configure le démarrage automatique
4. Double-cliquez sur le raccourci **Whisper Helio** créé sur votre Bureau

> ⚠️ Ne pas supprimer le dossier `_internal` — il contient le moteur IA

---

## 📦 Contenu de l'archive

| Fichier / Dossier | Description |
|---|---|
| `Whisper Helio.exe` | Application principale |
| `_internal/` | Moteur IA (ne pas supprimer) |
| `installer.bat` | Installateur automatique |
| `whisper_helio.ico` | Icône de l'application |
| `Notice_Whisper_Helio.docx` | Notice complète trilingue (FR/EN/DE) |
| `LICENSE.txt` | Licence MIT |

---

## 🖥️ Configuration recommandée

| | Minimum | Recommandée |
|---|---|---|
| **OS** | Windows 10 | Windows 11 |
| **CPU** | Intel i5 / Ryzen 5 | Intel i7 / Ryzen 7 |
| **RAM** | 8 Go | 16 Go |
| **GPU** | — | NVIDIA RTX 2000+ avec CUDA |
| **Disque** | 5 Go | 5 Go + SSD recommandé |

---

## 🎯 Utilisation

1. Lancer **Whisper Hélio** depuis le raccourci Bureau
2. Attendre la fin de l'initialisation (voyant 🟢 vert)
3. Placer le curseur dans n'importe quelle zone de texte
4. **Maintenir F9** → parler → **relâcher** → le texte apparaît !

### Mode Réunion
Cliquer sur le bouton **⏺ vert** pour activer l'enregistrement continu. Le texte se colle automatiquement toutes les 5 secondes. Re-cliquer pour arrêter.

> 💡 La fenêtre ne vole jamais le focus — votre zone de texte reste active même en cliquant sur les boutons.

---

## ⚙️ Paramètres

Cliquer sur **⚙** pour accéder aux paramètres (changements immédiats sans redémarrage) :

- **Thème** — Sombre ou clair
- **Modèle Whisper** — `tiny` (75 Mo) à `large-v3` (3 Go)
- **Device** — Auto, CUDA (GPU NVIDIA) ou CPU
- **Langue dictée** — fr, en, de, es, it, pt, nl
- **Langue interface** — Français, English, Deutsch
- **Raccourci** — F9 à F12, bouton pouce avant/arrière souris
- **Position de démarrage** — Coin ou centre de l'écran

---

## 🔧 Modèles Whisper

| Modèle | Taille | Précision |
|---|---|---|
| tiny | 75 Mo | Basique |
| base | 140 Mo | Correcte |
| small | 480 Mo | Bonne |
| medium | 1.5 Go | Très bonne |
| large-v3 | 3 Go | Excellente |

> Le changement de modèle nécessite un redémarrage de l'application

---

## 📄 Licence

MIT License — voir [LICENSE.txt](LICENSE.txt)

Basé sur [OpenAI Whisper](https://github.com/openai/whisper) et [faster-whisper](https://github.com/guillaumekln/faster-whisper)

---

## ☕ Soutenir le projet

Whisper Hélio est un projet indépendant et gratuit. Si ce logiciel vous est utile :

[![Soutenir le projet](https://img.shields.io/badge/Faire%20un%20don-PayPal-blue.svg)](https://paypal.me/heliostmalo)

---

**Réalisation Hélio — Février 2026**

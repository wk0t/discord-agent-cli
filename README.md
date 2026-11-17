# discord-agent-cli

Un client Discord en ligne de commande, conçu pour être piloté par un **agent IA** :
chaque commande produit un **JSON unique et uniforme sur stdout**, jamais de texte libre.

L'agent peut donc enchaîner naturellement :
`guilds` → `channels <guild_id>` → `messages <channel_id>` → `send` / `react` / `search` / `watch`...

## Contrat de sortie

Succès (code de sortie 0) :

```json
{"ok": true, "command": "messages", "data": [ ... ]}
```

Erreur (code de sortie 1) :

```json
{"ok": false, "command": "send", "error": {"type": "Forbidden", "message": "Missing Permissions"}}
```

- `watch` émet des **JSON lines** (un objet par ligne) : `{"ok": true, "event": "message", "data": {...}}`
- `--pretty` indente le JSON pour un humain ; sans le flag, c'est compact (idéal pour parser).
- Les logs internes vont sur **stderr**, jamais sur stdout.

## Installation

```bash
pip install -r requirements.txt
```

## Créer le bot Discord

1. Va sur <https://discord.com/developers/applications> → **New Application** → onglet **Bot** → **Add Bot**.
2. Copie le **token** (bouton *Reset Token*).
3. Active les **intents privilégiés** dans l'onglet *Bot* : `SERVER MEMBERS INTENT` et `MESSAGE CONTENT INTENT` (obligatoires pour lire les messages et la liste des membres).
4. Onglet *OAuth2 → URL Generator* : scopes `bot` (+ `applications.commands` si besoin), permissions utiles : `Read Messages/View Channels`, `Send Messages`, `Read Message History`, `Add Reactions`, `Manage Messages`, `Manage Channels`, `View Server Members`... puis invite le bot sur ton serveur avec l'URL générée.

## Configuration du token

```bash
cp .env.example .env   # puis mets ton token dans .env
# ou :
export DISCORD_TOKEN="ton_token"
# ou à chaque appel :
python discord_cli.py --token "ton_token" whoami
```

`.env` est dans `.gitignore` : le token ne sera jamais commité.

## Commandes

| Commande | Description | Exemple |
|---|---|---|
| `whoami` | identité du bot, latence | `python discord_cli.py whoami` |
| `guilds` | serveurs du bot | `python discord_cli.py guilds` |
| `guild <id>` | détails serveur + rôles | `python discord_cli.py guild 111...` |
| `channels <guild_id>` | salons (`--type`, `--category`) | `python discord_cli.py channels 111... --type text` |
| `channel <id>` | détails d'un salon | `python discord_cli.py channel 222...` |
| `messages <channel_id>` | historique (`-n`, `--before`, `--after`) | `python discord_cli.py messages 222... -n 30` |
| `send <channel_id> <texte>` | envoyer (`--reply-to`, `--file`, `--embed-*`) | `python discord_cli.py send 222... "Salut !"` |
| `edit <channel_id> <msg_id> <texte>` | éditer un message du bot | `... edit 222... 333... "corrigé"` |
| `delete <channel_id> <msg_id>` | supprimer un message | `... delete 222... 333...` |
| `react` / `unreact` | réagir à un message | `... react 222... 333... "👍"` |
| `pins <channel_id>` | messages épinglés | `... pins 222...` |
| `members <guild_id> [-n]` | membres du serveur | `... members 111... -n 200` |
| `member <guild_id> <user_id>` | détails d'un membre | `... member 111... 999...` |
| `roles <guild_id>` / `emojis <guild_id>` | rôles / emojis | `... roles 111...` |
| `search <query> --channel/--guild <id>` | recherche dans l'historique | `... search "rdv" --guild 111... --max 5000` |
| `create-channel <guild_id> <nom>` | créer un salon (`--type`, `--category`, `--topic`) | `... create-channel 111... "announces" --type text` |
| `delete-channel <id>` | supprimer un salon | `... delete-channel 222...` |
| `threads <channel_id> [--archived]` | threads d'un salon | `... threads 222...` |
| `create-thread <channel_id> <nom>` | créer un thread (`--message-id`, `--private`) | `... create-thread 222... "fil-1"` |
| `dm <user_id> <texte>` | message privé | `... dm 999... "hello en DM"` |
| `profile <user_id>` | profil global d'un user | `... profile 999...` |
| `watch <channel_id...>` | **temps réel** : JSON lines des nouveaux messages, Ctrl-C pour quitter (`--timeout N` pour s'arrêter seul) | `... watch 222... 444... --timeout 60` |

## Mode `--mock` (sans token)

Pour tester le contrat JSON sans compte Discord :

```bash
python discord_cli.py --mock --pretty guilds
python discord_cli.py --mock messages 123 -n 5
python discord_cli.py --mock watch 123
```

## Exemple de chaîne pour un agent

```bash
python discord_cli.py guilds                          # choisir un serveur
python discord_cli.py channels <guild_id>             # trouver #général
python discord_cli.py messages <channel_id> -n 50      # lire le contexte récent
python discord_cli.py send <channel_id> "Résumé: ..."  # répondre
python discord_cli.py watch <channel_id> --timeout 300 # attendre les nouveaux messages
```

## Limites connues

- `search --guild` parcourt l'historique salon par salon : borner avec `--max` (défaut 2000 messages scannés).
- `edit` ne fonctionne que sur les messages écrits par le bot lui-même (règle Discord).
- `members` nécessite l'intent *Server Members* activé sur le portail développeur.
- Le token n'est jamais affiché, y compris dans les erreurs.

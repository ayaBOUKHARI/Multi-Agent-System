# Robot Mission — Waste Collection MAS 2026
## Documentation d'architecture

---


## La grille et les zones

```
x=0                x=W//3         x=2W//3          x=W-1
|--- Zone 1 (z1) ---|--- Zone 2 (z2) ---|--- Zone 3 (z3) ---|
   faible radioact.    radioact. moyenne    forte radioact.
   déchets verts        déchets jaunes       zone de dépôt ★
   robots verts         robots jaunes
                        robots jaunes
                        robots rouges         robots rouges
```

| Zone | x | Radioactivité | Déchets initiaux | Robots autorisés |
|------|---|---------------|-----------------|-----------------|
| z1 | `[0, W//3-1]` | 0.00 – 0.33 | Verts | Vert |
| z2 | `[W//3, 2W//3-1]` | 0.33 – 0.66 | — | Jaune |
| z3 | `[2W//3, W-1]` | 0.66 – 1.00 | — | Rouge |

La zone de dépôt (★) est placée aléatoirement dans la dernière colonne (z3).

---

## Pipeline de transformation des déchets

```
  z1                      z2                      z3
  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
  │  🟩 Déchets verts │    │  🟡 Déchets jaunes│    │  🔴 Déchets rouges│
  │                  │    │                  │    │                  │
  │  Robot VERT      │    │  Robot JAUNE     │    │  Robot ROUGE     │
  │  ramasse 2 verts │    │  ramasse 2 jaunes│    │  ramasse 1 rouge │
  │  → transforme    │    │  → transforme    │    │  → dépose en ★   │
  │  → 1 jaune       │    │  → 1 rouge       │    │  → ÉLIMINÉ ✓     │
  │  → dépose bord z1│    │  → dépose bord z2│    │                  │
  └──────────────────┘    └──────────────────┘    └──────────────────┘
```

**Règle mathématique** : N déchets verts → N/2 jaunes → N/4 rouges → N/4 éliminés.
Pour une élimination totale, N doit être un multiple de 4 (ex : 8, 12, 16…).

---

## Les agents

### Agents passifs (`objects.py`)

| Classe | Rôle |
|--------|------|
| `RadioactivityAgent` | Un par cellule — encode le numéro de zone et le niveau de radioactivité |
| `WasteAgent` | Un déchet sur la grille (`waste_type` ∈ `{"green", "yellow", "red"}`) |
| `WasteDisposalZone` | Marque la cellule de dépôt final ; les robots rouges y déposent les déchets rouges |

Ces agents n'ont **pas de comportement** (`step()` = pass).

### Robots (`agents.py`)

| Classe | Zone | Inventaire max | Rôle |
|--------|------|---------------|------|
| `GreenAgent` | z1 | 2 | Collecte 2 verts → transforme → dépose 1 jaune en bord z1 |
| `YellowAgent` | z1 + z2 | 2 | Collecte 2 jaunes → transforme → dépose 1 rouge en bord z2 |
| `RedAgent` | z1 + z2 + z3 | 1 | Collecte 1 rouge → navigue vers ★ → dépose → éliminé |

---

## Boucle d'un robot (par step)

```
┌─────────────────────────────────────────────────────────────────┐
│  1. _update_knowledge(percepts_du_step_précédent)               │
│     ├── extrait la mailbox (messages reçus)                     │
│     ├── met à jour pos, percepts, known_wastes                  │
│     ├── résout / timeout l'état de handoff                      │
│     └── traite chaque message entrant (_process_message)        │
│                                                                 │
│  2. action = deliberate_fn(knowledge)                           │
│     └── fonction PURE : ne lit que knowledge, pas de globals    │
│                                                                 │
│  3. model.do(agent, action)                                     │
│     ├── exécute l'action sur la grille                          │
│     └── retourne les nouveaux percepts (5 cellules + mailbox)   │
└─────────────────────────────────────────────────────────────────┘
```

### La base de connaissance (`knowledge`)

```python
knowledge = {
    # Perception
    "pos":            (x, y),
    "percepts":       {(x,y): {"wastes": [...], "robots": [...], "radioactivity": float, "is_disposal": bool}},
    "known_wastes":   {(x,y): "green"|"yellow"|"red"},   # mémoire persistante

    # État interne
    "inventory":      ["green", "green"],   # liste des déchets portés
    "zone_boundaries": {"z1_max_x": int, "z2_max_x": int, ...},
    "disposal_pos":   (x, y),

    # Communication (Step 2)
    "mailbox":        [...],        # messages reçus ce step
    "pending_msg":    {...}|None,   # message à envoyer (priorité 0 dans deliberate)
    "partner_id":     int|None,     # ID du partenaire de handoff
    "partner_pos":    (x,y)|None,   # position cible du rendezvous
    "handoff_role":   "initiator"|"responder"|None,
    "handoff_wait":   int,          # compteur de timeout
    "drop_avoid_pos": (x,y)|None,   # position à ignorer pour ramassage (anti self-pickup)
}
```

### Priorités de délibération — GreenAgent

| Priorité | Condition | Action |
|----------|-----------|--------|
| 0 | `pending_msg` non vide | `send_message` (réponse ACCEPT en attente) |
| 1 | `inventory` ≥ 2 verts | `transform` |
| 2 | `inventory` contient 1 jaune | `move E` → `put_down yellow` au bord z1 |
| 3 | `handoff_role == "responder"` | Naviguer vers `partner_pos` → `put_down green` |
| 4 | Déchet vert visible dans percepts | `pick_up` ou `move` vers lui (skip `drop_avoid_pos`) |
| 5 | Déchet vert dans `known_wastes` | `move` vers lui (skip `drop_avoid_pos`) |
| 6 | `handoff_role == "initiator"` | `stay` (attendre le responder) |
| 7 | `inventory` = 1 vert (15% chance) | `send_message has_unpaired` broadcast |
| 8 | Déchet jaune visible | `send_message waste_at` → robots jaunes (Protocol B) |
| 9 | Sinon | `move` aléatoire dans z1 |

*(YellowAgent suit la même logique pour jaune/rouge ; RedAgent va directement vers ★)*

---

## Le modèle (`model.py`)

### Actions supportées par `model.do(agent, action)`

| Action | Paramètres | Effet |
|--------|-----------|-------|
| `move` | `direction`: N/S/E/W/stay | Déplace si dans les limites et zone autorisée |
| `pick_up` | — | Ramasse le premier déchet compatible dans la cellule actuelle |
| `transform` | — | Consomme 2 déchets → produit 1 déchet du tier supérieur |
| `put_down` | `waste_type` | Dépose depuis inventaire ; si à ★ et déchet rouge → éliminé |
| `send_message` | `recipients`, `message` | Route vers la mailbox des destinataires |

### Perceptions (`_get_percepts`)

Chaque appel à `model.do()` retourne les 5 cellules observables (cellule courante + N/S/E/W) **et la mailbox** du robot (clé spéciale `"__mailbox__"`).

```python
{
    (3, 4): {"radioactivity": 0.15, "wastes": [{"waste_type": "green"}], "robots": [], "is_disposal": False},
    (4, 4): {"radioactivity": 0.18, "wastes": [], "robots": [{"color": "green"}], "is_disposal": False},
    ...
    "__mailbox__": [{"sender_id": 42, "performative": "inform", "content": {...}}, ...]
}
```

---

## Communication décentralisée (Step 2)

### Format de message (inspiré FIPA-ACL)

```python
{
    "sender_id":    int,           # unique_id de l'émetteur
    "sender_color": "green"|"yellow"|"red",
    "sender_pos":   (x, y),
    "performative": "inform"|"accept"|"refuse",
    "content":      dict,          # payload spécifique au protocole
}
```

### Routage (`model.message_router`)

```python
message_router: dict[int, list[dict]]  # unique_id → file de messages
```

`send_message` avec `recipients=None` → broadcast à tous les robots de la même couleur.
`send_message` avec `to_color="yellow"` → broadcast vers les robots jaunes.
`send_message` avec `recipients=[id1, id2]` → unicast/multicast ciblé.

---

### Protocole A — Handoff de déchet (résolution des interblocages)

**Problème** : un robot porte 1 déchet mais a besoin de 2 pour transformer. Personne d'autre n'en apporte.

```
Robot A (1 vert, bloqué)          Robot B (1 vert, bloqué)
  │                                    │
  │── INFORM has_unpaired ────────────►│
  │   {waste: "green", pos: A.pos}     │
  │                                    │  B devient responder
  │◄── ACCEPT handoff_accept ─────────│  partner_pos = A.pos
  │                                    │
  A devient initiator                  │  B navigue vers A.pos
  A attend (stay)                      │
                                       │  B arrive → put_down green
                                       │  (drop_avoid_pos = A.pos → B ne ramasse pas)
  A voit vert visible ─────────────────►  A ramasse → 2 verts → transform ✓
```

**Garde-fous** :
- `drop_avoid_pos` — empêche B de ramasser immédiatement le déchet qu'il vient de déposer
- Timeout initiator (20 steps) — A reprend son exploration si B ne vient pas
- Timeout responder (40 steps) — B abandonne si A est inaccessible
- Broadcast probabiliste (15%) — les robots wandèrent 85% du temps pour trouver d'autres déchets sur la grille

### Protocole B — Partage de carte (stigmergie légère)

Quand un robot voit un déchet qui appartient à un autre tier, il prévient les robots concernés :

| Qui voit | Quoi | Informe |
|----------|------|---------|
| GreenAgent | déchet jaune | robots jaunes → `waste_at` |
| YellowAgent | déchet rouge | robots rouges → `waste_at` |

Le récepteur ajoute la position à son `known_wastes`. Cela réduit le temps de recherche aléatoire.

---

## Collecte de données

`DataCollector` (Mesa) enregistre à chaque step :

| Métrique | Description |
|----------|-------------|
| `Green wastes` | Déchets verts sur la grille |
| `Yellow wastes` | Déchets jaunes sur la grille |
| `Red wastes` | Déchets rouges sur la grille |
| `Total wastes` | Total sur la grille |
| `In inventories` | Total dans les inventaires des robots |
| `Disposed` | Cumulatif éliminés en zone de dépôt |

---

## Lancer la simulation

### Mode interactif (SolaraViz)

```bash
solara run robot_mission_MAS2026/server.py
```

Ouvre un navigateur avec la grille animée, des sliders pour ajuster les paramètres, et deux graphiques en temps réel.

### Mode headless (terminal)

```bash
# Défauts : 12 déchets, 300 steps, 3 robots de chaque couleur
python robot_mission_MAS2026/run.py

# Paramètres explicites
python robot_mission_MAS2026/run.py --steps 200 --wastes 12 --seed 42

# Sans graphique matplotlib
python robot_mission_MAS2026/run.py --no-plot
```

**Sortie attendue (12 déchets verts, multiples de 4)** :
```
  All waste disposed at step 133!
  Final disposed: 3
```

---

## Résultats observés

| Déchets verts | Éliminés théoriques max | Éliminés avec comm. | Termine ? |
|:---:|:---:|:---:|:---:|
| 8 | 2 | 2 | ✅ ~250 steps |
| 12 | 3 | 3 | ✅ ~150 steps |
| 16 | 4 | 4 | ✅ ~200 steps |
| 10 | 2 | 2 | ⚠️ 1 jaune irréductible (10 n'est pas un multiple de 4) |

---

## Notes techniques Mesa 3.5

| Problème | Cause | Solution |
|----------|-------|----------|
| `zorder` bug dans `_scatter` | `z_order == zorder & mask` évalue `&` avant `==` | Utiliser `zorder=1` pour tous les agents visibles |
| `FutureWarning portrayal` | Mesa 3.5 déprécie le retour de dicts | Retourner `AgentPortrayalStyle(...)` |
| `post_process(ax, model)` → erreur | Mesa appelle `post_process(ax)` sans model | Signature `post_process_space(ax)` + déduire la taille depuis `ax.get_xlim()` |
| `SolaraViz(RobotMission, ...)` → AttributeError | Mesa 3.5 attend une instance, pas la classe | Passer `_initial_model = RobotMission(...)` |

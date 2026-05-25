---
name: navigate_to
description: "Move the mobile base to a target pose or named landmark."
triggers:
  - "go to"
  - "navigate"
  - "去客厅"
preconditions: {}
parameters:
  target:
    type: string
    required: true
    description: "Either a scene graph object ID or a named landmark (e.g. 'kitchen_sink')."
  approach_distance:
    type: number
    required: false
    default: 0.6
    description: "Stop this many meters short of the target, in metres."
---

# Steps
1. Resolve `target` to a pose via the scene graph or the static landmark map.
2. Plan a path with the cerebellum nav stack.
3. Drive; monitor for dynamic obstacles every 0.5s.
4. On arrival, verify with a quick observation snap (should see the target in view).

# Known Failure Modes
- **Target not in scene graph and not in landmark map.** Replan: trigger `explore_room` first.
- **Path blocked by a person.** Wait up to 5s, then re-plan around.
- **Localization drift.** Cerebellum self-recovers; if it can't, escalate.

# Notes
Skill kept deliberately thin — the heavy lifting is in the cerebellum (ViNT-style nav foundation model or local SLAM). The brain only handles target resolution and high-level retry.

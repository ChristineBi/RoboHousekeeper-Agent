---
name: wipe_table
description: "Wipe a table surface to remove dust, water stains, or visible dirt."
triggers:
  - "wipe table"
  - "clean table"
  - "擦桌子"
  - "擦拭桌面"
preconditions:
  has_cloth: true
parameters:
  target_table:
    type: string
    required: true
    description: "Object ID of the table from the scene graph."
  thoroughness:
    type: string
    enum: [light, normal, deep]
    default: normal
---

# Steps
1. Look up `target_table` pose from the scene graph.
2. Check if any movable obstacle is on the table; if yes, delegate to `pickup_movable_obstacle` first (subtask insertion).
3. Plan an S-shape coverage path over the visible top surface.
4. Apply 5N normal force on the cloth, traverse the path at ~5 cm/s.
5. Re-observe the table; if visible dirt remains and `thoroughness == deep`, repeat once.

# Preconditions in detail
- `has_cloth` — the gripper must already be holding a cloth. If not, run `pickup_cloth` first.
- Table must be in front of the robot's nav goal pose (auto-checked by the cerebellum).

# Known Failure Modes
- **Glossy surface causes depth drift.** Fall back to RGB-only plane fit (cerebellum flag `--rgb-only`).
- **Cup or cable on table.** Detected by perception; insert `pickup_movable_obstacle` as a child subtask.
- **Robot arm reach limit.** If table is too wide, plan two coverage passes from different base poses.

# Success Criteria
- `dirt_pixel_ratio < 0.02` in the re-observed RGB (heuristic; replace with VLM check in M2).
- Cloth not dropped, gripper still holding.

# Notes
*Initial version — written by hand at project bootstrap. Will be auto-patched by the self-improvement loop after enough real trials.*

---
name: pickup_movable_obstacle
description: "Pick up a movable object that blocks another task (e.g. a cup on the table being wiped) and place it in a safe nearby location."
triggers:
  - "move obstacle"
  - "clear obstacle"
  - "把杯子拿走"
preconditions:
  has_free_gripper: true
parameters:
  obstacle_id:
    type: string
    required: true
    description: "Scene graph object ID of the obstacle to relocate."
  destination:
    type: string
    required: false
    default: "nearest_clear_spot"
    description: "Where to put it. Default: brain picks a clear nearby surface."
---

# Steps
1. Confirm `obstacle_id` is graspable (size, weight, fragility attributes).
2. If `liquid_inside == true` and `lid == false`, escalate — do **not** grab a half-full open cup; mark `needs_human` and abort.
3. Plan top-down grasp; if attribute `fragile == true`, reduce closure force to 50%.
4. Lift, transport to `destination`, place gently.
5. Update scene graph: remove `obstacle_id` from the source surface relation.

# Preconditions in detail
- `has_free_gripper` — one gripper must currently be empty. If both hands occupied, plan a temporary place-then-resume.

# Known Failure Modes
- **Liquid inside, no lid.** Hard escalation to human handover. Don't try.
- **Object slides during grasp.** Retry with parallel-jaw closure 20% increased; if still failing, replan.
- **Destination has its own obstacle.** Recursively call `pickup_movable_obstacle` — bounded by depth=1 to avoid loops.

# Success Criteria
- Obstacle no longer on source surface in re-observation.
- Obstacle intact and upright at destination.

# Notes
This skill is the **prototypical example of dynamic subtask insertion**: it's not part of the original "wipe table" plan, but gets inserted by the brain when perception finds a blocker. See `docs/RESEARCH.md § 5.2`.

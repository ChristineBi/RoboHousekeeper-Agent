---
name: improve_policy
description: "Periodically inspect recent episodes, fine-tune SmolVLA on successful ones, A/B evaluate, and promote the winner. The self-improvement loop."
triggers:
  - "improve the policy"
  - "retrain"
  - "self-improve"
  - "改进策略"
preconditions:
  has_local_gpu: true
parameters:
  reward_threshold:
    type: number
    required: false
    default: 0.6
    description: "Min subtask success ratio for an episode to be included in training."
  min_episodes:
    type: integer
    required: false
    default: 50
    description: "Skip the retrain if fewer than this many good episodes accumulated."
---

# Steps

1. Pull the most recent episodes from `MemoryManager`.
2. Filter: drop human-handover episodes; keep those with subtask success ratio ≥ `reward_threshold`.
3. If fewer than `min_episodes` survive, skip this round (logged).
4. Export the filtered episodes to LeRobot dataset format.
5. Fine-tune SmolVLA from the current incumbent checkpoint on the new dataset (config in `configs/training.yaml`).
6. Run open-loop eval on the held-out RoboCasa task set, both for the incumbent and the new (challenger) checkpoint.
7. Decision: promote the challenger only if **(a)** mean success improves by ≥ 2pp **and** **(b)** no individual task regresses by more than 10pp relative to incumbent.
8. Log the decision, update the active checkpoint pointer, append a one-line entry to `MEMORY.md`.

# Known Failure Modes

- **Slow-bleed regression.** A pure mean-success A/B can promote a model that trades hard tasks for easy ones. The worst-task floor in step 7 is what prevents this — it's the main divergence from hermes-embodied's vanilla A/B.
- **Mode collapse from over-filtering.** If `reward_threshold` is too high, we only train on the easy tasks and forget the hard ones. Watch the per-task episode count, not just the total.
- **LeRobot stats drift.** If the dataset stats (joint ranges, image normalization) diverge from the base model's expectations, training silently underperforms. Validate stats before launching the fine-tune.

# Success Criteria

- The "active checkpoint" pointer either stays the same or moves forward.
- Over many rounds, mean success on the eval set should monotonically improve (modulo noise). Logged in `MEMORY.md`'s `## Skill curve` section.

# Notes

This skill's procedure is borrowed from [hermes-embodied](https://github.com/bryercowan/hermes-embodied)'s `robot-loop` skill. Key divergences:

- We use local / cluster GPU, not Vast.ai.
- We add a per-task regression floor (see Step 7).
- Trigger is event-driven (M4) not strictly cron — we kick off when ≥ `min_episodes` good ones accumulate, not on a fixed schedule.

Entry point: `scripts/offline_improve.py`.

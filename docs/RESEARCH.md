# RoboHousekeeper-Agent: 基于 Hermes 框架借鉴的家务机器人 Agent 调研

## RoboOS 

```mermaid
flowchart TB
    subgraph Cloud["☁️ Cloud — Embodied Brain"]
        Brain["RoboBrain (MLLM)<br/>多机任务分解 · 工具调用<br/>时空记忆 · 自适应纠错"]
    end
    subgraph Edge["📡 Edge — Cerebellum (per robot)"]
        Skill1["Skill: pick"]
        Skill2["Skill: place"]
        Skill3["Skill: navigate"]
        SkillN["..."]
    end
    Shared["🧠 Real-Time Shared Memory<br/>(多 agent 时空同步)"]

    Brain <-->|edge-cloud comm| Edge
    Brain <--> Shared
    Edge <--> Shared
```

## Roadmap

### 整体架构

```mermaid
flowchart TB
    User["👤 USER<br/><i>'把厨房收拾一下,客厅地毯吸一下尘'</i>"]

    subgraph BrainLayer["🧠 BRAIN (Cloud · RoboBrain backbone)"]
        Planner["Planner<br/>(RoboBrain 2.5)"]
        Selector["Skill Selector & Composer<br/><i>← Hermes SKILL.md library</i>"]
        SelfEval["Self-Eval Checkpoint<br/><i>← Hermes 每 N 步反思</i>"]
        Mem["Memory Manager<br/><i>← Hermes MEMORY.md +<br/>scene KG + episodes</i>"]
        Heartbeat(("⏱ Heartbeat<br/>cron-like"))
        Spawner["Sub-Agent Spawner<br/><i>← Hermes contained subagents</i>"]
    end

    subgraph Perception["👁 Perception"]
        RGBD["RGB-D + Depth"]
        SceneKG["Scene Graph"]
        Detect["Event Detectors"]
    end

    subgraph SubAgent["🛠 Sub-Agent: wipe_table"]
        SubCtx["isolated context<br/>+ local memory"]
    end

    subgraph Cerebellum["⚡ CEREBELLUM (Edge · 30Hz)"]
        VLA["VLA policy<br/>(RoboBrain-X0 / pi-0)"]
        Prim["Motion Primitives"]
        Ctrl["Low-level Control"]
    end

    Hardware["🤖 Robot Hardware"]

    User --> Planner
    Planner --> Selector
    Selector --> Spawner
    Spawner --> SubAgent
    SubAgent --> Cerebellum
    Cerebellum --> Hardware
    Hardware --> Perception
    Perception --> Mem
    Perception --> SelfEval
    SelfEval --> Mem
    Mem --> Planner
    Heartbeat --> Perception
    SelfEval -.lessons.-> Selector
```

### 模块对应表

| 模块 | 灵感来源 | 实现路径 |
|------|---------|---------|
| `brain/planner` | RoboBrain 2.5 | 调用本地 / API 推理 |
| `brain/skill_library` | **Hermes Skills** | YAML+Markdown,带 trigger / preconditions / failure modes |
| `brain/self_eval` | **Hermes Self-Improving Loop** | 每 N 步 checkpoint,生成 trajectory summary |
| `brain/memory` | **Hermes Memory** + scene graph | `MEMORY.md` (家庭事实) + `SCENE.json` (动态场景图) + `EPISODES.db` (历史轨迹) |
| `brain/orchestrator` | **Hermes Sub-Agent + Kanban** | 任务分解为 kanban-style cards,失败重试 / 升级机制 |
| `perception` | Scene Graph-Guided Replanning | 事件驱动 + 周期性扫描混合 |
| `executor` | RoboOS Cerebellum | 接 RoboBrain-X0 / OpenVLA / pi-0 等 VLA 模型 |
| `executor/rollout.py` | **hermes-embodied `collect_trajectories.py`** | MuJoCo / RoboCasa rollout,LeRobot 格式存储 |
| `training/finetune_smolvla.py` | **hermes-embodied `train_smolvla.py`** | SmolVLA 微调封装(本地 GPU) |
| `scripts/offline_improve.py` | **hermes-embodied `improvement_loop.py`** | A/B checkpoint 比较 + 自动晋升 |
| `safety_guard` | **Hermes Soul** + 物理约束 | hard limits + 软约束(用户偏好) |

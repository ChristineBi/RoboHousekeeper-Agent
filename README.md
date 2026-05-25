# RoboHousekeeper-Agent

> 基于 **RoboOS / RoboBrain2.5** 大脑、借鉴 **Hermes Agent** 工作流的家务机器人多模态 agent。
> 仿真栈: **RoboSuite + MuJoCo** · Benchmark: **RoboCasa / RoboCasa365** · 数据/训练: **LeRobot + SmolVLA**.

[![Status](https://img.shields.io/badge/status-WIP%20--%20M0-yellow.svg)](#)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

详细调研、设计动机、参考文献见 [`docs/RESEARCH.md`](docs/RESEARCH.md)。


## 快速开始

> **目前处于 M0 阶段**: 仅有最小可跑的 mock pipeline,真实的 RoboBrain / RoboCasa 接入将在 M1 完成。

```bash
git clone https://github.com/<you>/robohousekeeper-agent.git
cd robohousekeeper-agent
pip install -e .

# 跑一个 mock demo:模拟"擦桌子被打断"的场景
python scripts/run_demo.py --task wipe_table --scenario interrupted
```


## Roadmap

- [x] **M0** — 调研文档 + 项目骨架 + mock pipeline ← *目前进度*
- [ ] **M1** — 单 RoboCasa 任务跑通 RoboBrain planner + 失败重试  *(rollout 模式借鉴 hermes-embodied)*
- [ ] **M2** — 加入 scene graph 主动 replan,覆盖 5-10 个任务
- [ ] **M3** — 接入 VLA cerebellum,跑 RoboCasa365 子集(20-30 任务)+ 完整 eval harness
- [ ] **M4** — Skill self-improvement loop:在线 lesson + 离线 patch + SmolVLA 自动 fine-tune + A/B checkpoint 比较  *(骨架直接改写自 [hermes-embodied](https://github.com/bryercowan/hermes-embodied))*

---
name: llm-finetune
display_name: "LLM Fine-tuning & Training Pipelines"
category: project
role_categories:
  - ml_engineer
  - research_engineer
  - llmops_engineer
  - data_scientist
seniority_range: [senior, staff]
tech_stacks:
  primary: ["Python", "PyTorch", "Transformers", "PEFT", "TRL", "FastAPI", "Weights & Biases"]
  alternatives: ["Unsloth", "Axolotl", "LLaMA Factory", "DeepSpeed", "FSDP", "MLflow"]
complexity_range: [7, 10]
estimated_loc: [1500, 5000]
sandbox_requirements:
  base_image: letsbuild/sandbox:latest
  extra_packages: ["libgomp1"]
  timeout_minutes: 35
topology: sequential
---

## Overview

LLM fine-tuning and training pipeline skill files generate production-grade machine learning training infrastructure: data preparation pipelines, parameter-efficient fine-tuning (PEFT/LoRA) configurations, evaluation harnesses, model versioning, and serving infrastructure. These projects are among the highest-signal portfolio pieces for ML engineering roles because they demonstrate understanding of the full model lifecycle — from raw data through training, evaluation, registration, and deployment. Because fine-tuning large models requires significant GPU compute that is unavailable in the sandbox, generated projects are structured so that the data pipeline, training configuration, and evaluation framework can be fully tested with tiny synthetic models (1M parameter stubs) while the full training configuration targets real models.

## Project Templates

### 1. Domain-Specific Instruction Fine-tuning Pipeline

- **Name:** instruct-finetune
- **One-liner:** An instruction fine-tuning pipeline for a domain-specific assistant using QLoRA on Llama-3, with data cleaning, prompt templating, training metrics, and an evaluation benchmark.
- **Seniority:** senior
- **Tech Stack:** Python, Transformers, PEFT (QLoRA), TRL (SFTTrainer), Weights & Biases, FastAPI
- **Complexity:** 7
- **Why It Impresses:** QLoRA (4-bit quantization + LoRA) makes fine-tuning accessible on single-GPU hardware while producing results comparable to full fine-tuning. A proper evaluation benchmark (not just training loss) demonstrates ML research discipline.

### 2. RLHF Pipeline with Reward Model

- **Name:** rlhf-pipeline
- **One-liner:** An RLHF pipeline with human preference data collection stubs, reward model training, PPO fine-tuning, and KL-divergence constraint monitoring.
- **Seniority:** staff
- **Tech Stack:** Python, Transformers, TRL (PPOTrainer, RewardTrainer), PEFT, Weights & Biases
- **Complexity:** 10
- **Why It Impresses:** RLHF is the technique behind ChatGPT-style alignment. A working RLHF pipeline — even with synthetic preference data — demonstrates cutting-edge ML engineering knowledge that very few portfolio projects show. KL-divergence monitoring proves understanding of the reward hacking problem.

### 3. Continual Learning Pipeline with Catastrophic Forgetting Mitigation

- **Name:** continual-lm
- **One-liner:** A continual learning pipeline that fine-tunes a language model on sequential domain datasets while mitigating catastrophic forgetting using Elastic Weight Consolidation (EWC).
- **Seniority:** staff
- **Tech Stack:** Python, PyTorch, Transformers, PEFT, scikit-learn, Weights & Biases
- **Complexity:** 9
- **Why It Impresses:** Catastrophic forgetting is a fundamental challenge in continual learning. Demonstrating EWC (computing and preserving the Fisher information matrix to protect important weights) shows deep understanding of the underlying optimization dynamics — a topic covered in ML research courses but rarely implemented in practice.

### 4. Multi-task Fine-tuning with Task Routing

- **Name:** multitask-ft
- **One-liner:** A multi-task fine-tuning framework that trains a single model on multiple NLP tasks simultaneously with task-specific LoRA adapters, a mixture-of-experts routing head, and per-task evaluation.
- **Seniority:** staff
- **Tech Stack:** Python, PyTorch, Transformers, PEFT (multiple LoRA adapters), TRL, Weights & Biases
- **Complexity:** 10
- **Why It Impresses:** Per-task LoRA adapters with a routing head is a research-frontier technique for multi-task models. It demonstrates understanding of parameter-efficient multi-task learning at the level expected in ML research engineering roles.

### 5. Data Flywheel Pipeline

- **Name:** data-flywheel
- **One-liner:** A data flywheel pipeline that collects production model outputs, filters by quality score, generates preference pairs, retrains the reward model, and closes the loop with a new fine-tuning run.
- **Seniority:** senior
- **Tech Stack:** Python, Transformers, TRL, FastAPI, SQLite, asyncio, Weights & Biases
- **Complexity:** 8
- **Why It Impresses:** The data flywheel (production usage → data collection → model improvement → deployment) is the continuous improvement loop that makes commercial AI products better over time. Demonstrating a working flywheel pipeline signals senior ML engineering maturity.

## Architecture Patterns

All LLM fine-tuning projects generated by this skill MUST follow these patterns:

1. **Data pipeline is separate from training.** The data preparation pipeline (`data/`) reads raw data, applies cleaning, formatting, and train/val/test splits, and writes versioned JSONL datasets. Training scripts read from versioned datasets only — never from raw data.

2. **Training is reproducible.** Every training run logs: random seed, model name, dataset version, hyperparameters, hardware specs, and library versions. The training configuration is a YAML file (not command-line arguments) so it is committed to version control.

3. **Evaluation is automated and structured.** An `eval/` directory contains evaluation scripts that produce a `results.json` with per-task and aggregate metrics. Evaluation runs against a held-out test set that is never used during training.

4. **Model versioning uses a registry.** Fine-tuned models are registered in a `model_registry.json` with: base model name, LoRA adapter path, training run ID, evaluation metrics, training date, and SHA-256 checksum of adapter weights.

5. **Training can run with tiny synthetic models.** The training configuration has a `--debug` or `--smoke-test` flag that replaces the real model with a 1M parameter synthetic model and the real dataset with a 100-example synthetic dataset. This allows CI to validate the training loop without GPU compute.

6. **Experiment tracking is mandatory.** All training runs log to Weights & Biases (or MLflow as an alternative). The `wandb.log()` calls for training loss, validation loss, and evaluation metrics are not optional.

## File Tree Template

```
project-name/
├── README.md
├── model_registry.json
├── docs/
│   └── decisions/
│       ├── 001-peft-strategy.md
│       └── 002-evaluation-design.md
├── data/
│   ├── raw/
│   │   └── .gitkeep
│   ├── processed/
│   │   └── .gitkeep
│   └── prepare_data.py
├── training/
│   ├── __init__.py
│   ├── train.py
│   ├── config/
│   │   └── base_config.yaml
│   └── utils/
│       ├── __init__.py
│       └── data_utils.py
├── eval/
│   ├── run_eval.py
│   └── benchmarks/
│       └── sample_benchmark.jsonl
├── serving/
│   ├── __init__.py
│   ├── main.py
│   └── inference.py
├── tests/
│   ├── conftest.py
│   ├── test_data_pipeline.py
│   ├── test_training_loop.py
│   └── test_evaluation.py
├── scripts/
│   ├── download_base_model.py
│   └── register_model.py
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .github/
│   └── workflows/
│       └── ci.yml
└── .gitignore
```

## Quality Criteria

The QualityGate checks the following for LLM fine-tuning projects:

1. **Tests pass with smoke-test mode.** `pytest tests/ -v` runs the full test suite using synthetic tiny models. No tests require a GPU or real model weights.
2. **Data pipeline produces valid output.** `python data/prepare_data.py --sample` runs end-to-end and produces a valid JSONL file with the correct schema.
3. **Training loop runs in smoke-test mode.** `python training/train.py --smoke-test` completes without error, demonstrating the full training loop on synthetic data.
4. **Evaluation script runs.** `python eval/run_eval.py --sample` produces a `results.json` with the expected metric fields.
5. **Model registry schema is valid.** `model_registry.json` validates against the documented schema (base_model, adapter_path, eval_metrics, training_date, checksum).
6. **No model weights committed.** `.gitignore` excludes `*.bin`, `*.safetensors`, `*.pt` files.
7. **Linting and type checking pass.** `ruff check .` and `mypy --strict training/ eval/ serving/` both exit with code 0.

## Sandbox Validation Plan

```yaml
sandbox_validation_plan:
  - "cd /mnt/workspace && pip install -e '.[dev]'"
  - "cd /mnt/workspace && pytest tests/ -v"
  - "cd /mnt/workspace && ruff check . && ruff format --check ."
  - "cd /mnt/workspace && mypy --strict training/ eval/ serving/"
  - "cd /mnt/workspace && python data/prepare_data.py --sample --output /tmp/sample_data.jsonl"
  - "cd /mnt/workspace && python training/train.py --smoke-test --output-dir /tmp/smoke-run"
  - "cd /mnt/workspace && python eval/run_eval.py --sample --model-path /tmp/smoke-run"
```

## ADR Templates

### ADR-001: PEFT Strategy

**Status:** Accepted

**Context:** Full fine-tuning of large language models requires expensive multi-GPU infrastructure. We need a parameter-efficient approach that produces competitive results on a single GPU or in the sandbox.

**Decision:** QLoRA (Quantized LoRA): 4-bit NF4 quantization of the base model with LoRA adapters on all attention projection matrices (q_proj, k_proj, v_proj, o_proj) and MLP layers. This reduces VRAM requirements from ~40GB (full 7B fine-tune) to ~6GB (QLoRA 7B) while retaining 95%+ of the performance of full fine-tuning on most tasks.

**Consequences:** The base model is frozen. Only LoRA adapter weights (~50-200MB) are trained and stored. The adapter can be merged with the base model for inference or served separately via PEFT's `PeftModel.from_pretrained()`. Sandbox testing uses a 1M-parameter synthetic model that requires no GPU.

### ADR-002: Evaluation Design

**Status:** Accepted

**Context:** Training loss (perplexity) is a poor proxy for downstream task performance. We need a structured evaluation that measures what the model is actually intended to do.

**Decision:** Multi-metric evaluation with three categories: (1) task-specific metrics (F1, BLEU, ROUGE, accuracy depending on the task), (2) alignment metrics (instruction-following rate evaluated by a judge model), (3) regression metrics (performance on a held-out general capability benchmark to detect catastrophic forgetting). All metrics are logged to W&B and saved to `results.json`.

**Consequences:** Evaluation takes longer than measuring just training loss but produces actionable results. The judge model for alignment evaluation uses the same Anthropic SDK pattern as the rest of LetsBuild (tool_use with structured output).

### ADR-003: Data Quality Pipeline

**Status:** Accepted

**Context:** Fine-tuning data quality directly determines model quality. Noisy, mislabeled, or low-quality training examples cause models to learn incorrect behaviors.

**Decision:** Three-stage data quality pipeline: (1) rule-based filters (length constraints, language detection, deduplication by MinHash), (2) model-based quality scoring (using a small classifier to score instruction-following quality), (3) human review sample (10% of training data flagged for spot-check review). Each stage has configurable pass/fail thresholds documented in the training config YAML.

**Consequences:** Data cleaning reduces training set size by 15-40% but improves model quality and training efficiency. The filtering thresholds are hyperparameters that can be tuned. All filtering decisions are logged for auditability.

## Common Failure Modes

1. **Training loop OOM on CPU in smoke-test mode.** Even synthetic tiny models can OOM if batch size is not reduced for smoke tests. Fix: `--smoke-test` flag must set `per_device_train_batch_size=1` and `gradient_accumulation_steps=1` regardless of the config file setting.

2. **W&B API key required but absent in CI.** Weights & Biases calls fail in CI if no API key is present. Fix: check for `WANDB_API_KEY` at startup and fall back to `wandb.init(mode="offline")` if absent. Tests always use offline mode.

3. **LoRA rank hyperparameter incompatibility.** LoRA rank must be compatible with the target module's hidden dimension. A rank > hidden_dim/2 is unusual and may not train well. Fix: validate `lora_rank <= target_module_hidden_dim // 4` at config load time.

4. **Checkpoint loading fails due to architecture mismatch.** Loading a LoRA adapter trained on model version A into model version B fails if the architecture has changed. Fix: store the base model name and revision in the model registry, and validate compatibility on load.

5. **Evaluation benchmark contamination.** If the training data overlaps with the evaluation benchmark (data leakage), evaluation metrics are inflated and misleading. Fix: run an n-gram overlap check between training data and the benchmark as part of the data preparation pipeline, and log the contamination rate to W&B.

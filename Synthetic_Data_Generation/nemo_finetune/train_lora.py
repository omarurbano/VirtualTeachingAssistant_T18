"""
LoRA / QLoRA Fine-tuning Pipeline
====================================
Uses HuggingFace TRL (SFTTrainer) + PEFT (LoRA) + bitsandbytes (4-bit QLoRA).

Prerequisites:
  pip install -r requirements.txt
  python gen_data.py --mode drive --folder-id <id>   # generate dataset first

Usage:
  # Full fine-tune (QLoRA 4-bit):
  python nemo_finetune/train_lora.py --dataset Synthetic_Data_Generation/output/training_dataset.jsonl

  # Dry-run (no GPU, just verify data loading):
  python nemo_finetune/train_lora.py --dataset ... --dry-run
"""

import logging
log = logging.getLogger("lora_train")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

import argparse
import json
import os
import sys
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer


def load_jsonl_dataset(path: str):
    return load_dataset("json", data_files=path, split="train")


def format_example(example: dict, tokenizer) -> dict:
    instruction = example.get("instruction", "")
    input_text = example.get("input", "")
    output = example.get("output", "")
    if input_text:
        prompt = f"### Instruction:\n{instruction}\n\n### Input:\n{input_text}\n\n### Response:\n"
    else:
        prompt = f"### Instruction:\n{instruction}\n\n### Response:\n"
    full_text = prompt + output + tokenizer.eos_token
    return {"text": full_text}


def train(
    dataset_path: str,
    base_model: str,
    output_dir: str,
    lora_rank: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    num_epochs: int = 3,
    batch_size: int = 4,
    gradient_accumulation: int = 4,
    learning_rate: float = 2e-4,
    max_seq_length: int = 2048,
    dry_run: bool = False,
):
    log.info("Loading dataset from %s …", dataset_path)
    dataset = load_jsonl_dataset(dataset_path)
    log.info("Dataset loaded: %d records.", len(dataset))

    if dry_run:
        log.info("Dry-run mode — printing first 3 examples:")
        for i, ex in enumerate(dataset.select(range(min(3, len(dataset))))):
            log.info("--- Example %d ---\n%s\n", i + 1, json.dumps(ex, indent=2))
        return

    log.info("Loading base model: %s (QLoRA 4-bit) …", base_model)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    log.info("Configuring LoRA adapter (rank=%d, alpha=%d) …", lora_rank, lora_alpha)
    peft_config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )

    log.info("Tokenizing dataset …")
    def tokenize_fn(example):
        formatted = format_example(example, tokenizer)
        tokenized = tokenizer(
            formatted["text"],
            truncation=True,
            max_length=max_seq_length,
            padding="max_length",
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    tokenized_ds = dataset.map(tokenize_fn, remove_columns=dataset.column_names, desc="Tokenizing")

    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation,
        num_train_epochs=num_epochs,
        learning_rate=learning_rate,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=10,
        save_steps=500,
        save_total_limit=2,
        report_to="none",
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_ds,
        peft_config=peft_config,
        tokenizer=tokenizer,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
    )

    log.info("Starting fine-tuning …")
    trainer.train()
    log.info("Saving LoRA adapter to %s …", output_dir)
    trainer.model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    log.info("✅ Fine-tuning complete. Adapter saved to %s", output_dir)


def main():
    parser = argparse.ArgumentParser(description="LoRA/QLoRA Fine-tuning Pipeline")
    parser.add_argument("--dataset", required=True, help="Path to JSONL training dataset")
    parser.add_argument("--base-model", default=os.getenv("FINETUNE_BASE_MODEL", "nvidia/nemotron-4-7b-instruct"))
    parser.add_argument("--output-dir", default=os.getenv("FINETUNE_OUTPUT_DIR", "./lora_adapter"))
    parser.add_argument("--lora-rank", type=int, default=int(os.getenv("FINETUNE_LORA_RANK", 16)))
    parser.add_argument("--lora-alpha", type=int, default=int(os.getenv("FINETUNE_LORA_ALPHA", 32)))
    parser.add_argument("--epochs", type=int, default=int(os.getenv("FINETUNE_EPOCHS", 3)))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("FINETUNE_BATCH_SIZE", 4)))
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--dry-run", action="store_true", help="Verify data without training")
    args = parser.parse_args()
    train(
        dataset_path=args.dataset,
        base_model=args.base_model,
        output_dir=args.output_dir,
        lora_rank=args.lora_rank,
        lora_alpha=args.lora_alpha,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        max_seq_length=args.max_seq_length,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

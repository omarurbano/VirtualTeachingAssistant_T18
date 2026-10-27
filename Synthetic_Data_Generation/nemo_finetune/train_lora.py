"""QLoRA fine-tuning script for the VTA teaching-assistant model using Unsloth.

Run on a machine with an NVIDIA GPU (>=4GB VRAM) and CUDA.
Usage:
    python train_lora.py --data path/to/training_dataset.jsonl --base qwen2.5-coder:7b --out ./vta-lora
"""
import argparse
import json
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="JSONL file with chat-format examples")
    parser.add_argument("--base", default="unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit")
    parser.add_argument("--out", default="./vta-lora")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-4)
    args = parser.parse_args()

    # Lazy imports so the file can be inspected without deps installed.
    from unsloth import FastLanguageModel
    from datasets import load_dataset
    from trl import SFTTrainer
    from transformers import TrainingArguments

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base,
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # Expect JSONL lines like: {"messages": [{"role":"system",...},{"role":"user",...},{"role":"assistant",...}]}
    dataset = load_dataset("json", data_files=args.data, split="train")

    def format_example(ex):
        return {"text": tokenizer.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)}

    dataset = dataset.map(format_example)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=2048,
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            per_device_train_batch_size=args.batch,
            gradient_accumulation_steps=args.grad_accum,
            warmup_steps=5,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            fp16=True,
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=42,
            output_dir=args.out,
            save_strategy="epoch",
        ),
    )
    trainer.train()
    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)
    # Export to GGUF for Ollama import
    model.save_pretrained_gguf(args.out + "/gguf", tokenizer, quantization_method="q4_k_m")
    print("Training complete. GGUF saved to", args.out + "/gguf")


if __name__ == "__main__":
    main()

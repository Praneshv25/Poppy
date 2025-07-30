import torch
import json
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, PeftModel
from trl import SFTTrainer

# --- 1. Configuration ---

# Path to your JSONL dataset
DATASET_PATH = "./dataset.jsonl"

# Hugging Face model you want to fine-tune
MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"

# The name of the new model you're creating
NEW_MODEL_NAME = "meLlamo-expert-robot-v1"


# --- 2. Load and Format the Dataset ---

# Define the formatting function
def format_instruction(sample):
    # Ensure the output is a clean JSON string
    output_json_string = json.dumps(sample['output'])

    # Create the prompt structure
    return f"""### Instruction:
{sample['instruction']}

### Input:
{sample['input']}

### Response:
{output_json_string}"""


# Load the dataset
dataset = load_dataset("json", data_files=DATASET_PATH, split="train")

print("Original dataset sample:", dataset[0])
print("\nFormatted dataset sample:", format_instruction(dataset[0]))

# --- 3. Configure Model and Tokenizer ---

# Configure 4-bit quantization to save memory
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,  # Use bfloat16 for better performance
)

# Load the base model with quantization
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    quantization_config=bnb_config,
    torch_dtype=torch.bfloat16,
    device_map="auto",  # Automatically place the model on available GPUs
    trust_remote_code=True,
)
model.config.use_cache = False  # Disable cache for training
model.config.pretraining_tp = 1

# Load the tokenizer
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
# Set a padding token if one is not already set
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"  # Important for correct padding

# --- 4. Configure LoRA (PEFT) ---
# LoRA (Low-Rank Adaptation) is a technique to train only a small fraction
# of the model's weights, which is much more memory-efficient.

peft_config = LoraConfig(
    lora_alpha=16,
    lora_dropout=0.1,
    r=64,  # Rank of the adaptation matrices. Higher rank means more trainable parameters.
    bias="none",
    task_type="CAUSAL_LM",
)

# --- 5. Set Up Training Arguments and Trainer ---

training_arguments = TrainingArguments(
    output_dir=f"./{NEW_MODEL_NAME}-results",
    num_train_epochs=2,  # 1-3 epochs is usually enough for fine-tuning
    per_device_train_batch_size=2,  # Reduce if you run out of memory
    gradient_accumulation_steps=2,  # Simulate a larger batch size
    optim="paged_adamw_32bit",  # Memory-efficient optimizer
    logging_steps=25,
    learning_rate=2e-4,
    weight_decay=0.001,
    fp16=False,  # Set to False when using 4-bit quantization
    bf16=True,  # Set to True when using 4-bit quantization
    max_grad_norm=0.3,
    max_steps=-1,  # -1 means train for the specified number of epochs
    warmup_ratio=0.03,
    group_by_length=True,  # Group sequences of similar length to save time and memory
    lr_scheduler_type="constant",  # Use a constant learning rate
)

# Initialize the SFTTrainer (Supervised Fine-tuning Trainer)
trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    peft_config=peft_config,
    dataset_text_field="text",  # We will format the text ourselves
    formatting_func=format_instruction,  # Use our custom formatting function
    max_seq_length=1024,  # Adjust based on your VRAM and typical prompt length
    tokenizer=tokenizer,
    args=training_arguments,
)

# --- 6. Train the Model ---

print("Starting training...")
trainer.train()
print("Training finished!")

# --- 7. Save the Fine-tuned Model ---
print(f"Saving fine-tuned model to ./{NEW_MODEL_NAME}")
trainer.save_model(NEW_MODEL_NAME)
print("Model saved successfully!")
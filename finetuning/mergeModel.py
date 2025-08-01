# save_merged_model.py
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE_MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"
ADAPTER_PATH = "../meLlamo-expert-robot-v1"
MERGED_MODEL_PATH = "../meLlamo-expert-robot-v1-merged"

print("Loading base model...")
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL_ID,
    torch_dtype=torch.float16,
    trust_remote_code=True,
)

print("Loading adapter...")
model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)

print("Merging adapter into base model...")
model = model.merge_and_unload()

print(f"Saving merged model to {MERGED_MODEL_PATH}...")
model.save_pretrained(MERGED_MODEL_PATH)
tokenizer = AutoTokenizer.from_pretrained(ADAPTER_PATH)
tokenizer.save_pretrained(MERGED_MODEL_PATH)

print("? Merged model saved successfully!")
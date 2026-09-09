import argparse
import hashlib
import json
import os
import random
from dataclasses import dataclass, field
from typing import List
import requests
from dotenv import load_dotenv
load_dotenv()  # Load .env file into environment


OLLAMA_URL = os.getenv("O_URL")
OLLAMA_MODEL = os.getenv("O_MODEL")

@dataclass
class SeedExample:
    '''A class to represent a seed example for generating synthetic data.'''
    topic: str
    instructions: str
    response: str
    tags: List[str] = field(default_factory=list)

#Add examples here to seed the generation process. Each example should have a topic, instructions, a response, and optional tags.
SEED_EXAMPLES = [
    SeedExample(
        topic="Software Engineering",
        instructions="Explain the importance of version control in software development.",
        response="Version control is crucial in software development as it allows multiple developers to work on the same codebase without conflicts. It also provides a history of changes, making it easy to track and revert to previous versions if needed.",
        tags=["software", "development", "version control"]
    ),
    SeedExample(
        topic="Software Engineering",
        instructions="What are the benefits of using automated testing in software development?",
        response="Automated testing helps ensure that code changes do not introduce new bugs, saves time by running tests quickly, and allows for continuous integration and delivery. It also improves code quality and reliability.",
        tags=["software", "testing", "automation"]
    ),
    SeedExample(
        topic="Software Engineering",
        instructions="Describe the concept of continuous integration and its advantages.",
        response="Continuous integration is a development practice where developers frequently merge their code changes into a central repository, followed by automated builds and tests. This practice helps detect errors early, improves collaboration among team members, and accelerates the development process by ensuring that the codebase is always in a deployable state.",
        tags=["software", "continuous integration", "development"]
    )
]

# Probs need to adjust this
INSTRUCTION_TEMPLATE = [
    "{instruction}",
    "Explain this as a beginner: {instruction_lower}",
    "In a couple of sentences, {instruction_lower}",
    "I'm new to software engineering -- {instruction_lower}",
    "For a software engineering doc, answer {instruction_lower}",
    "Quiz me: {instruction}"
]

def augment_instruction(instruction: str) -> List[str]:
    '''Augment the instruction using a random template.'''
    template = random.choice(INSTRUCTION_TEMPLATE)
    return template.format(
        instruction=instruction,
        instruction_lower=instruction[0].lower() + instruction[1:]
    )

def call_llm_to_rewrite(instruction:str, base_response:str) -> str:
    '''Call the LLM to rewrite the base response based on the instruction.'''
    prompt = (
        "Rewrite the following answer to match the tone/length implied by "
        "this instruction. Keep it factual and safe (no code execution, personal info). "
        "Return only the rewritten answer.\n\n"
        f"Instruction: {instruction}\n"
        f"Original Answer: {base_response}\n"
    )
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120
        )
        response.raise_for_status()
        text = response.json().get("response", "").strip()
        return text if text else base_response
    except requests.RequestException as e:
        print(f"Error calling LLM: {e}, falling back to base response.")
        return base_response

def is_valid(instruction: str, response: str) -> bool:
    '''Check if the generated instruction and response are valid.'''
    if len(instruction.strip()) < 8:
        return False
    if len(response.strip()) < 20:
        return False
    return True

def content_hash(instruction: str, response: str) -> str:
    '''Generate a unique hash for the instruction and response pair.'''
    return hashlib.sha256((instruction + "||" + response).encode("utf-8")).hexdigest()

def generate_examples(num_per_seed: int) -> List[dict]:
    '''Generate synthetic examples based on seed examples.'''
    seen_hashes = set()
    records = []

    for seed in SEED_EXAMPLES:
        for _ in range(num_per_seed):
            instruction = augment_instruction(seed.instructions)
            response = call_llm_to_rewrite(instruction, seed.response)
            if not is_valid(instruction, response):
                continue
            record_hash = content_hash(instruction, response)
            if record_hash in seen_hashes:
                continue
            seen_hashes.add(record_hash)
            records.append({
                "instruction": instruction,
                "response": response,
                "tags": seed.tags
            })
        write_examples_to_file(records, f"synthetic_data_{seed.topic.replace(' ', '_')}.json")
    return records

def write_examples_to_file(examples: List[dict], filename: str):
    '''Write the generated examples to a JSON file.'''
    with open("Synthetic_Data_Generation/" + filename, 'w') as f:
        json.dump(examples, f, indent=2)

if __name__ == "__main__":

    examples = generate_examples(num_per_seed=3)
    print(json.dumps(examples, indent=2))
from djl_python import Input, Output
import deepspeed
import torch
from transformers import pipeline, AutoModelForCausalLM, AutoTokenizer

torch.manual_seed(1234)

def load_model(properties):
    tensor_parallel = properties["tensor_parallel_degree"]
    model = AutoModelForCausalLM.from_pretrained(properties["model_dir"])
    tokenizer = AutoTokenizer.from_pretrained(properties["model_dir"], use_fast=False)
    model = deepspeed.init_inference(model,
                                     mp_size=tensor_parallel,
                                     dtype=model.dtype,
                                     replace_method='auto',
                                     replace_with_kernel_inject=True)
    return model, tokenizer


def get_reserved_memory():
    return [torch.cuda.memory_reserved(i) for i in range(torch.cuda.device_count())]


def batch_generation(batch_size):
    input_sentences = [
        "DeepSpeed is a machine learning framework",
        "He is working on",
        "He has a",
        "He got all",
        "Everyone is happy and I can",
        "The new movie that got Oscar this year",
        "In the far far distance from our galaxy,",
        "Peace is the only way",
    ]
    if batch_size > len(input_sentences):
        # dynamically extend to support larger bs by repetition
        input_sentences *= math.ceil(batch_size / len(input_sentences))
    return input_sentences[: batch_size]


model = None
tokenizer = None


def handle(inputs: Input):
    global model, tokenizer
    if not model:
        model, tokenizer = load_model(inputs.get_properties())

    if inputs.is_empty():
        # Model server makes an empty call to warmup the model on startup
        return None
    data = inputs.get_as_json()
    batch_size = data["batch_size"]
    tokens_to_gen = data["text_length"]
    result = {"reserved_memory": get_reserved_memory()}
    generate_kwargs = dict(min_length=tokens_to_gen, max_new_tokens=tokens_to_gen, do_sample=False)
    input_tokens = tokenizer.batch_encode_plus(batch_generation(batch_size), return_tensors="pt", padding=True)
    outputs = model.generate(**input_tokens, **generate_kwargs)
    outputs = tokenizer.batch_decode(outputs, skip_special_tokens=True)
    result["outputs"] = outputs
    return Output().add_as_json(result)

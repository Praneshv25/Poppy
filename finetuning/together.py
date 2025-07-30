import together

together.api_key = "9e49a17321c9878e825fb16777bf6e1c1406013fd454a239d1e55b399b291ba9"

resp = together.Files.check(file="/Users/PV/PycharmProjects/meLlamo/finetuning/dataset.jsonl")
print(resp)